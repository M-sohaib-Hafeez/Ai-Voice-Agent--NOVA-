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

_tavily_key = getattr(settings, 'TAVILY_API_KEY', '')
_tavily = bool(_tavily_key)   # True if key exists

def _web_search(query: str) -> str:
    """Call Tavily REST API directly — no tavily-python package needed."""
    if not _tavily_key:
        return ''
    try:
        resp = _requests.post(
            'https://api.tavily.com/search',
            json={
                'api_key':      _tavily_key,
                'query':        query,
                'search_depth': 'basic',
                'max_results':  3,
                'include_answer': True,
            },
            timeout=8,
        )
        data = resp.json()
        answer = data.get('answer', '')
        if answer:
            return f"[Web search result]: {answer}"
        snippets = [r.get('content', '')[:300] for r in data.get('results', [])[:3]]
        return "[Web search results]:\n" + "\n---\n".join(snippets)
    except Exception as e:
        return f"[Web search failed: {e}]"

# ── Groq client ───────────────────────────────────────────────────────────────
client = Groq(api_key=settings.GROQ_API_KEY)

# ── Keywords that signal a current-events / live-data question ────────────────
_WEB_SEARCH_PATTERNS = re.compile(
    r'\b(today|tonight|right now|current(ly)?|latest|recent(ly)?|'
    r'news|happening|update|score|weather|price|stock|'
    r'who (is|are|won|leads)|what (is|are) the (latest|current|today)|'
    r'did .* (win|lose|happen)|'
    r'2024|2025|2026)\b',
    re.IGNORECASE
)


def _needs_web_search(text: str) -> bool:
    return bool(_WEB_SEARCH_PATTERNS.search(text))

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
        answer = data.get('answer', '')
        if answer:
            return f"[Web search result]: {answer}"
        snippets = [r.get('content', '')[:300] for r in data.get('results', [])[:3]]
        return "[Web search results]:\n" + "\n---\n".join(snippets)
    except Exception:
        return ''  # silently fall back to LLM knowledge

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are NOVA — an intelligent, friendly AI voice assistant built with Whisper (deep learning STT) and LLaMA via Groq.

CRITICAL LANGUAGE RULE: You MUST ALWAYS respond in English only. No matter what language the user speaks in — your reply must ALWAYS be in English. Never switch to Arabic, Urdu, or any other language under any circumstances.

Your personality:
- Warm, conversational, and concise (voice-first: keep replies under 3 sentences unless asked for detail)
- You can discuss anything: programming, AI, science, sports, news, history, general knowledge
- If asked who built you: "I was built by a DUET CS student using Whisper, Groq LLaMA, and Django"
- Your knowledge goes up to early 2024. For anything after that, rely on the [Web search result] if provided.

Rules:
- ALWAYS reply in English — this is non-negotiable
- Keep responses SHORT — they will be spoken aloud
- No markdown, no bullet points (this is voice output)
- If a [Web search result] is included in the message, use it to answer accurately
- Be encouraging and helpful
"""


# ── Session-based conversation history ───────────────────────────────────────
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

    # ── Web search injection ──────────────────────────────────────────────────
    web_context = ''
    used_web_search = False
    if _tavily and _needs_web_search(user_message):
        web_context = _web_search(user_message)
        used_web_search = bool(web_context)

    # Build message payload
    history = _get_history(request)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)

    # Inject web context + English reminder into the user turn
    augmented = user_message
    if web_context:
        augmented = f"{user_message}\n\n{web_context}"
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
            'web_search_used': used_web_search,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def clear_history(request):
    request.session['chat_history'] = []
    request.session.modified = True
    return JsonResponse({'status': 'cleared'})