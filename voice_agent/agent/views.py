import base64
import hashlib
import hmac
import json
import os
import re
import tempfile
import time
import unicodedata
import requests as _requests

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from groq import Groq

# ── API keys ──────────────────────────────────────────────────────────────────
_tavily_key = getattr(settings, 'TAVILY_API_KEY',    '')
_genius_key = getattr(settings, 'GENIUS_API_KEY',    '')
_acr_host   = getattr(settings, 'ACR_HOST',          '')
_acr_key    = getattr(settings, 'ACR_ACCESS_KEY',    '')
_acr_secret = getattr(settings, 'ACR_ACCESS_SECRET', '')

_tavily = bool(_tavily_key)
_genius = bool(_genius_key)
_acr    = bool(_acr_host and _acr_key and _acr_secret)

# ── Groq client ───────────────────────────────────────────────────────────────
client = Groq(api_key=settings.GROQ_API_KEY)

# ── Regex patterns ────────────────────────────────────────────────────────────
_WEB_SEARCH_PATTERNS = re.compile(
    r'\b(today|tonight|right now|current(ly)?|latest|recent(ly)?|'
    r'news|happening|update|score|weather|price|stock|'
    r'who (is|are|won|leads)|what (is|are) the (latest|current|today)|'
    r'did .* (win|lose|happen)|'
    r'2024|2025|2026)\b',
    re.IGNORECASE
)

_LYRICS_PATTERNS = re.compile(
    r'\b(lyric|lyrics|what song|which song|who sings|who sang|'
    r"what's this song|name this song|identify (this )?song|"
    r'song with|the song (that|where|which)|find (the )?song|'
    r'singer|artist|what band|who made|who wrote|'
    r'goes like|sounds like|the words|the line)\b',
    re.IGNORECASE
)

