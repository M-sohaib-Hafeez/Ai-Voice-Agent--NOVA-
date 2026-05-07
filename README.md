# 🎙 NOVA — AI Voice Agent
 
> **Django + Groq Whisper + LLaMA 3.3 70B + Tavily Web Search + Genius Song Recognition + Web Speech API**
> Built for DUET CS Artificial Intelligence Course Project — 2025
 
---
 
## 📐 Architecture
 
```
Browser Mic (MediaRecorder)
        ↓  audio blob (webm)
Django View → Groq Whisper Large v3     ← Deep Learning STT
        ↓  transcript (English-forced)
Django View → Genius API                ← Song recognition (if lyrics detected)
        ↓  OR
Django View → Tavily Web Search API     ← Live data (if current events detected)
        ↓  context injected into prompt
Django View → Groq LLaMA 3.3 70B       ← Free, ultra-fast LLM
        ↓  English-only reply
Browser SpeechSynthesis                 ← Built-in TTS, English voice
```
 
---
 
## 🧠 Deep Learning Component
 
**Whisper Large v3** — OpenAI's Transformer encoder-decoder trained on **680,000 hours**
of multilingual speech. Runs via Groq's LPU hardware for near-zero latency.
This satisfies the Deep Learning requirement of the AI course project.
 
---
 
## ✨ Features
 
- 🎙 **Push-to-Talk** voice input via browser MediaRecorder API
- 🧠 **Whisper Large v3** Deep Learning speech-to-text (English-forced transcription)
- ⚡ **Groq LLaMA 3.3 70B** — free, ultra-fast LLM responses
- 🌐 **Tavily Web Search** — live current affairs, news, scores, prices
- 🎵 **Genius Song Recognition** — identify songs from lyrics snippets
- 🔊 **Browser TTS** — English voice with 8-level priority voice picker
- 💬 **Session Memory** — remembers last 10 turns of conversation
- ⌨️ **Text Input Fallback** — type instead of speaking
- 🌙 **Dark / Light Theme Toggle** — persisted in localStorage
- ℹ️ **Slide-out Info Panel** — tech stack, deep learning info, live session stats
- 📱 **Mobile Responsive** — works on all screen sizes
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
DJANGO_SECRET_KEY=any-random-string-here
```
 
| Key | Where to get it | Cost |
|---|---|---|
| `GROQ_API_KEY` | https://console.groq.com | Free |
| `TAVILY_API_KEY` | https://app.tavily.com | Free tier available |
| `GENIUS_API_KEY` | https://genius.com/api-clients | Free |
 
### 5. Run migrations (first time only)
```bash
python manage.py migrate
```
 
### 6. Start the server
```bash
python manage.py runserver
```
 
### 7. Open in browser
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
    ├── views.py                   ← All backend logic (STT + search + LLM)
    ├── urls.py                    ← 4 API endpoints
    ├── apps.py
    ├── templates/agent/
    │   └── index.html             ← Main UI (topbar, transcript feed, info panel)
    └── static/agent/
        ├── css/main.css           ← Dark/light theme, animations, responsive layout
        └── js/voice.js            ← Recording, API calls, TTS, theme toggle
```
 
---
 
## 🔌 API Endpoints
 
| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Main voice agent UI |
| `/api/transcribe/` | POST | Audio blob → Groq Whisper → English transcript |
| `/api/chat/` | POST | Text → (Genius / Tavily / LLaMA) → reply |
| `/api/clear/` | POST | Clear conversation session history |
 
---
 
## 🛠 Tech Stack
 
| Component | Technology | Notes |
|---|---|---|
| Web Framework | Django 4.2+ | Backend, sessions, routing, templates |
| Speech-to-Text | Groq Whisper Large v3 | Deep Learning STT — 1.5B param Transformer |
| Language Model | Groq LLaMA 3.3 70B Versatile | Free API, ultra-fast responses |
| Web Search | Tavily REST API | Live news, scores, prices, current events |
| Song Recognition | Genius REST API | Identify songs from lyrics snippets |
| Audio Capture | MediaRecorder API | Browser — records WebM blob |
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
 
NOVA detects lyrics-related keywords (`lyrics`, `who sings`, `what song`, `goes like`,
`sounds like`, `who sang`, etc.) and calls the Genius API to search for the matching song.
It returns the song title and artist name clearly in the reply.
 
**Example queries that trigger song search:**
- *"What song has the lyrics never gonna give you up"*
- *"Who sings blinding lights"*
- *"What song goes like we will rock you"*
**Priority order in views.py:**
1. Genius song search (if lyrics keywords detected)
2. Tavily web search (if current events keywords detected)
3. LLaMA answers from its own knowledge (everything else)
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
Selected voice is logged in browser console on load.
 
---
 
## 🎓 Course Submission Notes
 
- **Deep Learning model:** OpenAI Whisper Large v3 (Transformer encoder-decoder)
- **Training data:** 680,000 hours of multilingual speech
- **Parameters:** 1.5 Billion
- **Inference:** Groq LPU — Language Processing Unit (custom AI silicon)
- **Pipeline:** Mic → Whisper STT → (Genius / Tavily) → LLaMA 3.3 70B → TTS
---
 
## ❓ Troubleshooting
 
| Problem | Solution |
|---|---|
| `GROQ_API_KEY not configured` | Check `.env` exists in project root (not `.env.example`) |
| Mic not working | Use Chrome or Edge — Firefox may not support `audio/webm` |
| No speech detected | Hold button for at least 2 seconds and speak clearly |
| Arabic / wrong language TTS | Check browser console for selected voice name |
| Song not recognized | Try saying "what song has the lyrics..." clearly |
| Port 8000 in use | Run: `python manage.py runserver 8080` |
| pydantic install error | Run: `pip install --only-binary=:all: pydantic pydantic-core` first |
| `No module named django` | Activate venv first: `.venv\Scripts\activate` |
| `manage.py not found` | Wrong folder — run `cd voice_agent` first |
 
---
 
## 📦 Dependencies
 
```
django>=4.2
groq>=0.9.0
python-dotenv>=1.0.0
requests>=2.31.0
```
 
> Note: `pydantic` and `pydantic-core` are installed as pre-built binaries
> (`--only-binary=:all:`) to avoid the Rust compiler requirement on Windows.
 
---
 
## 👥 Team
 
| Name | Role |
|---|---|
| Muhammad Sohaib Hafeez (Roll: 24F-CS-085) | Backend — Django, Groq API, Tavily, Genius, views.py |
| Maham Siddiqui (Roll: 70) | Frontend — HTML, CSS, JS, theme toggle, info panel |
 
---
 
## 📄 License
 
Built for academic purposes — DUET CS AI Course 2025.
