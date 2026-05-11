# 🎙 NOVA — AI Voice Agent
 
> **Django + Groq Whisper + LLaMA 3.3 70B + Tavily Web Search + ACRCloud Song Recognition + Web Speech API**
> Built for DUET CS Artificial Intelligence Course Project — 2025
 
---
 
## 📐 Architecture
 
```
Browser Mic (MediaRecorder @ 128kbps)
        ↓  audio blob (webm)
Django View ──┬──► ACRCloud Audio Fingerprinting  ← Song Recognition (melody-based)
              └──► Groq Whisper Large v3           ← Deep Learning STT
                        ↓  transcript + song_detected
Django View ──┬──► Genius API                      ← Lyrics search (text-based fallback)
              ├──► Tavily Web Search API            ← Live current events
              └──► Groq LLaMA 3.3 70B              ← Free, ultra-fast LLM
                        ↓  English-only reply
Browser SpeechSynthesis                            ← Built-in TTS, English voice
```
 
---
 
## 🧠 Deep Learning Component
 
**Whisper Large v3** — OpenAI's Transformer encoder-decoder trained on **680,000 hours**
of multilingual speech. Runs via Groq's LPU hardware for near-zero latency.
This satisfies the Deep Learning requirement of the AI course project.
 
---
 
## ✨ Features
 
- 🎙 **Push-to-Talk** voice input via browser MediaRecorder API (128kbps for quality)
- 🧠 **Whisper Large v3** Deep Learning speech-to-text (English-forced transcription)
- ⚡ **Groq LLaMA 3.3 70B** — free, ultra-fast LLM responses
- 🌐 **Tavily Web Search** — live current affairs, news, scores, prices
- 🎵 **ACRCloud Audio Fingerprinting** — identify songs by melody, hum, or background music
- 🎤 **Genius API** — text-based song/lyrics search fallback
- 🔊 **Browser TTS** — English voice with 8-level priority voice picker
- 💬 **Session Memory** — remembers last 10 turns of conversation
- ⌨️ **Text Input Fallback** — type instead of speaking
- 🌙 **Dark / Light Theme Toggle** — persisted in localStorage
- ℹ️ **Slide-out Info Panel** — tech stack, deep learning info, live session stats
- 📱 **Mobile Responsive** — works on all screen sizes
- 🎯 **Zero-Shot Song Detection** — hold mic near music, say nothing, NOVA identifies it
---
 
## ⚡ Quick Start
 
### 1. Extract / clone the project
```bash
cd voice_agent/
```
 
### 2. Create virtual environment
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac/Linux
```
 
### 3. Install dependencies
```bash
pip install --only-binary=:all: pydantic pydantic-core
pip install -r requirements.txt
```
 
> No extra packages needed for ACRCloud — it uses Python's built-in
> `hashlib`, `hmac`, and `base64` libraries plus `requests` (already installed).
 
### 4. Set up API keys
```bash
# Windows CMD
copy .env.example .env
 
# Mac/Linux
cp .env.example .env
```
 
Open `.env` and fill in your keys:
```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxxxxx
GENIUS_API_KEY=your_genius_token_here
ACR_HOST=identify-eu-west-1.acrcloud.com
ACR_ACCESS_KEY=your_acr_access_key
ACR_ACCESS_SECRET=your_acr_access_secret
DJANGO_SECRET_KEY=any-random-string-here
```
 
| Key | Where to get it | Cost |
|---|---|---|
| `GROQ_API_KEY` | https://console.groq.com | Free |
| `TAVILY_API_KEY` | https://app.tavily.com | Free tier |
| `GENIUS_API_KEY` | https://genius.com/api-clients | Free |
| `ACR_HOST` + `ACR_ACCESS_KEY` + `ACR_ACCESS_SECRET` | https://console.acrcloud.com | Free trial |
 
### 5. Add ACRCloud keys to `settings.py`
```python
ACR_HOST          = os.getenv('ACR_HOST', '')
ACR_ACCESS_KEY    = os.getenv('ACR_ACCESS_KEY', '')
ACR_ACCESS_SECRET = os.getenv('ACR_ACCESS_SECRET', '')
```
 
### 6. Run migrations (first time only)
```bash
python manage.py migrate
```
 
### 7. Start the server
```bash
python manage.py runserver
```
 
### 8. Open in browser
```
http://127.0.0.1:8000
```
 
Allow microphone access → **Hold the mic button → Speak → Release**
 
> **Stop the server:** Press `Ctrl + C` in the terminal
 
---
 
## 🗂 Project Structure
 
```
voice_agent/
├── manage.py
├── requirements.txt
├── .env                           ← your secrets (never commit this)
├── .env.example                   ← template for .env
├── .gitignore
├── README.md
├── db.sqlite3                     ← auto-created by migrate
│
├── voice_agent_project/           ← Django project config
│   ├── settings.py                ← all API keys, middleware, database
│   ├── urls.py
│   └── wsgi.py
│
└── agent/                         ← Main Django app
    ├── views.py                   ← All backend logic (STT + ACRCloud + search + LLM)
    ├── urls.py                    ← 4 API endpoints
    ├── apps.py
    ├── templates/agent/
    │   └── index.html             ← Main UI (topbar, transcript feed, info panel)
    └── static/agent/
        ├── css/main.css           ← Dark/light theme, animations, responsive layout
        └── js/voice.js            ← Recording, ACRCloud context, API calls, TTS
