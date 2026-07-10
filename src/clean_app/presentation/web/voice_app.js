// DOM Elements
const voiceBody = document.getElementById("voice-body");
const orbTrigger = document.getElementById("orb-trigger");
const statusLabel = document.getElementById("status-label");
const micIcon = document.getElementById("mic-icon");
const playingIcon = document.getElementById("playing-icon");
const thinkingIcon = document.getElementById("thinking-icon");
const canvas = document.getElementById("canvas-visualizer");
const autoListenToggle = document.getElementById("auto-listen-toggle");
const toggleLogBtn = document.getElementById("toggle-log-btn");
const exitBtn = document.getElementById("exit-btn");
const transcriptDrawer = document.getElementById("transcript-drawer");
const closeLogBtn = document.getElementById("close-log-btn");
const drawerBody = document.getElementById("drawer-body");

// Audio Context & Recording variables
let audioContext = null;
let analyser = null;
let micStream = null;
let mediaRecorder = null;
let audioChunks = [];
let visualizerId = null;

// Silence detection (VAD) configuration
let isRecording = false;
let hasSpoken = false;
let silenceStartTimer = null;
const SILENCE_THRESHOLD = 0.022; // RMS volume threshold (higher for background noise resistance)
const SILENCE_DURATION_MS = 750; // 0.75 seconds of silence to trigger auto-submit (snappier, Ixigo-style)

// Audio playback state
let activeAudio = null;
let session_id = "voice_session_" + Math.random().toString(36).substring(2, 11);
let lastResumeTime = 0; // Timestamp to filter initial mic click/pops
let ambientSamples = []; // Collected samples for ambient noise calibration
let calibratedThreshold = 0.022; // Calibrated adaptive threshold

// Visualizer configuration
const ctx = canvas.getContext("2d");
function resizeCanvas() {
  canvas.width = orbTrigger.clientWidth;
  canvas.height = orbTrigger.clientHeight;
}
window.addEventListener("resize", resizeCanvas);
resizeCanvas();

// Web Audio API Synthesized Chime Cues for clean, lag-free responsiveness (Ixigo-style)
function playAudioCue(type) {
  try {
    const ctxNode = audioContext || new (window.AudioContext || window.webkitAudioContext)();
    if (ctxNode.state === "suspended") {
      ctxNode.resume();
    }
    const now = ctxNode.currentTime;

    if (type === "listen") {
      // Clean rising chime (double tone: 440Hz -> 620Hz)
      const osc1 = ctxNode.createOscillator();
      const osc2 = ctxNode.createOscillator();
      const gainNode = ctxNode.createGain();

      osc1.type = "sine";
      osc1.frequency.setValueAtTime(440, now);
      osc1.frequency.exponentialRampToValueAtTime(490, now + 0.08);

      osc2.type = "sine";
      osc2.frequency.setValueAtTime(620, now + 0.08);
      osc2.frequency.exponentialRampToValueAtTime(680, now + 0.16);

      gainNode.gain.setValueAtTime(0.0, now);
      gainNode.gain.linearRampToValueAtTime(0.12, now + 0.02);
      gainNode.gain.setValueAtTime(0.12, now + 0.08);
      gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.22);

      osc1.connect(gainNode);
      osc2.connect(gainNode);
      gainNode.connect(ctxNode.destination);

      osc1.start(now);
      osc1.stop(now + 0.08);
      osc2.start(now + 0.08);
      osc2.stop(now + 0.22);

    } else if (type === "stop") {
      // Soft falling chime (double tone: 540Hz -> 380Hz)
      const osc1 = ctxNode.createOscillator();
      const osc2 = ctxNode.createOscillator();
      const gainNode = ctxNode.createGain();

      osc1.type = "sine";
      osc1.frequency.setValueAtTime(540, now);
      osc1.frequency.exponentialRampToValueAtTime(500, now + 0.08);

      osc2.type = "sine";
      osc2.frequency.setValueAtTime(380, now + 0.08);
      osc2.frequency.exponentialRampToValueAtTime(340, now + 0.16);

      gainNode.gain.setValueAtTime(0.0, now);
      gainNode.gain.linearRampToValueAtTime(0.1, now + 0.02);
      gainNode.gain.setValueAtTime(0.1, now + 0.08);
      gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.22);

      osc1.connect(gainNode);
      osc2.connect(gainNode);
      gainNode.connect(ctxNode.destination);

      osc1.start(now);
      osc1.stop(now + 0.08);
      osc2.start(now + 0.08);
      osc2.stop(now + 0.22);
    }
  } catch (err) {
    console.warn("Could not play synthesized audio cue:", err);
  }
}

