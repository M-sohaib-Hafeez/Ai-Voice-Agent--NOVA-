import json
import os
import re
import tempfile
import requests as _requests

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from groq import Groq

_tavily_key  = getattr(settings, 'TAVILY_API_KEY',  '')
_genius_key  = getattr(settings, 'GENIUS_API_KEY',  '')
_tavily      = bool(_tavily_key)
_genius      = bool(_genius_key)

client = Groq(api_key=settings.GROQ_API_KEY)

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

def _needs_web_search(text: str) -> bool:
    return bool(_WEB_SEARCH_PATTERNS.search(text))

def _needs_lyrics_search(text: str) -> bool:
    return bool(_LYRICS_PATTERNS.search(text))

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
        data   = resp.json()
        answer = data.get('answer', '')
        if answer:
            return f"[Web search result]: {answer}"
        snippets = [r.get('content', '')[:300] for r in data.get('results', [])[:3]]
        return "[Web search results]:\n" + "\n---\n".join(snippets)
    except Exception:
        return ''

def _search_lyrics(query: str) -> str:
    """
    Search Genius for a song matching the lyrics snippet or song title query.
    Returns the song name and artist name.
    Genius API is completely free with no rate limit issues.
    """
    if not _genius_key:
        return ''
    try:
        clean_query = re.sub(
            r'\b(what song|which song|who sings|who sang|lyrics|lyric|'
            r'goes like|sounds like|the words|identify|find the song|'
            r'name this song|what\'s this song|song with|the line)\b',
            '', query, flags=re.IGNORECASE
        ).strip()

        if not clean_query:
            clean_query = query

        resp = _requests.get(
            'https://api.genius.com/search',
            headers={'Authorization': f'Bearer {_genius_key}'},
            params={'q': clean_query},
            timeout=8,
        )
        data = resp.json()
        hits = data.get('response', {}).get('hits', [])

        if not hits:
            return ''

        top        = hits[0]['result']
        title      = top.get('title', 'Unknown')
        artist     = top.get('primary_artist', {}).get('name', 'Unknown')
        genius_url = top.get('url', '')

        result = f"[Lyrics search result]: Song: \"{title}\" by {artist}."
        if genius_url:
            result += f" Full lyrics at: {genius_url}"
        return result

    except Exception:
        return ''

SYSTEM_PROMPT = """You are NOVA — an intelligent, friendly AI voice assistant built with Whisper (deep learning STT) and LLaMA via Groq.

CRITICAL LANGUAGE RULE: You MUST ALWAYS respond in English only. No matter what language the user speaks in — your reply must ALWAYS be in English. Never switch to Arabic, Urdu, or any other language under any circumstances.

Your personality:
- Warm, conversational, and concise (voice-first: keep replies under 3 sentences unless asked for detail)
- You can discuss anything: programming, AI, science, sports, news, history, general knowledge, songs
- If asked who built you: "I was built by a DUET CS student using Whisper, Groq LLaMA, and Django"
- Your knowledge goes up to early 2024. For anything after that, rely on the search result if provided.
- If a [Lyrics search result] is provided, use it to clearly tell the user the song name and artist.

Rules:
- ALWAYS reply in English — this is non-negotiable
- Keep responses SHORT — they will be spoken aloud
- No markdown, no bullet points (this is voice output)
- If a [Web search result] or [Lyrics search result] is included, use it to answer accurately
- Be encouraging and helpful
"""

def _get_history(request):
    return request.session.get('chat_history', [])

def _save_history(request, history):
    max_turns = getattr(settings, 'MAX_HISTORY_TURNS', 10)
    if len(history) > max_turns * 2:
        history = history[-(max_turns * 2):]
    request.session['chat_history'] = history
    request.session.modified = True
def index(request):
    return render(request, 'agent/index.html')


@csrf_exempt
@require_http_methods(["POST"])
def transcribe_audio(request):
    if not settings.GROQ_API_KEY:
        return JsonResponse({'error': 'GROQ_API_KEY not configured in .env'}, status=500)

    audio_file = request.FILES.get('audio')
    if not audio_file:
        return JsonResponse({'error': 'No audio file received'}, status=400)

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tmp:
            for chunk in audio_file.chunks():
                tmp.write(chunk)
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
        return JsonResponse({'transcript': transcript_text.strip()})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def chat(request):
    if not settings.GROQ_API_KEY:
        return JsonResponse({'error': 'GROQ_API_KEY not configured in .env'}, status=500)

    try:
        body = json.loads(request.body)
        user_message = body.get('message', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    if not user_message:
        return JsonResponse({'error': 'Empty message'}, status=400)

    extra_context = ''
    used_lyrics   = False
    used_web      = False

    if _genius and _needs_lyrics_search(user_message):
        extra_context = _search_lyrics(user_message)
        used_lyrics   = bool(extra_context)

    if not extra_context and _tavily and _needs_web_search(user_message):
        extra_context = _web_search(user_message)
        used_web      = bool(extra_context)

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

        history.append({"role": "user",      "content": user_message})
        history.append({"role": "assistant", "content": ai_reply})
        _save_history(request, history)

        return JsonResponse({
            'reply':           ai_reply,
            'history_length':  len(history) // 2,
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
