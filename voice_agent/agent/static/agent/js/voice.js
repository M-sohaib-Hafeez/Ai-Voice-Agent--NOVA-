const micBtn          = document.getElementById('micBtn');
const sendBtn         = document.getElementById('sendBtn');
const textInput       = document.getElementById('textInput');
const statusText      = document.getElementById('statusText');
const statusIndicator = document.getElementById('statusIndicator');
const audioBars       = document.getElementById('audioBars');
const transcriptFeed  = document.getElementById('transcriptFeed');
const turnCount       = document.getElementById('turn-count');
const statusDot       = document.getElementById('status-dot');
const clearBtn        = document.getElementById('clearBtn');
const csrfToken       = document.getElementById('csrfToken').value;

const themeBtn        = document.getElementById('themeBtn');
const infoBtn         = document.getElementById('infoBtn');
const infoPanel       = document.getElementById('infoPanel');
const panelBackdrop   = document.getElementById('panelBackdrop');
const panelClose      = document.getElementById('panelClose');
const panelClearBtn   = document.getElementById('panelClearBtn');

const panelTurns      = document.getElementById('panel-turns');
const panelStatus     = document.getElementById('panel-status');

const mainEl          = document.querySelector('.main');

let mediaRecorder      = null;
let audioChunks        = [];
let isRecording        = false;
let isBusy             = false;
let turns              = 0;
let currentUtterance   = null;
let panelOpen          = false;

// ── Stores ACRCloud song result from transcribe response ──────────────────────
// Cleared after each chat turn to prevent "memory leak"
let detectedSongContext = null;


// ── Theme ─────────────────────────────────────────────────────────────────────
function getTheme() {
  return localStorage.getItem('nova-theme') || 'dark';
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('nova-theme', theme);
}

function toggleTheme() {
  applyTheme(getTheme() === 'dark' ? 'light' : 'dark');
}

applyTheme(getTheme());


// ── Info panel ────────────────────────────────────────────────────────────────
function openPanel() {
  panelOpen = true;
  infoPanel.classList.add('open');
  infoPanel.setAttribute('aria-hidden', 'false');
  panelBackdrop.classList.add('open');
  infoBtn.classList.add('active');
  if (window.innerWidth > 600) mainEl.classList.add('panel-open');
}

function closePanel() {
  panelOpen = false;
  infoPanel.classList.remove('open');
  infoPanel.setAttribute('aria-hidden', 'true');
  panelBackdrop.classList.remove('open');
  infoBtn.classList.remove('active');
  mainEl.classList.remove('panel-open');
}

function togglePanel() {
  panelOpen ? closePanel() : openPanel();
}


// ── Status helpers ────────────────────────────────────────────────────────────
const STATUS_LABELS = {
  idle:      'Idle',
  recording: 'Recording',
  thinking:  'Thinking',
  speaking:  'Speaking',
};

function setStatus(msg, type = 'idle') {
  statusText.textContent    = msg;
  const label               = STATUS_LABELS[type] || type;
  statusDot.textContent     = label;
  statusDot.className       = `stat-val status-${type}`;
  statusIndicator.className = `status-indicator ${type !== 'idle' ? type : ''}`;
  if (panelStatus) {
    panelStatus.textContent = label;
    panelStatus.className   = `session-val session-status status-${type}`;
  }
}

function showBars(active) {
  audioBars.classList.toggle('active', active);
}

function scrollFeed() {
  transcriptFeed.scrollTop = transcriptFeed.scrollHeight;
}

function clearWelcome() {
  const w = transcriptFeed.querySelector('.welcome-wrap');
  if (w) w.remove();
}

function updateTurns(n) {
  turns = n;
  turnCount.textContent = n;
  if (panelTurns) panelTurns.textContent = n;
}


// ── Message rendering ─────────────────────────────────────────────────────────
function addMessage(role, text, extraClass = '') {
  clearWelcome();
  const div        = document.createElement('div');
  div.className    = `msg ${role} ${extraClass}`.trim();
  const meta       = document.createElement('div');
  meta.className   = 'msg-meta';
  meta.textContent = role === 'user' ? 'You' : 'NOVA';
  const bubble         = document.createElement('div');
  bubble.className     = 'msg-bubble';
  bubble.textContent   = text;
  div.appendChild(meta);
  div.appendChild(bubble);
  transcriptFeed.appendChild(div);
  scrollFeed();
  return div;
}

