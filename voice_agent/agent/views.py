import base64
import hashlib
import hmac
import json
import os
import re
import tempfile
import time
import requests as _requests

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from groq import Groq

# ── API keys ──────────────────────────────────────────────────────────────────
_tavily_key = getattr(settings, 'TAVILY_API_KEY', '')
_genius_key = getattr(settings, 'GENIUS_API_KEY', '')
_acr_host = getattr(settings, 'ACR_HOST', '')
_acr_key = getattr(settings, 'ACR_ACCESS_KEY', '')
_acr_secret = getattr(settings, 'ACR_ACCESS_SECRET', '')

_tavily = bool(_tavily_key)
_genius = bool(_genius_key)
_acr = bool(_acr_host and _acr_key and _acr_secret)

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
    r'what\'s this song|name this song|identify (this )?song|'
    r'song with|the song (that|where|which)|find (the )?song|'
    r'singer|artist|what band|who made|who wrote|'
    r'goes like|sounds like|the words|the line)\b',
    re.IGNORECASE
)


# ── Detect query type ─────────────────────────────────────────────────────────
def _needs_web_search(text: str) -> bool:
    return bool(_WEB_SEARCH_PATTERNS.search(text))


def _needs_lyrics_search(text: str) -> bool:
    return bool(_LYRICS_PATTERNS.search(text))


# ── ACRCloud audio fingerprint recognition ────────────────────────────────────
def _acr_recognize(audio_bytes: bytes) -> dict | None:
    """
    Send audio bytes to ACRCloud for song recognition via audio fingerprinting.
    Returns a dict with title, artist, album, etc. or None if not recognized.
    Uses HMAC-SHA1 signature authentication as required by ACRCloud API.
    """
    if not _acr:
        return None
    try:
        # Build HMAC-SHA1 signature (ACRCloud requirement)
        http_method = 'POST'
        http_uri = '/v1/identify'
        data_type = 'audio'
        signature_version = '1'
        timestamp = str(int(time.time()))

        string_to_sign = '\n'.join([
            http_method, http_uri, _acr_key,
            data_type, signature_version, timestamp
        ])
        sign = base64.b64encode(
            hmac.new(
                _acr_secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                digestmod=hashlib.sha1
            ).digest()
        ).decode('utf-8')

        # POST to ACRCloud
        url = f'https://{_acr_host}/v1/identify'
        files = {'sample': ('audio.webm', audio_bytes, 'audio/webm')}
        data = {
            'access_key': _acr_key,
            'sample_bytes': len(audio_bytes),
            'timestamp': timestamp,
            'signature': sign,
            'data_type': data_type,
            'signature_version': signature_version,
        }

        resp = _requests.post(url, files=files, data=data, timeout=10)
        result = resp.json()

        # ACRCloud returns code 0 for a successful match
        status_code = result.get('status', {}).get('code', -1)
        if status_code != 0:
            return None  # No match found — silent fallback

        # Extract song metadata
        music = result.get('metadata', {}).get('music', [{}])[0]
        title = music.get('title', 'Unknown')
        artists = ', '.join(a.get('name', '') for a in music.get('artists', []))
        album = music.get('album', {}).get('name', '')
        genres = ', '.join(g.get('name', '') for g in music.get('genres', []))

        # Extract 3rd party links if available
        spotify_id = ''
        ext_ids = music.get('external_ids', {})
        if ext_ids.get('isrc'):
            spotify_id = ext_ids['isrc']

        return {
            'title': title,
            'artists': artists,
            'album': album,
            'genres': genres,
            'isrc': spotify_id,
        }

    except Exception:
        return None  # Always fail silently — don't break the pipeline


def _format_acr_result(song: dict) -> str:
    """Format ACRCloud result into a context string for LLaMA."""
    result = f'[Song recognition result]: Song: "{song["title"]}" by {song["artists"]}.'
    if song.get('album'):
        result += f' Album: {song["album"]}.'
    if song.get('genres'):
        result += f' Genre: {song["genres"]}.'
    return result


# ── Tavily web search ─────────────────────────────────────────────────────────
def _web_search(query: str) -> str:
    if not _tavily_key:
        return ''
    try:
        resp = _requests.post(
            'https://api.tavily.com/search',
            json={
                'api_key': _tavily_key,
                'query': query,
                'search_depth': 'basic',
                'max_results': 3,
                'include_answer': True,
            },
            timeout=8,
        )
        data = resp.json()
        answer = data.get('answer', '')
        if answer:
            return f'[Web search result]: {answer}'
        snippets = [r.get('content', '')[:300] for r in data.get('results', [])[:3]]
        return '[Web search results]:\n' + '\n---\n'.join(snippets)
    except Exception:
        return ''