# ── Whisper known hallucination phrases ───────────────────────────────────────
_WHISPER_HALLUCINATIONS = {
    'thank you', 'thanks', 'thank you.', 'thanks.',
    'you', 'the', 'a', '.', '...', 'bye', 'bye.',
    'goodbye', 'goodbye.', 'please', 'sorry',
    'thank you for watching', 'thank you for watching.',
    'thanks for watching', 'thanks for watching.',
    'thank you very much', 'thank you very much.',
    'subtitles by', 'subscribe', 'like and subscribe',
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _needs_web_search(text: str) -> bool:
    return bool(_WEB_SEARCH_PATTERNS.search(text))


def _needs_lyrics_search(text: str) -> bool:
    return bool(_LYRICS_PATTERNS.search(text))


def _is_gibberish(text: str) -> bool:
    """
    Detect when Whisper transcribes music/noise as non-Latin script gibberish.
    When music plays, Whisper often outputs Hindi/Devanagari/Arabic characters
    instead of the user's speech. We detect this by checking if the majority
    of characters fall outside basic Latin Unicode range.
    """
    if not text:
        return False
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    non_latin = sum(1 for c in letters if ord(c) > 591)
    return (non_latin / len(letters)) > 0.6


# ── ACRCloud audio fingerprint recognition ────────────────────────────────────

def _acr_recognize(audio_bytes: bytes) -> dict | None:
    """
    Send audio bytes to ACRCloud for song recognition via audio fingerprinting.
    Returns a dict with title, artists, album, genres or None if not recognized.
    Uses HMAC-SHA1 signature authentication as required by ACRCloud API.
    """
    if not _acr:
        return None
    try:
        timestamp      = str(int(time.time()))
        string_to_sign = '\n'.join(['POST', '/v1/identify', _acr_key, 'audio', '1', timestamp])
        sign = base64.b64encode(
            hmac.new(
                _acr_secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                digestmod=hashlib.sha1
            ).digest()
        ).decode('utf-8')

        resp = _requests.post(
            f'https://{_acr_host}/v1/identify',
            files={'sample': ('audio.webm', audio_bytes, 'audio/webm;codecs=opus')},
            data={
                'access_key':        _acr_key,
                'sample_bytes':      str(len(audio_bytes)),
                'timestamp':         timestamp,
                'signature':         sign,
                'data_type':         'audio',
                'signature_version': '1',
            },
            timeout=10,
        )
        result = resp.json()

        if result.get('status', {}).get('code', -1) != 0:
            return None

        music   = result.get('metadata', {}).get('music', [{}])[0]
        title   = music.get('title', 'Unknown')
        artists = ', '.join(a.get('name', '') for a in music.get('artists', []))
        album   = music.get('album', {}).get('name', '')
        genres  = ', '.join(g.get('name', '') for g in music.get('genres', []))
        isrc    = music.get('external_ids', {}).get('isrc', '')

        return {'title': title, 'artists': artists, 'album': album,
                'genres': genres, 'isrc': isrc}

    except Exception:
        return None


def _format_acr_result(song: dict) -> str:
    """Format ACRCloud result into a context string for LLaMA."""
    ctx = f'[Song recognition result]: Song: "{song["title"]}" by {song["artists"]}.'
    if song.get('album'):
        ctx += f' Album: {song["album"]}.'
    if song.get('genres'):
        ctx += f' Genre: {song["genres"]}.'
    return ctx


# ── Tavily web search ─────────────────────────────────────────────────────────

def _web_search(query: str) -> str:
    if not _tavily_key:
        return ''
    try:
        resp = _requests.post(
            'https://api.tavily.com/search',
            json={
                'api_key':        _tavily_key,
                'query':          query,
                'search_depth':   'basic',
                'max_results':    3,
                'include_answer': True,
            },
            timeout=8,
        )
        data = resp.json()
        if data.get('answer'):
            return f'[Web search result]: {data["answer"]}'
        snippets = [r.get('content', '')[:300] for r in data.get('results', [])[:3]]
        return '[Web search results]:\n' + '\n---\n'.join(snippets)
    except Exception:
        return ''


# ── Genius lyrics search ──────────────────────────────────────────────────────

def _search_lyrics(query: str) -> str:
    if not _genius_key:
        return ''
    try:
        clean = re.sub(
            r'\b(what song|which song|who sings|who sang|lyrics|lyric|'
            r'goes like|sounds like|the words|identify|find the song|'
            r"name this song|what's this song|song with|the line)\b",
            '', query, flags=re.IGNORECASE
        ).strip() or query

        resp = _requests.get(
            'https://api.genius.com/search',
            headers={'Authorization': f'Bearer {_genius_key}'},
            params={'q': clean},
            timeout=8,
        )
        hits = resp.json().get('response', {}).get('hits', [])
        if not hits:
            return ''
        top    = hits[0]['result']
        title  = top.get('title', 'Unknown')
        artist = top.get('primary_artist', {}).get('name', 'Unknown')
        return f'[Lyrics search result]: Song: "{title}" by {artist}.'
    except Exception:
        return ''


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are NOVA — an intelligent, friendly AI voice assistant built with Whisper (deep learning STT) and LLaMA via Groq.

CRITICAL LANGUAGE RULE: You MUST ALWAYS respond in English only. No matter what language the user speaks in — your reply must ALWAYS be in English. Never switch to Arabic, Urdu, or any other language under any circumstances.

Your personality:
- Warm, conversational, and concise (voice-first: keep replies under 3 sentences unless asked for detail)
- You can discuss anything: programming, AI, science, sports, news, history, general knowledge, songs
- If asked who built you: "I was built by a DUET CS student using Whisper, Groq LLaMA, Django, and ACRCloud"
- Your knowledge goes up to early 2024. For anything after that, rely on the search result if provided.
- If a [Song recognition result] is provided, tell the user the song name and artist enthusiastically.
- If a [Lyrics search result] is provided, use it to clearly tell the user the song name and artist.

Rules:
- ALWAYS reply in English — this is non-negotiable
- Keep responses SHORT — they will be spoken aloud
- No markdown, no bullet points (this is voice output)
- If any search result is included in the message, use it to answer accurately
- Be encouraging and helpful
"""

# ── Session history ───────────────────────────────────────────────────────────

def _get_history(request):
    return request.session.get('chat_history', [])


def _save_history(request, history):
    max_turns = getattr(settings, 'MAX_HISTORY_TURNS', 10)
    if len(history) > max_turns * 2:
        history = history[-(max_turns * 2):]
    request.session['chat_history'] = history
    request.session.modified = True


# ── Views ─────────────────────────────────────────────────────────────────────

def index(request):
    return render(request, 'agent/index.html')


@csrf_exempt
@require_http_methods(["POST"])
def transcribe_audio(request):
    """
    Pipeline:
    1. Receive audio blob from browser
    2. Run ACRCloud audio fingerprint recognition (song detection)
    3. Run Groq Whisper STT (speech-to-text via verbose_json)
    4. Filter Whisper hallucinations, non-Latin gibberish, and silence
    5. Return transcript + song_detected to frontend
    """
    if not settings.GROQ_API_KEY:
        return JsonResponse({'error': 'GROQ_API_KEY not configured in .env'}, status=500)

    audio_file = request.FILES.get('audio')
    if not audio_file:
        return JsonResponse({'error': 'No audio file received'}, status=400)

    try:
        audio_bytes = audio_file.read()

        # Step 1 — ACRCloud song recognition
        song_detected = _acr_recognize(audio_bytes) if _acr else None

        # Step 2 — Whisper STT via Groq (verbose_json for segment-level data)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        with open(tmp_path, 'rb') as f:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(tmp_path), f, 'audio/webm'),
                model='whisper-large-v3',
                response_format='verbose_json',
                prompt='Transcribe the following English speech.',
            )
        os.unlink(tmp_path)

        # Step 3 — Extract transcript
        transcript_text = ''
        if hasattr(transcription, 'text') and transcription.text:
            transcript_text = transcription.text.strip()

        # Step 4 — Compute average no_speech_prob across segments
        no_speech_prob = 0.0
        if hasattr(transcription, 'segments') and transcription.segments:
            probs = []
            for seg in transcription.segments:
                if hasattr(seg, 'no_speech_prob'):
                    probs.append(seg.no_speech_prob)
                elif isinstance(seg, dict) and 'no_speech_prob' in seg:
                    probs.append(seg['no_speech_prob'])
            if probs:
                no_speech_prob = sum(probs) / len(probs)

        # Step 5 — Filter bad transcripts
        # 5a. Known Whisper hallucination phrases (silence/noise artifacts)
        if transcript_text.lower() in _WHISPER_HALLUCINATIONS:
            transcript_text = ''

        # 5b. Non-Latin gibberish — Whisper "hears" music as Hindi/Arabic characters
        #     Only suppress if song was detected (confirms it's music, not real speech)
        if song_detected and _is_gibberish(transcript_text):
            transcript_text = ''

        # 5c. Very short output with high silence probability = noise/silence
        if no_speech_prob > 0.85 and len(transcript_text.split()) <= 2:
            transcript_text = ''

        return JsonResponse({
            'transcript':    transcript_text,
            'song_detected': song_detected,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def chat(request):
    """
    Context injection priority:
    1. ACRCloud song_detected (audio fingerprint — highest priority)
    2. Genius lyrics search (text-based song query fallback)
    3. Tavily web search (live current events)
    4. LLaMA own knowledge (default)
    """
    if not settings.GROQ_API_KEY:
        return JsonResponse({'error': 'GROQ_API_KEY not configured in .env'}, status=500)

    try:
        body         = json.loads(request.body)
        user_message = body.get('message', '').strip()
        song_info    = body.get('song_detected', None)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    if not user_message and not song_info:
        return JsonResponse({'error': 'Empty message'}, status=400)

    if not user_message and song_info:
        user_message = 'What song is this?'

    # Context injection
    extra_context = ''
    used_acr      = False
    used_lyrics   = False
    used_web      = False

    if song_info:
        extra_context = _format_acr_result(song_info)
        used_acr      = True
    elif _genius and _needs_lyrics_search(user_message):
        extra_context = _search_lyrics(user_message)
        used_lyrics   = bool(extra_context)

    if not extra_context and _tavily and _needs_web_search(user_message):
        extra_context = _web_search(user_message)
        used_web      = bool(extra_context)

    # Build message list with history
    history  = _get_history(request)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)

    augmented = user_message
    if extra_context:
        augmented = f"{user_message}\n\n{extra_context}"
    augmented += "\n\n[Reminder: Reply in English only.]"
    messages.append({"role": "user", "content": augmented})

    try:
        response = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        )
        ai_reply = response.choices[0].message.content.strip()

        # Save clean history (without injected context)
        history.append({"role": "user",      "content": user_message})
        history.append({"role": "assistant", "content": ai_reply})
        _save_history(request, history)

        return JsonResponse({
            'reply':           ai_reply,
            'history_length':  len(history) // 2,
            'acr_used':        used_acr,
            'web_search_used': used_web,
            'lyrics_used':     used_lyrics,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def clear_history(request):
    request.session['chat_history'] = []
    request.session.modified = True
    return JsonResponse({'status': 'cleared'})
