/**
 * NOVA Voice Agent — Frontend JS
 * Flow: Hold mic → record audio → POST to /api/transcribe/ (Groq Whisper)
 *       → POST to /api/chat/ (Groq LLaMA) → speak reply (Web Speech API)
 */

// ── DOM refs ─────────────────────────────────────────────────────────────────
const micBtn       = document.getElementById('micBtn');
const sendBtn      = document.getElementById('sendBtn');
const textInput    = document.getElementById('textInput');
const statusText   = document.getElementById('statusText');
const audioBars    = document.getElementById('audioBars');
const transcriptFeed = document.getElementById('transcriptFeed');
const turnCount    = document.getElementById('turn-count');
const statusDot    = document.getElementById('status-dot');
const clearBtn     = document.getElementById('clearBtn');
const csrfToken    = document.getElementById('csrfToken').value;

// ── State ─────────────────────────────────────────────────────────────────────
let mediaRecorder  = null;
let audioChunks    = [];
let isRecording    = false;
let isBusy         = false;
let turns          = 0;
let currentUtterance = null;

// ── Helpers ───────────────────────────────────────────────────────────────────

function setStatus(msg, type = 'idle') {
  statusText.textContent = msg;
  statusDot.textContent  = { idle: 'Idle', recording: 'Recording', thinking: 'Thinking', speaking: 'Speaking' }[type] || type;
  statusDot.className = `session-val status-${type}`;
}

function showBars(active) {
  audioBars.classList.toggle('active', active);
}

function scrollFeed() {
  transcriptFeed.scrollTop = transcriptFeed.scrollHeight;
}

function clearWelcome() {
  const welcome = transcriptFeed.querySelector('.welcome-msg');
  if (welcome) welcome.remove();
}

function addMessage(role, text, extra_class = '') {
  clearWelcome();
  const div = document.createElement('div');
  div.className = `msg ${role} ${extra_class}`.trim();

  const meta = document.createElement('div');
  meta.className = 'msg-meta';
  meta.textContent = role === 'user' ? 'You' : 'NOVA';

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.textContent = text;

  div.appendChild(meta);
  div.appendChild(bubble);
  transcriptFeed.appendChild(div);
  scrollFeed();
  return div;
}

function addTypingIndicator() {
  clearWelcome();
  const div = document.createElement('div');
  div.className = 'msg nova msg-typing';
  div.innerHTML = `
    <div class="msg-meta">NOVA</div>
    <div class="msg-bubble">
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
    </div>`;
  transcriptFeed.appendChild(div);
  scrollFeed();
  return div;
}

function setBusy(busy) {
  isBusy = busy;
  micBtn.disabled = busy;
  sendBtn.disabled = busy;
  textInput.disabled = busy;
}

// ── TTS via Web Speech API ────────────────────────────────────────────────────

function getEnglishVoice() {
  const voices = window.speechSynthesis.getVoices();
  // Priority chain: best quality English voices first
  return (
    voices.find(v => v.name === 'Google US English')                          ||
    voices.find(v => v.name === 'Microsoft Aria Online (Natural) - English (United States)') ||
    voices.find(v => v.name === 'Samantha')                                   ||
    voices.find(v => v.lang === 'en-US' && v.name.toLowerCase().includes('google')) ||
    voices.find(v => v.lang === 'en-US' && v.localService === false)          ||
    voices.find(v => v.lang === 'en-US')                                      ||
    voices.find(v => v.lang === 'en-GB')                                      ||
    voices.find(v => v.lang.startsWith('en'))                                 ||
    null
  );
}

function speak(text) {
  if (!window.speechSynthesis) return Promise.resolve();
  return new Promise((resolve) => {
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.rate  = 1.0;
    utter.pitch = 1.0;
    utter.lang  = 'en-US';   // Always set lang — prevents browser falling back to system locale

    const englishVoice = getEnglishVoice();
    if (englishVoice) {
      utter.voice = englishVoice;
    }

    utter.onend  = resolve;
    utter.onerror = resolve;
    currentUtterance = utter;
    window.speechSynthesis.speak(utter);
    setStatus('Speaking response…', 'speaking');
  });
}

// ── API calls ─────────────────────────────────────────────────────────────────

async function transcribeAudio(blob) {
  const formData = new FormData();
  formData.append('audio', blob, 'recording.webm');

  const res = await fetch('/api/transcribe/', {
    method: 'POST',
    headers: { 'X-CSRFToken': csrfToken },
    body: formData,
  });
  const data = await res.json();
  if (!res.ok || data.error) throw new Error(data.error || 'Transcription failed');
  return data.transcript;
}

async function sendChat(message) {
  const res = await fetch('/api/chat/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken,
    },
    body: JSON.stringify({ message }),
  });
  const data = await res.json();
  if (!res.ok || data.error) throw new Error(data.error || 'Chat failed');
  return data;
}