# ── Genius lyrics search (fallback for text-based song queries) ───────────────
def _search_lyrics(query: str) -> str:
    if not _genius_key:
        return ''
    try:
        clean_query = re.sub(
            r'\b(what song|which song|who sings|who sang|lyrics|lyric|'
            r'goes like|sounds like|the words|identify|find the song|'
            r'name this song|what\'s this song|song with|the line)\b',
            '', query, flags=re.IGNORECASE
        ).strip() or query

        resp = _requests.get(
            'https://api.genius.com/search',
            headers={'Authorization': f'Bearer {_genius_key}'},
            params={'q': clean_query},
            timeout=8,
        )
        hits = resp.json().get('response', {}).get('hits', [])
        if not hits:
            return ''

        top = hits[0]['result']
        title = top.get('title', 'Unknown')
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
    1. Receive audio blob from browser
    2. Run ACRCloud audio fingerprint recognition (song detection)
    3. Run Groq Whisper transcription (speech-to-text)
    4. Return both transcript + song_detected to frontend
    """
    if not settings.GROQ_API_KEY:
        return JsonResponse({'error': 'GROQ_API_KEY not configured in .env'}, status=500)

    audio_file = request.FILES.get('audio')
    if not audio_file:
        return JsonResponse({'error': 'No audio file received'}, status=400)

    try:
        # Read audio bytes once — used for both ACRCloud and Whisper
        audio_bytes = audio_file.read()

        # ── Step 1: ACRCloud song recognition (runs on same audio blob) ──────
        song_detected = None
        if _acr:
            song_detected = _acr_recognize(audio_bytes)

        # ── Step 2: Whisper transcription ─────────────────────────────────────
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        with open(tmp_path, 'rb') as f:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(tmp_path), f, 'audio/webm'),
                model='whisper-large-v3',
                response_format='text',
                language='en',
                prompt='Transcribe the following English speech.',
            )

        os.unlink(tmp_path)
        transcript_text = transcription if isinstance(transcription, str) else transcription.text

        return JsonResponse({
            'transcript': transcript_text.strip(),
            'song_detected': song_detected,  # None or {title, artists, album, genres}
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def chat(request):
    """
    Priority order for context injection:
    1. ACRCloud song_detected (passed from frontend via JSON body)
    2. Genius lyrics search (if lyrics keywords in text)
    3. Tavily web search (if current events keywords in text)
    4. LLaMA answers from its own knowledge
    """
    if not settings.GROQ_API_KEY:
        return JsonResponse({'error': 'GROQ_API_KEY not configured in .env'}, status=500)

    try:
        body = json.loads(request.body)
        user_message = body.get('message', '').strip()
        song_info = body.get('song_detected', None)  # passed from voice.js
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    if not user_message and not song_info:
        return JsonResponse({'error': 'Empty message'}, status=400)

    # If no speech but song detected — create a message automatically
    if not user_message and song_info:
        user_message = 'What song is this?'

    # ── Context injection ─────────────────────────────────────────────────────
    extra_context = ''
    used_acr = False
    used_lyrics = False
    used_web = False

    # 1. ACRCloud result (highest priority — actual audio recognition)
    if song_info:
        extra_context = _format_acr_result(song_info)
        used_acr = True

    # 2. Genius lyrics search (text-based query)
    if not extra_context and _genius and _needs_lyrics_search(user_message):
        extra_context = _search_lyrics(user_message)
        used_lyrics = bool(extra_context)

    # 3. Tavily web search
    if not extra_context and _tavily and _needs_web_search(user_message):
        extra_context = _web_search(user_message)
        used_web = bool(extra_context)

    # ── Build messages ────────────────────────────────────────────────────────
    history = _get_history(request)
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

        # Save clean history (no injected context)
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": ai_reply})
        _save_history(request, history)

        return JsonResponse({
            'reply': ai_reply,
            'history_length': len(history) // 2,
            'acr_used': used_acr,
            'web_search_used': used_web,
            'lyrics_used': used_lyrics,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def clear_history(request):
    request.session['chat_history'] = []
    request.session.modified = True
    return JsonResponse({'status': 'cleared'})