// Change visual orb states: 'idle', 'listening', 'thinking', 'speaking'
function transitionState(state) {
  voiceBody.classList.remove("state-idle", "state-listening", "state-thinking", "state-speaking");
  voiceBody.classList.add(`state-${state}`);

  // Hide all icons
  micIcon.classList.add("hidden");
  playingIcon.classList.add("hidden");
  thinkingIcon.classList.add("hidden");

  if (state === "idle") {
    micIcon.classList.remove("hidden");
    statusLabel.textContent = "Tap to Speak";
  } else if (state === "listening") {
    micIcon.classList.remove("hidden");
    statusLabel.textContent = "Listening...";
    playAudioCue("listen");
  } else if (state === "thinking") {
    thinkingIcon.classList.remove("hidden");
    statusLabel.textContent = "Thinking...";
    playAudioCue("stop");
  } else if (state === "speaking") {
    playingIcon.classList.remove("hidden");
    statusLabel.textContent = "Speaking...";
  }
}

// Log messages in the slide-up drawer
function logMessage(role, text) {
  const bubble = document.createElement("div");
  bubble.className = `log-bubble ${role}`;
  bubble.textContent = text;
  drawerBody.appendChild(bubble);
  drawerBody.scrollTop = drawerBody.scrollHeight;
}