```
 
---
 
## 🔌 API Endpoints
 
| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Main voice agent UI |
| `/api/transcribe/` | POST | Audio blob → ACRCloud + Whisper → transcript + song_detected |
| `/api/chat/` | POST | Text + song_detected → (Genius / Tavily / LLaMA) → reply |
| `/api/clear/` | POST | Clear conversation session history |
 
---
 
## 🛠 Tech Stack
 
| Component | Technology | Notes |
|---|---|---|
| Web Framework | Django 4.2+ | Backend, sessions, routing, templates |
| Speech-to-Text | Groq Whisper Large v3 | Deep Learning STT — 1.5B param Transformer |
| Language Model | Groq LLaMA 3.3 70B Versatile | Free API, ultra-fast responses |
| Song Recognition | ACRCloud Audio Fingerprinting | Melody-based — identifies any song in 2-3 seconds |
| Lyrics Search | Genius REST API | Text-based song search fallback |
| Web Search | Tavily REST API | Live news, scores, prices, current events |
| Audio Capture | MediaRecorder API | Browser — records WebM blob at 128kbps |
| Text-to-Speech | Web SpeechSynthesis API | Browser built-in, 8-level English voice picker |
| Session Memory | Django Sessions + SQLite | Stores last 10 conversation turns |
| Env Config | python-dotenv | Loads keys from .env securely |
| Fonts | Manrope + Martian Mono | Google Fonts CDN |
 
---
 
## 🌐 Web Search Behaviour
 
NOVA automatically detects when a question needs live data using keyword patterns
(`today`, `latest`, `news`, `price`, `2025`, `score`, `weather`, etc.) and calls
the Tavily API to fetch current results before answering. The web context is injected
into the LLaMA prompt but is **not** saved to session history to keep memory clean.
 
---
 
## 🎵 Song Recognition Behaviour
 
NOVA uses a **two-layer song recognition system**:
 
**Layer 1 — ACRCloud Audio Fingerprinting (Primary)**
Every audio recording is simultaneously sent to ACRCloud for melody-based recognition.
This works even if you say nothing — just hold the mic near any music for 5 seconds.
 
**Layer 2 — Genius Lyrics Search (Fallback)**
If no song is detected by audio but the user says lyrics-related keywords
(`who sings`, `what song`, `goes like`, etc.), Genius API is searched by text.
 
**Priority order in `views.py`:**
1. ACRCloud song result (if audio matched)
2. Genius lyrics search (if lyrics keywords in text)
3. Tavily web search (if current events keywords in text)
4. LLaMA answers from its own knowledge
**Example usage:**
- Hold mic near speaker playing any song → NOVA identifies it automatically
- Say *"What song goes like we will rock you"* → Genius finds it by lyrics
- Say *"Who won the Champions League 2025"* → Tavily fetches live result
**Zero-Shot Mode:**
Hold mic near music, say nothing, release → NOVA replies:
*"I can hear 'Blinding Lights' by The Weeknd! Want to know more about this song?"*
 
---
 
## 🔊 English TTS Voice Priority
 
The voice picker in `voice.js` follows an 8-level priority chain:
 
1. Google US English
2. Microsoft Aria Online Natural (en-US)
3. Samantha (macOS)
4. Any `en-US` Google voice
5. Any `en-US` online voice
6. Any `en-US` voice
7. Any `en-GB` voice
8. Any English voice
Selected voice is logged in browser console on load:
```
🔊 TTS voice: Google US English (en-US)
```
 
---
 
## 🎓 Course Submission Notes
 
- **Deep Learning model:** OpenAI Whisper Large v3 (Transformer encoder-decoder)
- **Training data:** 680,000 hours of multilingual speech
- **Parameters:** 1.5 Billion
- **Inference:** Groq LPU — Language Processing Unit (custom AI silicon)
- **Pipeline:** Mic → ACRCloud Fingerprint + Whisper STT → (Genius / Tavily) → LLaMA 3.3 70B → TTS
- **Architecture type:** Hybrid Multi-Model Pipeline
---
 
## ❓ Troubleshooting
 
| Problem | Solution |
|---|---|
| `GROQ_API_KEY not configured` | Check `.env` exists in `voice_agent/` root |
| Mic not working | Use Chrome or Edge — Firefox may not support `audio/webm` |
| No speech detected | Hold button for at least 2 seconds and speak clearly |
| Song not recognized | Hold mic closer to speaker for at least 5 seconds |
| Arabic / wrong language TTS | Check browser console for selected voice name |
| ACRCloud not working | Check all 3 ACR keys in `.env` — HOST, ACCESS_KEY, ACCESS_SECRET |
| Port 8000 in use | Run: `python manage.py runserver 8080` |
| pydantic install error | Run: `pip install --only-binary=:all: pydantic pydantic-core` first |
| `No module named django` | Activate venv: `.venv\Scripts\activate` |
| `manage.py not found` | Wrong folder — run `cd voice_agent` first |
 
---
 
## 📦 Dependencies
 
```
django>=4.2
groq>=0.9.0
python-dotenv>=1.0.0
requests>=2.31.0
```
 
> **ACRCloud** requires no extra package — uses Python built-ins:
> `hashlib`, `hmac`, `base64`, `time` (all standard library).
>
> **Note:** `pydantic` and `pydantic-core` must be installed as pre-built binaries
> using `--only-binary=:all:` to avoid the Rust compiler requirement on Windows.
 
---
 
## 👥 Team
 
| Name | Role |
|---|---|
| Muhammad Sohaib Hafeez (Roll: 24F-CS-085) | Backend — Django, Groq, Tavily, ACRCloud, Genius, views.py |
| Maham Siddiqui (Roll: 70) | Frontend — HTML, CSS, JS, theme toggle, info panel, UI redesign |
| Mubashir Awan Hafeez (Roll: 24F-CS-074) | Backend — Django, views.py & Frontend — HTML, CSS, JS|
 
---
 
## 📄 License
 
Built for academic purposes — DUET CS AI Course 2025.