function addTypingIndicator() {
  clearWelcome();
  const div     = document.createElement('div');
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

// ── Song detected banner ──────────────────────────────────────────────────────
function addSongBanner(song) {
  clearWelcome();
  const div     = document.createElement('div');
  div.className = 'msg nova';
  const meta       = document.createElement('div');
  meta.className   = 'msg-meta';
  meta.textContent = '🎵 NOVA';
  const bubble       = document.createElement('div');
  bubble.className   = 'msg-bubble msg-song';
  bubble.innerHTML   = `<strong>${song.title}</strong> — ${song.artists}` +
                       (song.album ? `<br><small>${song.album}</small>` : '');
  div.appendChild(meta);
  div.appendChild(bubble);
  transcriptFeed.appendChild(div);
  scrollFeed();
}

function setBusy(busy) {
  isBusy             = busy;
  micBtn.disabled    = busy;
  sendBtn.disabled   = busy;
  textInput.disabled = busy;
}


// ── TTS ───────────────────────────────────────────────────────────────────────
function getEnglishVoice() {
  const voices = window.speechSynthesis.getVoices();
  return (
    voices.find(v => v.name === 'Google US English') ||
    voices.find(v => v.name === 'Microsoft Aria Online (Natural) - English (United States)') ||
    voices.find(v => v.name === 'Samantha') ||
    voices.find(v => v.lang === 'en-US' && v.name.toLowerCase().includes('google')) ||
    voices.find(v => v.lang === 'en-US' && v.localService === false) ||
    voices.find(v => v.lang === 'en-US') ||
    voices.find(v => v.lang === 'en-GB') ||
    voices.find(v => v.lang.startsWith('en')) ||
    null
  );
}

function speak(text) {
  if (!window.speechSynthesis) return Promise.resolve();
  return new Promise((resolve) => {
    window.speechSynthesis.cancel();
    const utter   = new SpeechSynthesisUtterance(text);
    utter.rate    = 1.0;
    utter.pitch   = 1.0;
    utter.lang    = 'en-US';
    const voice   = getEnglishVoice();
    if (voice) utter.voice = voice;
    utter.onend   = resolve;
    utter.onerror = resolve;
    currentUtterance = utter;
    window.speechSynthesis.speak(utter);
    setStatus('Speaking response…', 'speaking');
  });
}


// ── API calls ─────────────────────────────────────────────────────────────────

/**
 * transcribeAudio — sends audio blob to Django /api/transcribe/
 * Returns { transcript, song_detected }
 * song_detected is either null or { title, artists, album, genres }
 * from ACRCloud audio fingerprinting
 */
async function transcribeAudio(blob) {
  const formData = new FormData();
  formData.append('audio', blob, 'recording.webm');

  const res  = await fetch('/api/transcribe/', {
    method:  'POST',
    headers: { 'X-CSRFToken': csrfToken },
    body:    formData,
  });
  const data = await res.json();
  if (!res.ok || data.error) throw new Error(data.error || 'Transcription failed');

  // Store song context globally so runPipeline can pass it to /api/chat/
  detectedSongContext = data.song_detected || null;

  if (detectedSongContext) {
    console.log('🎵 ACRCloud detected:', detectedSongContext);
  }

  return data.transcript;
}

/**
 * sendChat — sends transcript + optional song_detected to Django /api/chat/
 * song_detected is "hitchhiked" along with the message
 */
async function sendChat(message) {
  const payload = {
    message,
    song_detected: detectedSongContext,   // null or ACRCloud result object
  };

  const res  = await fetch('/api/chat/', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
    body:    JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok || data.error) throw new Error(data.error || 'Chat failed');

  // Clear song context after use — prevents "memory leak" across turns
  detectedSongContext = null;

  return data;
}


// ── Main pipeline ─────────────────────────────────────────────────────────────
async function runPipeline(userText) {
  try {
    setBusy(true);

    // Show song banner in UI if ACRCloud detected a song
    if (detectedSongContext) {
      addSongBanner(detectedSongContext);
    }

    addMessage('user', userText);
    updateTurns(turns + 1);

    setStatus('Thinking…', 'thinking');
    const typingEl = addTypingIndicator();
    const chatData = await sendChat(userText);
    typingEl.remove();

    addMessage('nova', chatData.reply);

    // Debug log
    if (chatData.acr_used)        console.log('🎵 ACRCloud used for this reply');
    if (chatData.web_search_used) console.log('🌐 Tavily web search used');
    if (chatData.lyrics_used)     console.log('🎤 Genius lyrics used');

    await speak(chatData.reply);
    setStatus('Ready — press and hold to record', 'idle');

  } catch (err) {
    addMessage('nova', `⚠ Error: ${err.message}`, 'msg-error');
    setStatus('Error — try again', 'idle');
    console.error(err);
  } finally {
    setBusy(false);
  }
}


// ── Recording ─────────────────────────────────────────────────────────────────
async function startRecording() {
  if (isRecording || isBusy) return;
  try {
    // audioBitsPerSecond: 128000 = sweet spot for both Whisper STT and ACRCloud fingerprinting
    const stream  = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks   = [];
    mediaRecorder = new MediaRecorder(stream, {
      mimeType:          'audio/webm',
      audioBitsPerSecond: 128000,
    });

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
        setStatus('Recognising audio…', 'thinking');
        const transcript = await transcribeAudio(blob);

        // Handle case: song detected but no speech
        if ((!transcript || transcript.trim().length === 0) && detectedSongContext) {
          setStatus('Song detected!', 'thinking');
          await runPipeline('What song is this?');
          showBars(false);
          micBtn.classList.remove('recording');
          return;
        }

        if (!transcript || transcript.trim().length === 0) {
          setStatus('No speech detected — try again', 'idle');
          setBusy(false);
          showBars(false);
          micBtn.classList.remove('recording');
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


// ── Clear session ─────────────────────────────────────────────────────────────
async function clearSession() {
  await fetch('/api/clear/', {
    method:  'POST',
    headers: { 'X-CSRFToken': csrfToken },
  });
  transcriptFeed.innerHTML = `
    <div class="welcome-wrap">
      <div class="welcome-inner">
        <div class="welcome-glyph">
          <svg viewBox="0 0 60 60" fill="none">
            <circle cx="30" cy="30" r="28" stroke="currentColor" stroke-width="1.5"
              stroke-dasharray="4 3" opacity="0.3"/>
            <path d="M30 16a6 6 0 0 0-6 6v10a6 6 0 0 0 12 0V22a6 6 0 0 0-6-6z"
              stroke="currentColor" stroke-width="1.8" fill="none"/>
            <path d="M22 30v2a8 8 0 0 0 16 0v-2"
              stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            <line x1="30" y1="40" x2="30" y2="44"
              stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            <line x1="26" y1="44" x2="34" y2="44"
              stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
          </svg>
        </div>
        <p class="welcome-heading">Session cleared</p>
        <p class="welcome-sub">Hold the mic button and speak.<br/>NOVA will transcribe and reply.</p>
      </div>
    </div>`;
  detectedSongContext = null;
  updateTurns(0);
  setStatus('Ready — press and hold to record', 'idle');
  window.speechSynthesis && window.speechSynthesis.cancel();
}


// ── Event listeners ───────────────────────────────────────────────────────────
micBtn.addEventListener('mousedown',  (e) => { e.preventDefault(); startRecording(); });
micBtn.addEventListener('mouseup',    stopRecording);
micBtn.addEventListener('mouseleave', stopRecording);
micBtn.addEventListener('touchstart', (e) => { e.preventDefault(); startRecording(); }, { passive: false });
micBtn.addEventListener('touchend',   (e) => { e.preventDefault(); stopRecording(); },  { passive: false });

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

clearBtn.addEventListener('click', clearSession);
if (panelClearBtn) panelClearBtn.addEventListener('click', () => { clearSession(); closePanel(); });

themeBtn.addEventListener('click', toggleTheme);
infoBtn.addEventListener('click', togglePanel);
panelClose.addEventListener('click', closePanel);
panelBackdrop.addEventListener('click', closePanel);

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && panelOpen) closePanel();
});

window.addEventListener('resize', () => {
  if (panelOpen && window.innerWidth <= 600) mainEl.classList.remove('panel-open');
  else if (panelOpen) mainEl.classList.add('panel-open');
});

if (window.speechSynthesis) {
  window.speechSynthesis.getVoices();
  window.speechSynthesis.addEventListener('voiceschanged', () => {
    const v = getEnglishVoice();
    console.log('🔊 TTS voice:', v ? `${v.name} (${v.lang})` : 'browser default (en-US)');
  });
}

setStatus('Ready — press and hold to record', 'idle');
console.log('🎙 NOVA v2.0 loaded — Whisper STT + ACRCloud + Groq LLaMA + Django');
console.log(`🎨 Theme: ${getTheme()}`);