// Visualizer: Draw sound waves around the orb
function startVisualizer() {
  const bufferLength = analyser ? analyser.frequencyBinCount : 64;
  const dataArray = new Uint8Array(bufferLength);

  function draw() {
    visualizerId = requestAnimationFrame(draw);
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    let volume = 0;
    if (analyser && isRecording) {
      analyser.getByteFrequencyData(dataArray);
      let sum = 0;
      for (let i = 0; i < bufferLength; i++) {
        sum += dataArray[i];
      }
      volume = sum / bufferLength;
    } else if (voiceBody.classList.contains("state-speaking") && activeAudio) {
      // Simulate waveform when AI is speaking using an oscillating wave
      volume = 15 + Math.sin(Date.now() / 80) * 12 + Math.random() * 5;
    }

    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    // Orb radius is roughly 85px in standard and 70px in mobile
    const baseRadius = canvas.width < 300 ? 70 : 85;

    // Draw animated halo layers
    const numPoints = 80;
    ctx.beginPath();
    for (let i = 0; i < numPoints; i++) {
      const angle = (i / numPoints) * Math.PI * 2;
      // Frequency/volume modulation
      const mod = volume > 0 ? (volume / 255) * 35 * Math.sin(i * 0.4 + Date.now() * 0.01) : 0;
      const r = baseRadius + 8 + mod;
      const x = centerX + Math.cos(angle) * r;
      const y = centerY + Math.sin(angle) * r;

      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();

    // Colors based on state
    if (voiceBody.classList.contains("state-listening")) {
      ctx.strokeStyle = "rgba(239, 68, 68, 0.6)"; // Red
      ctx.lineWidth = 3;
    } else if (voiceBody.classList.contains("state-speaking")) {
      ctx.strokeStyle = "rgba(16, 185, 129, 0.7)"; // Green
      ctx.lineWidth = 3;
    } else {
      ctx.strokeStyle = "rgba(6, 182, 212, 0.4)"; // Cyan
      ctx.lineWidth = 2;
    }
    ctx.stroke();
  }

  draw();
}

function stopVisualizer() {
  if (visualizerId) {
    cancelAnimationFrame(visualizerId);
    visualizerId = null;
  }
}

// Silence Detection loop (calculates RMS of audio input)
function startSilenceDetection(stream) {
  if (!audioContext) {
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
  }
  if (audioContext.state === "suspended") {
    audioContext.resume();
  }

  const source = audioContext.createMediaStreamSource(stream);
  analyser = audioContext.createAnalyser();
  analyser.fftSize = 256;
  source.connect(analyser);

  const processor = audioContext.createScriptProcessor(2048, 1, 1);
  source.connect(processor);
  processor.connect(audioContext.destination);

  hasSpoken = false;
  silenceStartTimer = null;
  ambientSamples = [];
  calibratedThreshold = 0.022;

  processor.onaudioprocess = (e) => {
    if (!isRecording) return;

    const inputBuffer = e.inputBuffer.getChannelData(0);
    let sum = 0;
    for (let i = 0; i < inputBuffer.length; i++) {
      sum += inputBuffer[i] * inputBuffer[i];
    }
    const rms = Math.sqrt(sum / inputBuffer.length);

    // Calibration phase (first 500ms)
    if (Date.now() - lastResumeTime < 500) {
      ambientSamples.push(rms);
      return;
    }

    // End of calibration phase: compute adaptive threshold
    if (ambientSamples.length > 0) {
      const avgAmbient = ambientSamples.reduce((a, b) => a + b, 0) / ambientSamples.length;
      calibratedThreshold = Math.max(SILENCE_THRESHOLD, avgAmbient * 1.8);
      ambientSamples = []; // Clear to signal calibration is done
      console.log(`[Voice App VAD Calibrated] Ambient Avg: ${avgAmbient.toFixed(4)} | Threshold Set To: ${calibratedThreshold.toFixed(4)}`);
    }

    // Check if voice levels cross threshold (using calibratedThreshold instead of static SILENCE_THRESHOLD)
    if (rms > calibratedThreshold) {
      if (!hasSpoken) {
        hasSpoken = true;
        statusLabel.textContent = "Listening...";
      }
      // Reset silence timer because they are currently speaking
      if (silenceStartTimer) {
        clearTimeout(silenceStartTimer);
        silenceStartTimer = null;
      }
    } else if (hasSpoken) {
      // User has spoken but is now silent. Start timer to auto-submit
      if (!silenceStartTimer) {
        statusLabel.textContent = "Processing pause...";
        silenceStartTimer = setTimeout(() => {
          console.log("[Silence VAD] Silence detected. Automatically stopping recording.");
          stopRecordingAndSubmit();
        }, SILENCE_DURATION_MS);
      }
    }
  };

  // Save references to cleanup later
  stream.processor = processor;
  stream.source = source;
}

// Stop Audio recording and submit to backend
async function stopRecordingAndSubmit() {
  if (!isRecording) return;
  isRecording = false;

  transitionState("thinking");

  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
  }
}

// Handle microphone streaming and launch MediaRecorder
async function startRecording() {
  if (isRecording) return;
  isRecording = true;
  audioChunks = [];
  lastResumeTime = Date.now();
  ambientSamples = [];
  calibratedThreshold = 0.022;

  // Stop any active AI speech
  if (activeAudio) {
    activeAudio.pause();
    activeAudio = null;
  }

  try {
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      }
    });

    // Check supported mime types
    let options = { mimeType: "audio/webm" };
    if (!MediaRecorder.isTypeSupported("audio/webm")) {
      options = { mimeType: "audio/ogg" };
    }

    mediaRecorder = new MediaRecorder(micStream, options);
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data);
      }
    };

    mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(audioChunks, { type: options.mimeType });

      // Clean up mic streams and processors
      if (micStream) {
        if (micStream.processor) micStream.processor.disconnect();
        if (micStream.source) micStream.source.disconnect();
        micStream.getTracks().forEach(track => track.stop());
      }

      await submitVoiceQuery(audioBlob);
    };

    transitionState("listening");
    startSilenceDetection(micStream);
    startVisualizer();
    mediaRecorder.start();

  } catch (error) {
    console.error("Microphone access blocked or failed:", error);
    isRecording = false;
    transitionState("idle");
    // Turn off auto-listen to prevent loop locks under permission-denied / constraint environments
    autoListenToggle.checked = false;
    alert("Could not access microphone. Please check permissions.");
  }
}