// ── Core pipeline ─────────────────────────────────────────────────────────────

async function runPipeline(userText) {
  try {
    setBusy(true);

    // 1. Show user message
    addMessage('user', userText);
    turns++;
    turnCount.textContent = turns;

    // 2. Show typing indicator + call LLM
    setStatus('Thinking…', 'thinking');
    const typingEl = addTypingIndicator();
    const chatData = await sendChat(userText);
    typingEl.remove();

    // 3. Show NOVA reply
    const reply = chatData.reply;
    addMessage('nova', reply);

    // 4. Speak
    await speak(reply);

    setStatus('Ready — press and hold to record', 'idle');
  } catch (err) {
    const errEl = addMessage('nova', `⚠ Error: ${err.message}`, 'msg-error');
    setStatus('Error — try again', 'idle');
    console.error(err);
  } finally {
    setBusy(false);
  }
}

// ── Microphone recording ──────────────────────────────────────────────────────

async function startRecording() {
  if (isRecording || isBusy) return;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      const blob = new Blob(audioChunks, { type: 'audio/webm' });

      if (blob.size < 1000) {
        setStatus('Too short — hold longer', 'idle');
        showBars(false);
        micBtn.classList.remove('recording');
        return;
      }

      try {
        setBusy(true);
        setStatus('Transcribing with Whisper…', 'thinking');
        const transcript = await transcribeAudio(blob);

        if (!transcript || transcript.trim().length === 0) {
          setStatus('No speech detected — try again', 'idle');
          setBusy(false);
          return;
        }

        await runPipeline(transcript);
      } catch (err) {
        addMessage('nova', `⚠ Transcription error: ${err.message}`, 'msg-error');
        setStatus('Error — try again', 'idle');
        setBusy(false);
      }

      showBars(false);
      micBtn.classList.remove('recording');
    };

    mediaRecorder.start(100);
    isRecording = true;
    micBtn.classList.add('recording');
    showBars(true);
    setStatus('Recording… release to send', 'recording');

  } catch (err) {
    if (err.name === 'NotAllowedError') {
      setStatus('Microphone permission denied', 'idle');
      addMessage('nova', '⚠ Please allow microphone access in your browser.', 'msg-error');
    } else {
      setStatus('Mic error: ' + err.message, 'idle');
    }
  }
}

function stopRecording() {
  if (!isRecording || !mediaRecorder) return;
  isRecording = false;
  mediaRecorder.stop();
  setStatus('Processing audio…', 'thinking');
}

// ── Event listeners ───────────────────────────────────────────────────────────

// Push-to-talk — mouse
micBtn.addEventListener('mousedown',  (e) => { e.preventDefault(); startRecording(); });
micBtn.addEventListener('mouseup',    stopRecording);
micBtn.addEventListener('mouseleave', stopRecording);

// Push-to-talk — touch (mobile)
micBtn.addEventListener('touchstart', (e) => { e.preventDefault(); startRecording(); }, { passive: false });
micBtn.addEventListener('touchend',   (e) => { e.preventDefault(); stopRecording(); },  { passive: false });

// Text input — send on Enter
textInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !isBusy) {
    const msg = textInput.value.trim();
    if (msg) { textInput.value = ''; runPipeline(msg); }
  }
});

sendBtn.addEventListener('click', () => {
  const msg = textInput.value.trim();
  if (msg && !isBusy) { textInput.value = ''; runPipeline(msg); }
});

// Clear session
clearBtn.addEventListener('click', async () => {
  await fetch('/api/clear/', {
    method: 'POST',
    headers: { 'X-CSRFToken': csrfToken },
  });
  transcriptFeed.innerHTML = `
    <div class="welcome-msg">
      <div class="welcome-icon">🎙</div>
      <div class="welcome-text">Session cleared. Hold the mic button and speak.</div>
    </div>`;
  turns = 0;
  turnCount.textContent = 0;
  setStatus('Ready — press and hold to record', 'idle');
  window.speechSynthesis && window.speechSynthesis.cancel();
});

// Pre-load voices (Chrome loads them async — must wait for voiceschanged)
if (window.speechSynthesis) {
  window.speechSynthesis.getVoices(); // triggers load in Firefox/Safari
  window.speechSynthesis.addEventListener('voiceschanged', () => {
    const v = getEnglishVoice();
    console.log('🔊 TTS voice selected:', v ? `${v.name} (${v.lang})` : 'browser default (en-US forced)');
  });
}

// Initial status
setStatus('Ready — press and hold to record', 'idle');
console.log('🎙 NOVA Voice Agent loaded — Whisper STT + Groq LLaMA + Django');