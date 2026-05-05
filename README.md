# 🎙 NOVA — AI Voice Agent
 
> **Django + Groq Whisper + LLaMA 3.3 70B + Tavily Web Search + Web Speech API**
> Built for DUET CS Artificial Intelligence Course Project — 2025
 
---
 
## 📐 Architecture
 
```
Browser Mic (MediaRecorder)
        ↓  audio blob (webm)
Django View → Groq Whisper Large v3     ← Deep Learning STT
        ↓  transcript (English-forced)
Django View → Tavily Web Search API     ← Live data (if needed)
        ↓  search context injected into prompt
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
- 🔊 **Browser TTS** — English voice with 8-level priority voice picker
- 💬 **Session Memory** — remembers last 10 turns of conversation
- ⌨️ **Text Input Fallback** — type instead of speaking
- 🌙 **Dark / Light Theme Toggle** — persisted in localStorage
- ℹ️ **Slide-out Info Panel** — tech stack, deep learning info, live session stats
- 📊 **Live Status Indicator** — animated dot showing Idle / Recording / Thinking / Speaking
- 📱 **Mobile Responsive** — panel collapses correctly on small screens
- ⌨️ **Keyboard Shortcut** — press `Escape` to close the info panel
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
# Copy the example env file and rename it to .env
cp .env.example .env        # Mac/Linux
copy .env.example .env      # Windows CMD
```
 
Open `.env` and fill in your keys:
```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxxxxx
DJANGO_SECRET_KEY=any-random-string-here
```
 
| Key | Where to get it | Cost |
|---|---|---|
| `GROQ_API_KEY` | https://console.groq.com | Free |
| `TAVILY_API_KEY` | https://app.tavily.com | Free tier available |
 
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
│   ├── settings.py                ← GROQ_API_KEY, TAVILY_API_KEY, middleware
│   ├── urls.py
│   └── wsgi.py
│
└── agent/                         ← Main Django app
    ├── views.py                   ← All backend logic (STT + web search + LLM)
    ├── urls.py                    ← 4 API endpoints
    ├── apps.py
    ├── templates/agent/
    │   └── index.html             ← Main UI (topbar, transcript feed, info panel)
    └── static/agent/
        ├── css/main.css           ← Dark/light theme, animations, responsive layout
        └── js/voice.js            ← Recording, API calls, theme toggle, info panel
```
 
---
 
## 🔌 API Endpoints
 
| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Main voice agent UI |
| `/api/transcribe/` | POST | Audio blob → Groq Whisper → English transcript |
| `/api/chat/` | POST | Text → (optional Tavily search) → LLaMA reply |
| `/api/clear/` | POST | Clear conversation session history |
 
---
 
## 🛠 Tech Stack
 
| Component | Technology | Notes |
|---|---|---|
| Web Framework | Django 4.2+ | Backend, sessions, routing, templates |
| Speech-to-Text | Groq Whisper Large v3 | Deep Learning STT — 1.5B param Transformer |
| Language Model | Groq LLaMA 3.3 70B Versatile | Free API, handles tool-use well |
| Web Search | Tavily REST API | Live news, scores, prices, current events |
| Audio Capture | MediaRecorder API | Browser — records WebM blob |
| Text-to-Speech | Web SpeechSynthesis API | Browser built-in, 8-level English voice picker |
| Session Memory | Django Sessions + SQLite | Stores last 10 conversation turns |
| Env Config | python-dotenv | Loads keys from .env securely |
| Fonts | Manrope + Martian Mono | Google Fonts — loaded via CDN |
 
---
 
## 🎨 UI Overview
 
NOVA's interface is built entirely with vanilla HTML, CSS, and JavaScript inside Django templates.
 
**Topbar** contains the NOVA brand mark, active model chip, turn counter, status pill, and three icon buttons — theme toggle, info panel, and new session.
 
**Transcript Feed** is the scrollable conversation area. Messages animate in from below. A typing indicator (three bouncing dots) appears while NOVA is thinking.
 
**Controls** sit at the bottom — a status bar with an animated indicator dot, the large push-to-talk mic button with ripple rings, and a text input fallback.
 
**Info Panel** slides in from the right and shows the full tech stack, the deep learning core description, and live session stats (turns + status). It can be closed by clicking the X button, clicking the backdrop, or pressing `Escape`.
 
**Theme** defaults to dark and can be toggled to light mode. The preference is saved in `localStorage` and restored on next visit.
 
---
 
## 🌐 Web Search Behaviour
 
NOVA automatically detects when a question needs live data using keyword patterns
(`today`, `latest`, `news`, `price`, `2025`, `score`, `weather`, etc.) and calls
the Tavily API to fetch current results before answering. The web context is injected
into the LLaMA prompt but is **not** saved to session history to keep memory clean.
 
The response JSON includes `"web_search_used": true/false` for debugging.
 
---
 
## 🔊 English TTS Voice Priority
 
The voice picker in `voice.js` follows an 8-level priority chain:
 
1. Google US English
2. Microsoft Aria Online Natural (en-US)
3. Samantha (macOS)
4. Any `en-US` Google voice
5. Any `en-US` online (non-local) voice
6. Any `en-US` voice
7. Any `en-GB` voice
8. Any English voice
The selected voice name is logged in the browser console on load:
```
🔊 TTS voice: Google US English (en-US)
```
 
---
 
## 🎓 Course Submission Notes
 
- **Deep Learning model:** OpenAI Whisper Large v3 (Transformer encoder-decoder)
- **Training data:** 680,000 hours of multilingual speech
- **Parameters:** 1.5 Billion
- **Inference:** Groq LPU — Language Processing Unit (custom AI silicon)
- **Pipeline:** Mic → Whisper STT → (Tavily search) → LLaMA 3.3 70B → TTS
---
 
## ❓ Troubleshooting
 
| Problem | Solution |
|---|---|
| `GROQ_API_KEY not configured` | Check `.env` exists in `voice_agent/` root (not `.env.example`) |
| Mic not working | Use Chrome or Edge — Firefox may not support `audio/webm` |
| No speech detected | Hold button for at least 2 seconds and speak clearly |
| Arabic / wrong language TTS | Open browser console — check which voice was selected |
| Theme not saving | Make sure localStorage is not blocked in your browser |
| Info panel not opening | Check browser console for JS errors |
| Port 8000 in use | Run: `python manage.py runserver 8080` |
| pydantic install error | Run: `pip install --only-binary=:all: pydantic pydantic-core` first |
| `No module named django` | Make sure venv is activated before running manage.py |
| `manage.py not found` | You're in the wrong folder — run `cd voice_agent` first |
 
---
 
## 📦 Dependencies
 
```
django>=4.2
groq>=0.9.0
python-dotenv>=1.0.0
requests>=2.31.0
```
 
> **Note:** `pydantic` and `pydantic-core` must be installed as pre-built binaries
> using `--only-binary=:all:` to avoid the Rust compiler requirement on Windows.
 
---
 
## 👥 Team
 
| Name | Roll no  | Roll  |
|---|---|---|
| Muhammad Sohaib Hafeez | 24F-CS-085 | Backend |
| Maham Siddiqui  | 24F-CS-070 | Backend |
| Mubahsir Awan | 24F-CS-074 | Frontend |
 
---
 
## 📄 License
 
Built for academic purposes — DUET CS AI Course 2025.