// Call backend speech-to-text -> query pipeline -> text-to-speech
async function submitVoiceQuery(blob) {
  try {
    const formData = new FormData();
    formData.append("file", blob, "voice.webm");
    formData.append("session_id", session_id);
    formData.append("top_k", 3);

    const response = await fetch("/api/chat/voice-input", {
      method: "POST",
      body: formData
    });

    if (!response.ok) {
      throw new Error(`Voice endpoint error: ${response.status}`);
    }

    const data = await response.json();

    // Log user transcription and AI answer text
    logMessage("user", data.query);
    logMessage("assistant", data.answer);

    if (data.audio_base64) {
      playSpeech(data.audio_base64, data.answer);
    } else if (data.answer) {
      speakBrowserFallback(data.answer);
    } else {
      transitionState("idle");
    }

  } catch (error) {
    console.error("Failed to submit voice payload:", error);
    logMessage("assistant", "Sorry, I had trouble understanding that. Let's try again.");
    transitionState("idle");

    // If auto-listen is checked, auto-listen after errors too
    if (autoListenToggle.checked) {
      setTimeout(startRecording, 1000);
    }
  }
}

// Fallback browser speech synthesis if backend TTS is unavailable/fails
function speakBrowserFallback(text) {
  if (activeAudio) {
    activeAudio.pause();
    activeAudio = null;
  }
  window.speechSynthesis.cancel();

  // Strip markdown formatting out of spoken text
  const cleanText = text
    .replace(/\*\*/g, "")
    .replace(/\*/g, "")
    .replace(/-\s/g, "")
    .replace(/#+/g, "")
    .replace(/\n/g, " ")
    .trim();

  if (!cleanText) {
    transitionState("idle");
    return;
  }

  const utterance = new SpeechSynthesisUtterance(cleanText);

  // Try to find a nice Indian or English voice
  const voices = window.speechSynthesis.getVoices();
  const targetVoice = voices.find(v => v.lang === "hi-IN" || v.lang === "en-IN") || voices.find(v => v.lang.startsWith("en"));
  if (targetVoice) {
    utterance.voice = targetVoice;
  }

  utterance.onstart = () => {
    transitionState("speaking");
    startVisualizer();
  };

  utterance.onend = () => {
    transitionState("idle");
    stopVisualizer();

    // continuous conversation hook
    if (autoListenToggle.checked) {
      console.log("[Voice App] Fallback playback ended. Auto-listening again...");
      setTimeout(startRecording, 500);
    }
  };

  utterance.onerror = (e) => {
    console.error("SpeechSynthesis error:", e);
    transitionState("idle");
    stopVisualizer();

    // Proceed to listening if auto-listen is checked, so the app doesn't hang on error
    if (autoListenToggle.checked) {
      console.log("[Voice App] Speech synthesis errored. Moving to auto-listening...");
      setTimeout(startRecording, 500);
    }
  };

  window.speechSynthesis.speak(utterance);
}

// Convert base64 and play synthesized audio
function playSpeech(base64Data, textFallback = "") {
  if (activeAudio) {
    activeAudio.pause();
    activeAudio = null;
  }
  window.speechSynthesis.cancel();

  const audioUrl = `data:audio/mp3;base64,${base64Data}`;
  activeAudio = new Audio(audioUrl);

  activeAudio.onplay = () => {
    transitionState("speaking");
    startVisualizer();
  };

  activeAudio.onended = () => {
    activeAudio = null;
    transitionState("idle");
    stopVisualizer();

    // continuous conversation hook
    if (autoListenToggle.checked) {
      console.log("[Voice App] Response playback ended. Auto-listening again...");
      setTimeout(startRecording, 500);
    }
  };

  activeAudio.onerror = (e) => {
    console.error("Audio playback error:", e);
    activeAudio = null;
    if (textFallback) {
      console.log("[Voice App] Audio playback failed. Falling back to browser speech synthesis...");
      speakBrowserFallback(textFallback);
    } else {
      transitionState("idle");
      stopVisualizer();
    }
  };

  activeAudio.play().catch(err => {
    console.warn("Autoplay blocked or playback aborted:", err);
    activeAudio = null;
    if (textFallback) {
      console.log("[Voice App] Autoplay blocked. Falling back to browser speech synthesis...");
      speakBrowserFallback(textFallback);
    } else {
      transitionState("idle");
      stopVisualizer();
    }
  });
}

// User clicked central visualizer orb
orbTrigger.addEventListener("click", () => {
  // Resume audio context for browsers that block it
  if (audioContext && audioContext.state === "suspended") {
    audioContext.resume();
  }

  if (voiceBody.classList.contains("state-speaking")) {
    // Interrupt AI speech
    if (activeAudio) {
      activeAudio.pause();
      activeAudio = null;
    }
    window.speechSynthesis.cancel();
    transitionState("idle");
    stopVisualizer();
  } else if (isRecording) {
    // Manually stop and submit
    stopRecordingAndSubmit();
  } else {
    // Start listening
    startRecording();
  }
});

// Navigation and panel controls
toggleLogBtn.addEventListener("click", () => {
  transcriptDrawer.classList.toggle("active");
});

closeLogBtn.addEventListener("click", () => {
  transcriptDrawer.classList.remove("active");
});

exitBtn.addEventListener("click", () => {
  // Cleanup audio objects
  if (activeAudio) {
    activeAudio.pause();
    activeAudio = null;
  }
  window.speechSynthesis.cancel();
  if (isRecording && mediaRecorder) {
    mediaRecorder.stop();
  }
  window.location.href = "/";
});

// Setup visualizer for idle animation on start
startVisualizer();
transitionState("idle");

// Play welcome message on load or on first user click/interaction
function playWelcomeGreeting() {
  const welcomeText = "Hello! I am your Trvios Voice Assistant. Speak anytime to ask about our travel packages, budget trips, become a partner portal, or the split bills tool!";
  console.log("[Voice App] Playing welcome greeting...");

  // Clean up any existing utterance/audio before playing greeting
  if (activeAudio) {
    activeAudio.pause();
    activeAudio = null;
  }

  try {
    window.speechSynthesis.cancel();
    speakBrowserFallback(welcomeText);
  } catch (err) {
    console.error("Failed to play welcome greeting:", err);
    // If speaking fails completely, transition to listening directly
    if (autoListenToggle.checked) {
      setTimeout(startRecording, 500);
    }
  }
}

// Automatic greeting trigger (handling browser autoplay restrictions)
let welcomeTriggered = false;

function triggerGreetingOnce() {
  if (welcomeTriggered) return;
  welcomeTriggered = true;

  // Resume AudioContext for visualizer on first interaction
  if (audioContext && audioContext.state === "suspended") {
    audioContext.resume();
  }

  playWelcomeGreeting();

  // Remove event listeners once triggered
  document.removeEventListener("click", triggerGreetingOnce);
  document.removeEventListener("touchstart", triggerGreetingOnce);
}

// Try to trigger on page load
window.addEventListener("DOMContentLoaded", () => {
  // Try to play immediately, fallback to click/touch if blocked
  setTimeout(() => {
    try {
      playWelcomeGreeting();
      welcomeTriggered = true;
    } catch (e) {
      console.warn("Autoplay welcome greeting blocked. Waiting for user interaction to play:", e);
      // Wait for click or touch to play greeting
      document.addEventListener("click", triggerGreetingOnce);
      document.addEventListener("touchstart", triggerGreetingOnce);
    }
  }, 300);
});

// Fallback trigger if DOMContentLoaded has already fired
if (document.readyState === "complete" || document.readyState === "interactive") {
  setTimeout(() => {
    if (!welcomeTriggered) {
      try {
        playWelcomeGreeting();
        welcomeTriggered = true;
      } catch (e) {
        document.addEventListener("click", triggerGreetingOnce);
        document.addEventListener("touchstart", triggerGreetingOnce);
      }
    }
  }, 300);
} else {
  document.addEventListener("click", triggerGreetingOnce);
  document.addEventListener("touchstart", triggerGreetingOnce);
}
