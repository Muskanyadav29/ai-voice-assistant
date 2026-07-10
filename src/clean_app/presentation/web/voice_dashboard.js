// DOM Elements
const callBody = document.getElementById("call-body");
const statusDisplay = document.getElementById("status-display");
const userCard = document.getElementById("user-card");
const botCard = document.getElementById("bot-card");
const userSubtext = document.getElementById("user-subtext");
const botSubtext = document.getElementById("bot-subtext");
const canvas = document.getElementById("canvas-visualizer");
const btnMute = document.getElementById("btn-mute");
const btnCallTrigger = document.getElementById("btn-call-trigger");
const callBtnIcon = document.getElementById("call-btn-icon");
const btnToggleDrawer = document.getElementById("btn-toggle-drawer");
const callTimerVal = document.getElementById("call-timer");
const micLevelVal = document.getElementById("mic-level-val");
const vadActivityVal = document.getElementById("vad-activity-val");
const transcriptFeed = document.getElementById("transcript-feed");
const prefLanguage = document.getElementById("pref-language");
const prefSensitivity = document.getElementById("pref-sensitivity");

// Audio Context & Streaming states
let audioContext = null;
let analyser = null;
let micStream = null;
let mediaRecorder = null;
let audioChunks = [];
let visualizerId = null;

// Call configuration
let isCallActive = false;
let isMuted = false;
let isRecording = false;
let hasSpoken = false;
let silenceStartTimer = null;
let speechTicks = 0;
let callDuration = 0;
let timerInterval = null;
let activeAudio = null;
let session_id = null;
let lastResumeTime = 0; // Timestamp to prevent microphone pops and speaker trails from triggering VAD
let ambientSamples = []; // Collected samples for ambient noise calibration
let calibratedThreshold = 0.022; // Calibrated adaptive threshold

// Dynamic configuration from UI settings
let silenceThreshold = 0.022; // RMS threshold
let SILENCE_DURATION_MS = 800; // 0.8s of silence triggers submission (snappier response)

// Web Audio API canvas visualizer configuration
const ctx = canvas.getContext("2d");
function resizeCanvas() {
  const container = canvas.parentElement;
  canvas.width = container.clientWidth;
  canvas.height = container.clientHeight;
}
window.addEventListener("resize", resizeCanvas);
resizeCanvas();

// Web Audio API Synthesized sound cues (Premium Ixigo/Phone style)
function playSyntheticChime(type) {
  try {
    const ctxNode = audioContext || new (window.AudioContext || window.webkitAudioContext)();
    if (ctxNode.state === "suspended") {
      ctxNode.resume();
    }
    const now = ctxNode.currentTime;
    const gainNode = ctxNode.createGain();
    gainNode.connect(ctxNode.destination);

    if (type === "connect") {
      // Pleasant double bell (523Hz -> 659Hz - C5 to E5)
      const osc1 = ctxNode.createOscillator();
      const osc2 = ctxNode.createOscillator();
      osc1.type = "sine";
      osc2.type = "sine";
      osc1.frequency.setValueAtTime(523.25, now);
      osc2.frequency.setValueAtTime(659.25, now + 0.12);

      gainNode.gain.setValueAtTime(0.0, now);
      gainNode.gain.linearRampToValueAtTime(0.12, now + 0.04);
      gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.35);

      osc1.connect(gainNode);
      osc2.connect(gainNode);
      osc1.start(now);
      osc1.stop(now + 0.15);
      osc2.start(now + 0.12);
      osc2.stop(now + 0.35);

    } else if (type === "disconnect") {
      // Soft clean fall chime (392Hz -> 261Hz - G4 to C4)
      const osc = ctxNode.createOscillator();
      osc.type = "sine";
      osc.frequency.setValueAtTime(392, now);
      osc.frequency.exponentialRampToValueAtTime(261.63, now + 0.25);

      gainNode.gain.setValueAtTime(0.12, now);
      gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.25);

      osc.connect(gainNode);
      osc.start(now);
      osc.stop(now + 0.25);

    } else if (type === "listening_beep") {
      // Soft high tone (880Hz) to signal mic active
      const osc = ctxNode.createOscillator();
      osc.type = "sine";
      osc.frequency.setValueAtTime(880, now);
      
      gainNode.gain.setValueAtTime(0.0, now);
      gainNode.gain.linearRampToValueAtTime(0.05, now + 0.02);
      gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.1);

      osc.connect(gainNode);
      osc.start(now);
      osc.stop(now + 0.1);
    }
  } catch (err) {
    console.warn("Could not play synthesized audio chime:", err);
  }
}

// Transition Dashboard Visual State
function transitionState(state) {
  callBody.className = `state-${state}`;
  
  // Reset active classes
  userCard.classList.remove("active");
  botCard.classList.remove("active");
  
  if (state === "disconnected") {
    statusDisplay.textContent = "Disconnected";
    userSubtext.textContent = "Inactive";
    botSubtext.textContent = "Offline";
    micLevelVal.textContent = "Muted";
    vadActivityVal.textContent = "None";
  } else if (state === "connecting") {
    statusDisplay.textContent = "Connecting Call...";
    userSubtext.textContent = "Syncing...";
    botSubtext.textContent = "Connecting...";
  } else if (state === "listening") {
    statusDisplay.textContent = "Listening";
    userCard.classList.add("active");
    userSubtext.textContent = "Speaking/Silent";
    botSubtext.textContent = "Waiting";
    vadActivityVal.textContent = "Monitoring";
  } else if (state === "thinking") {
    statusDisplay.textContent = "AI Processing...";
    userSubtext.textContent = "Processing Pause";
    botCard.classList.add("active");
    botSubtext.textContent = "Thinking...";
    vadActivityVal.textContent = "Inactive";
  } else if (state === "speaking") {
    statusDisplay.textContent = "AI Speaking";
    botCard.classList.add("active");
    botSubtext.textContent = "Speaking...";
    userSubtext.textContent = "Muted (Listening Off)";
    vadActivityVal.textContent = "Suppressed";
  } else if (state === "muted") {
    statusDisplay.textContent = "Microphone Muted";
    userSubtext.textContent = "Muted";
    botSubtext.textContent = "Waiting";
    micLevelVal.textContent = "Muted";
    vadActivityVal.textContent = "None";
  }
}

// Log transcript bubble to feed
function logCallMessage(role, text) {
  // Remove existing system helper bubble if any
  const systemBubble = transcriptFeed.querySelector(".chat-bubble.system");
  if (systemBubble) {
    systemBubble.remove();
  }

  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${role}`;
  
  const textContent = document.createElement("div");
  
  // Format basic HTML entities
  let formattedText = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  if (role === 'bot') {
    // Parse CARD tags
    formattedText = formattedText.replace(/\[CARD:\s*([\s\S]*?)\s*\]/g, (match, content) => {
      const parts = content.split("|");
      const data = {};
      for (let part of parts) {
        const decodedPart = part.replaceAll("&amp;", "&").replaceAll("&#39;", "'").replaceAll("&quot;", '"');
        const idx = decodedPart.indexOf("=");
        if (idx !== -1) {
          const k = decodedPart.slice(0, idx).replace(/<br\s*\/?>/gi, "").trim().toLowerCase();
          const v = decodedPart.slice(idx + 1).replace(/<br\s*\/?>/gi, "").trim();
          data[k] = v;
        }
      }

      const type = data.type || "attraction";
      const name = data.name || "Unknown Place";
      const rating = data.rating || "4.0";
      const photo_url = data.photo_url || "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=200&auto=format&fit=crop";
      const maps_url = data.maps_url || "#";
      const address = data.address || "";

      // Safe string escaping for HTML onclick handler
      const escapedName = name.replace(/'/g, "\\'");

      if (type === "hotel") {
        const price = data.price || "N/A";
        const amenities = data.amenities || "";
        const amenityHtml = amenities ? amenities.split(",").map(a => `<span class="amenity-tag">${a.trim()}</span>`).join("") : "";
        
        return `
  <div class="place-card hotel">
    <img src="${photo_url}" alt="${name}" onerror="this.src='https://images.unsplash.com/photo-1566073771259-6a8506099945?w=200&auto=format&fit=crop';">
    <div class="place-card-content">
      <div class="place-card-name">${name}</div>
      <div class="place-card-rating">⭐⭐⭐⭐⭐ ${rating}</div>
      <div class="place-card-price">${price}</div>
      <div class="place-card-amenities">${amenityHtml}</div>
      <a class="place-card-link" href="${maps_url}" target="_blank">📍 View on Google Maps ↗</a>
      <div class="place-card-actions" style="display: flex; gap: 8px; margin-top: 8px;">
        <button class="card-action-btn" style="background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); color: #fff; padding: 4px 8px; border-radius: 4px; font-size: 11px; cursor: pointer; display: flex; align-items: center; gap: 4px;" onclick="handleCardAction('swap', '${escapedName}', 'hotel')">🔄 Swap</button>
        <button class="card-action-btn" style="background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); color: #fff; padding: 4px 8px; border-radius: 4px; font-size: 11px; cursor: pointer; display: flex; align-items: center; gap: 4px;" onclick="handleCardAction('calendar', '${escapedName}', 'hotel')">📅 Add to Calendar</button>
      </div>
    </div>
  </div>
  `;
      } else if (type === "restaurant" || type === "lunch" || type === "dinner") {
        const cuisine = data.cuisine || "Local Cuisine";
        const avg_cost = data.avg_cost || "N/A";
        const must_try = data.must_try || "";
        
        return `
  <div class="place-card restaurant">
    <img src="${photo_url}" alt="${name}" onerror="this.src='https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=200&auto=format&fit=crop';">
    <div class="place-card-content">
      <div class="place-card-name">${name}</div>
      <div class="place-card-rating">⭐ ${rating} | <em>${cuisine}</em></div>
      <div class="place-card-info-grid">
        <div class="info-item"><strong>🍽 Avg Cost:</strong> ${avg_cost}</div>
        <div class="info-item"><strong>🍴 Must Try:</strong> ${must_try}</div>
      </div>
      <div class="place-card-address">${address}</div>
      <a class="place-card-link" href="${maps_url}" target="_blank">📍 View on Google Maps ↗</a>
      <div class="place-card-actions" style="display: flex; gap: 8px; margin-top: 8px;">
        <button class="card-action-btn" style="background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); color: #fff; padding: 4px 8px; border-radius: 4px; font-size: 11px; cursor: pointer; display: flex; align-items: center; gap: 4px;" onclick="handleCardAction('swap', '${escapedName}', 'restaurant')">🔄 Swap</button>
        <button class="card-action-btn" style="background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); color: #fff; padding: 4px 8px; border-radius: 4px; font-size: 11px; cursor: pointer; display: flex; align-items: center; gap: 4px;" onclick="handleCardAction('calendar', '${escapedName}', 'restaurant')">📅 Add to Calendar</button>
      </div>
    </div>
  </div>
  `;
      } else { // attraction
        const visit_time = data.visit_time || "Flexible";
        const stay = data.stay || "Flexible";
        const travel = data.travel || "N/A";
        const entry = data.entry || "Free";
        const reviews = data.reviews || "";
        const reviewText = reviews ? `(${reviews})` : "";
        
        return `
  <div class="place-card attraction">
    <img src="${photo_url}" alt="${name}" onerror="this.src='https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=200&auto=format&fit=crop';">
    <div class="place-card-content">
      <div class="place-card-name">${name}</div>
      <div class="place-card-rating">⭐ ${rating} ${reviewText}</div>
      <div class="place-card-info-grid">
        <div class="info-item"><strong>🕒 Visit Time:</strong> ${visit_time}</div>
        <div class="info-item"><strong>⏱ Stay:</strong> ${stay}</div>
        <div class="info-item"><strong>🚗 Travel:</strong> ${travel}</div>
        <div class="info-item"><strong>🎟 Entry:</strong> ${entry}</div>
      </div>
      <div class="place-card-address">${address}</div>
      <a class="place-card-link" href="${maps_url}" target="_blank">📍 View on Google Maps ↗</a>
      <div class="place-card-actions" style="display: flex; gap: 8px; margin-top: 8px;">
        <button class="card-action-btn" style="background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); color: #fff; padding: 4px 8px; border-radius: 4px; font-size: 11px; cursor: pointer; display: flex; align-items: center; gap: 4px;" onclick="handleCardAction('remove', '${escapedName}', 'attraction')">❌ Remove</button>
        <button class="card-action-btn" style="background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); color: #fff; padding: 4px 8px; border-radius: 4px; font-size: 11px; cursor: pointer; display: flex; align-items: center; gap: 4px;" onclick="handleCardAction('calendar', '${escapedName}', 'attraction')">📅 Add to Calendar</button>
      </div>
    </div>
  </div>
  `;
      }
    });

    // Parse TRAVEL tags
    formattedText = formattedText.replace(/\[TRAVEL:\s*([\s\S]*?)\s*\]/g, (match, content) => {
      const parts = content.split("|");
      const data = {};
      for (let part of parts) {
        const decodedPart = part.replaceAll("&amp;", "&").replaceAll("&#39;", "'").replaceAll("&quot;", '"');
        const idx = decodedPart.indexOf("=");
        if (idx !== -1) {
          const k = decodedPart.slice(0, idx).replace(/<br\s*\/?>/gi, "").trim().toLowerCase();
          const v = decodedPart.slice(idx + 1).replace(/<br\s*\/?>/gi, "").trim();
          data[k] = v;
        }
      }
      
      const leave_time = data.leave_time || "N/A";
      const travel_time = data.travel_time || "N/A";
      const distance = data.distance || "N/A";
      const navigation_link = data.navigation_link || "#";
      
      return `
  <div class="travel-transition">
    <div class="travel-icon">🚖</div>
    <div class="travel-details">
      <strong>Leave at:</strong> ${leave_time} | <strong>Drive Time:</strong> ${travel_time} | <strong>Distance:</strong> ${distance}<br/>
      <a class="place-card-link" href="${navigation_link}" target="_blank" style="margin-top: 4px; display: inline-flex; align-items: center; gap: 4px;">🗺️ Start Navigation ↗</a>
    </div>
    <div class="travel-arrow">↓</div>
  </div>
  `;
    });

    // Parse TIME tags
    formattedText = formattedText.replace(/\[TIME:\s*(.*?)\s*\|\s*(.*?)\]/g, `
  <div class="timeline-item">
    <div class="timeline-time">🕒 $1</div>
    <div class="timeline-content">$2</div>
  </div>
  `);
  } else {
    // Strip cards for non-bot messages
    formattedText = formattedText.replace(/\[CARD:[^\]]*\]/g, "").replace(/\[TRAVEL:[^\]]*\]/g, "");
  }

  // Parse remaining basic markdown
  formattedText = formattedText
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/### (.*)/g, "<h3>$1</h3>")
    .replace(/## (.*)/g, "<h2>$1</h2>")
    .replace(/# (.*)/g, "<h1>$1</h1>")
    .replace(/\n/g, "<br>");

  textContent.innerHTML = formattedText;
  bubble.appendChild(textContent);

  // Time stamp
  const time = document.createElement("div");
  time.className = "bubble-time";
  const now = new Date();
  time.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  bubble.appendChild(time);

  transcriptFeed.appendChild(bubble);
  transcriptFeed.scrollTop = transcriptFeed.scrollHeight;

  // Also update live subtitle display
  const subtitleEl = document.getElementById("live-subtitle");
  if (subtitleEl) {
    // Strip markdown formatting out of spoken text
    const cleanText = text
      .replace(/\*\*/g, "")
      .replace(/\*/g, "")
      .replace(/-\s/g, "")
      .replace(/#+/g, "")
      .replace(/\[CARD:[^\]]*\]/g, "")
      .replace(/\[TRAVEL:[^\]]*\]/g, "")
      .trim();
    if (role === 'bot') {
      subtitleEl.innerHTML = `<span style="color: #10b981; font-weight: 600;">Trvios AI:</span> ${cleanText}`;
    } else if (role === 'user') {
      subtitleEl.innerHTML = `<span style="color: #22d3ee; font-weight: 600;">You:</span> ${cleanText}`;
    } else if (role === 'system') {
      subtitleEl.innerHTML = `<span style="color: #94a3b8; font-style: italic;">${cleanText}</span>`;
    }
  }
}

// Start Call Timer
function startTimer() {
  callDuration = 0;
  clearInterval(timerInterval);
  callTimerVal.textContent = "00:00";
  
  timerInterval = setInterval(() => {
    callDuration++;
    const mins = String(Math.floor(callDuration / 60)).padStart(2, '0');
    const secs = String(callDuration % 60).padStart(2, '0');
    callTimerVal.textContent = `${mins}:${secs}`;
  }, 1000);
}

function stopTimer() {
  clearInterval(timerInterval);
}

// Draw Animated Soundwaves around Central Orb
function startVisualizer() {
  const bufferLength = analyser ? analyser.frequencyBinCount : 64;
  const dataArray = new Uint8Array(bufferLength);

  function draw() {
    visualizerId = requestAnimationFrame(draw);
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    let volume = 0;
    if (analyser && isRecording && !isMuted && isCallActive && callBody.classList.contains("state-listening")) {
      analyser.getByteFrequencyData(dataArray);
      let sum = 0;
      for (let i = 0; i < bufferLength; i++) {
        sum += dataArray[i];
      }
      volume = sum / bufferLength;
      micLevelVal.textContent = `${Math.round(volume)} dB`;
    } else if (callBody.classList.contains("state-speaking") && activeAudio) {
      // Simulate speaking wave
      volume = 18 + Math.sin(Date.now() / 60) * 12 + Math.random() * 4;
      micLevelVal.textContent = "AI Output";
    } else if (callBody.classList.contains("state-thinking")) {
      // Subtle pulse
      volume = 8 + Math.sin(Date.now() / 150) * 4;
      micLevelVal.textContent = "Processing";
    }

    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const baseRadius = canvas.width < 250 ? 45 : 55;

    // Draw secondary outer halo
    if (volume > 0) {
      ctx.beginPath();
      ctx.arc(centerX, centerY, baseRadius + 15 + (volume / 255) * 40, 0, Math.PI * 2);
      ctx.strokeStyle = callBody.classList.contains("state-listening")
        ? "rgba(6, 182, 212, 0.15)"
        : callBody.classList.contains("state-speaking")
        ? "rgba(16, 185, 129, 0.15)"
        : "rgba(139, 92, 246, 0.1)";
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    // Draw primary visualizer wave rings
    const numPoints = 80;
    ctx.beginPath();
    for (let i = 0; i < numPoints; i++) {
      const angle = (i / numPoints) * Math.PI * 2;
      const waveMod = volume > 0 ? (volume / 255) * 45 * Math.sin(i * 0.5 + Date.now() * 0.015) : 0;
      const r = baseRadius + waveMod;
      const x = centerX + Math.cos(angle) * r;
      const y = centerY + Math.sin(angle) * r;

      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();

    if (callBody.classList.contains("state-listening")) {
      ctx.strokeStyle = "rgba(6, 182, 212, 0.75)"; // Cyan
      ctx.lineWidth = 2.5;
    } else if (callBody.classList.contains("state-speaking")) {
      ctx.strokeStyle = "rgba(16, 185, 129, 0.85)"; // Green
      ctx.lineWidth = 3;
    } else if (callBody.classList.contains("state-thinking")) {
      ctx.strokeStyle = "rgba(139, 92, 246, 0.6)"; // Purple
      ctx.lineWidth = 2;
    } else {
      ctx.strokeStyle = "rgba(255, 255, 255, 0.08)"; // Silent
      ctx.lineWidth = 1.5;
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

// Voice Activity Detection (VAD) using ScriptProcessor RMS level calculation
function startVAD(stream) {
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
    // Only perform VAD checks if the call is live and not muted
    if (!isCallActive || isMuted) {
      return;
    }

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
      const userSettingThreshold = parseFloat(prefSensitivity.value) / 1000;
      // Set calibratedThreshold: at least the user's slider setting, or 1.8x the ambient noise level
      calibratedThreshold = Math.max(userSettingThreshold, avgAmbient * 1.8);
      ambientSamples = []; // Clear to signal calibration is done
      console.log(`[VAD Calibrated] Ambient Avg: ${avgAmbient.toFixed(4)} | Threshold Set To: ${calibratedThreshold.toFixed(4)}`);
    }

    // Disable barge-in / interruption during AI speech to ensure a robust two-way connection
    if (callBody.classList.contains("state-speaking")) {
      return;
    }

    // Normal user speech capture VAD (only when state is listening and we are recording)
    if (!isRecording || !callBody.classList.contains("state-listening")) {
      return;
    }

    // Use calibratedThreshold instead of static silenceThreshold
    if (rms > calibratedThreshold) {
      speechTicks++;
      if (speechTicks > 5 && !hasSpoken) { // ~225ms of active sound
        hasSpoken = true;
        vadActivityVal.textContent = "Speech Detected";
      }
      // Reset silence timer because they are currently speaking
      if (silenceStartTimer) {
        clearTimeout(silenceStartTimer);
        silenceStartTimer = null;
      }
    } else if (hasSpoken) {
      // User spoke but is now silent. Start countdown to submit
      if (!silenceStartTimer) {
        vadActivityVal.textContent = "Speech Paused...";
        silenceStartTimer = setTimeout(() => {
          // Submit if speech was detected (aligned with the speechTicks > 5 detection threshold)
          if (speechTicks > 5) {
            console.log("[Continuous VAD] Silence window reached. Triggering AI processing...");
            stopAndSubmitVoiceSegment();
          } else {
            console.log("[Continuous VAD] Discarded noise segment (" + speechTicks + " ticks).");
            hasSpoken = false;
            speechTicks = 0;
            vadActivityVal.textContent = "Monitoring";
          }
        }, SILENCE_DURATION_MS);
      }
    }
  };

  // Keep references to disconnect on shutdown
  stream.processor = processor;
  stream.source = source;
}

// Interrupt active AI speech on user barge-in (making it feel like a real 2-person talk)
function interruptAISpeech() {
  console.log("[Barge-in] User interrupted AI speech. Stopping playback...");
  if (activeAudio) {
    activeAudio.pause();
    activeAudio = null;
  }
  window.speechSynthesis.cancel();

  // Transition UI state back to listening
  transitionState("listening");
  logCallMessage("system", "Listening to you...");

  // Restart listening loop immediately with bargeIn flag enabled
  isRecording = false; 
  resumeListening(true);
}

// End recording of current speech segment and submit to API
async function stopAndSubmitVoiceSegment() {
  if (!isRecording) return;
  isRecording = false;

  transitionState("thinking");

  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
  }
}

// Initialize recording for the next user speech turn
async function resumeListening(bargeIn = false) {
  if (!isCallActive || isMuted || isRecording) return;
  isRecording = true;
  audioChunks = [];
  hasSpoken = bargeIn;
  silenceStartTimer = null;
  speechTicks = bargeIn ? 10 : 0;
  lastResumeTime = Date.now();
  ambientSamples = [];
  calibratedThreshold = 0.022;

  try {
    // Re-verify microphone stream
    if (!micStream || !micStream.active) {
      micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
      startVAD(micStream);
    }

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
      await submitCallPayload(audioBlob);
    };

    transitionState("listening");
    mediaRecorder.start();

  } catch (error) {
    console.error("Failed to resume continuous listening loop:", error);
    logCallMessage("system", "Microphone connection lost. Reconnecting...");
    transitionState("disconnected");
    hangUpCall();
  }
}

// Submit Audio Blob to voice-input endpoint
async function submitCallPayload(blob) {
  try {
    const formData = new FormData();
    formData.append("file", blob, "voice.webm");
    formData.append("session_id", session_id);
    formData.append("top_k", 3);
    formData.append("language", prefLanguage.value);

    const response = await fetch("/api/chat/voice-input", {
      method: "POST",
      body: formData
    });

    if (!response.ok) {
      throw new Error(`Voice pipeline returned error ${response.status}`);
    }

    const data = await response.json();

    // Log query and answer
    if (data.query) {
      logCallMessage("user", data.query);
    }
    if (data.answer) {
      logCallMessage("bot", data.answer);
    }

    // Playback Voice response (Feedback prevention active inside playback function)
    if (data.audio_base64) {
      playSpeechResponse(data.audio_base64, data.answer);
    } else if (data.answer) {
      speakBrowserSynthesisFallback(data.answer);
    } else {
      resumeListening();
    }

  } catch (error) {
    console.error("Failed to submit speech segment:", error);
    logCallMessage("bot", "Sorry, my systems had trouble routing that response. Let's continue.");
    // Auto-listen again after errors so call doesn't hang
    setTimeout(resumeListening, 1000);
  }
}

// Play Voice audio responses, pausing mic/VAD input while speaking
function playSpeechResponse(base64Data, textFallback = "") {
  // Clear any existing speech
  if (activeAudio) {
    activeAudio.pause();
    activeAudio = null;
  }
  window.speechSynthesis.cancel();

  const audioUrl = `data:audio/mp3;base64,${base64Data}`;
  activeAudio = new Audio(audioUrl);

  activeAudio.onplay = () => {
    transitionState("speaking");
  };

  activeAudio.onended = () => {
    activeAudio = null;
    console.log("[Continuous Call] Audio response complete. Resuming microphone...");
    if (isCallActive && !isMuted) {
      resumeListening();
    } else if (isMuted) {
      transitionState("muted");
    }
  };

  activeAudio.onerror = (e) => {
    console.warn("Audio element error. Falling back to Browser TTS...", e);
    activeAudio = null;
    if (textFallback) {
      speakBrowserSynthesisFallback(textFallback);
    } else {
      resumeListening();
    }
  };

  activeAudio.play().catch(err => {
    console.warn("Autoplay block / playback abort:", err);
    activeAudio = null;
    if (textFallback) {
      speakBrowserSynthesisFallback(textFallback);
    } else {
      resumeListening();
    }
  });
}

// Speech fallback using Web Speech API SpeechSynthesis
function speakBrowserSynthesisFallback(text) {
  if (activeAudio) {
    activeAudio.pause();
    activeAudio = null;
  }
  window.speechSynthesis.cancel();

  // Strip formatting
  const cleanText = text
    .replace(/\*\*/g, "")
    .replace(/\*/g, "")
    .replace(/-\s/g, "")
    .replace(/#+/g, "")
    .replace(/\n/g, " ")
    .trim();

  if (!cleanText) {
    resumeListening();
    return;
  }

  const utterance = new SpeechSynthesisUtterance(cleanText);
  const voices = window.speechSynthesis.getVoices();
  
  // Preferred language route
  const selectedLang = prefLanguage.value;
  const targetVoice = voices.find(v => v.lang === selectedLang) || 
                      voices.find(v => v.lang === "hi-IN" || v.lang === "en-IN") ||
                      voices.find(v => v.lang.startsWith("en"));

  if (targetVoice) {
    utterance.voice = targetVoice;
  }

  utterance.onstart = () => {
    transitionState("speaking");
  };

  utterance.onend = () => {
    console.log("[Continuous Call] Browser Synthesis complete. Resuming microphone...");
    if (isCallActive && !isMuted) {
      resumeListening();
    } else if (isMuted) {
      transitionState("muted");
    }
  };

  utterance.onerror = (e) => {
    console.error("SpeechSynthesisUtterance error:", e);
    resumeListening();
  };

  window.speechSynthesis.speak(utterance);
}

// Start Call Conversation
async function startCall() {
  if (isCallActive) return;
  
  transitionState("connecting");
  session_id = "voice_call_" + Math.random().toString(36).substring(2, 11);
  isCallActive = true;
  isMuted = false;
  btnMute.disabled = false;
  btnMute.classList.remove("active-toggle");

  // Swap icon and hover classes on Start/Hangup button
  btnCallTrigger.className = "control-btn btn-hangup";
  btnCallTrigger.title = "End Conversation";
  callBtnIcon.innerHTML = `<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M10.68 13.31a16 16 0 0 0 3.41 2.6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91" style="transform: rotate(135deg); transform-origin: center;"></path>
  </svg>`;

  logCallMessage("system", "Connecting live line to Trvios travel agent...");

  try {
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      }
    });
    
    // Play synthetic chime
    playSyntheticChime("connect");
    
    startVAD(micStream);
    lastResumeTime = Date.now();
    ambientSamples = [];
    calibratedThreshold = 0.022;
    startTimer();
    startVisualizer();
    
    // Clear back-end history for a fresh session
    fetch(`/api/chat/clear?session_id=${session_id}`, { method: "POST" }).catch(err => console.warn(err));

    logCallMessage("system", "Line connected. Start speaking hands-free.");
    
    // Quick welcome greeting
    const welcome = "Welcome to your Trvios AI Voice Call. How can I help you plan your itinerary today?";
    logCallMessage("bot", welcome);
    speakBrowserSynthesisFallback(welcome);

  } catch (error) {
    console.error("Microphone access denied or audio startup failed:", error);
    alert("Microphone Access Error:\n\n" + error.name + ": " + error.message + "\n\nPlease click the microphone icon in your browser address bar to allow microphone access. Note that browsers only permit microphone usage over localhost or secure HTTPS connections.");
    logCallMessage("system", "Microphone access denied. Please grant permission to start call.");
    hangUpCall();
  }
}

// Disconnect/Hang Up Call
function hangUpCall() {
  if (!isCallActive) return;
  isCallActive = false;
  isRecording = false;

  playSyntheticChime("disconnect");
  stopTimer();
  stopVisualizer();

  // Reset button state
  btnCallTrigger.className = "control-btn btn-start";
  btnCallTrigger.title = "Start Call";
  btnMute.disabled = true;
  btnMute.classList.remove("active-toggle");
  
  callBtnIcon.innerHTML = `<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path>
  </svg>`;

  // Stop active speech playback
  if (activeAudio) {
    activeAudio.pause();
    activeAudio = null;
  }
  window.speechSynthesis.cancel();

  // Clean up streams & processors
  if (micStream) {
    if (micStream.processor) {
      micStream.processor.disconnect();
    }
    if (micStream.source) {
      micStream.source.disconnect();
    }
    micStream.getTracks().forEach(track => track.stop());
    micStream = null;
  }

  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    try {
      mediaRecorder.stop();
    } catch(e) {}
    mediaRecorder = null;
  }

  if (silenceStartTimer) {
    clearTimeout(silenceStartTimer);
    silenceStartTimer = null;
  }
  speechTicks = 0;

  logCallMessage("system", "Call ended. Session closed.");
  transitionState("disconnected");
}

// Mute Toggle handler
function toggleMute() {
  if (!isCallActive) return;
  isMuted = !isMuted;

  if (isMuted) {
    btnMute.classList.add("active-toggle");
    btnMute.title = "Unmute Microphone";
    logCallMessage("system", "Microphone muted.");
    transitionState("muted");
    
    // Stop recording
    if (isRecording) {
      isRecording = false;
      if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
      }
    }
  } else {
    btnMute.classList.remove("active-toggle");
    btnMute.title = "Mute Microphone";
    logCallMessage("system", "Microphone active.");
    
    // Re-engage listening VAD loop
    resumeListening();
  }
}

// DOM Event Listeners
btnCallTrigger.addEventListener("click", () => {
  if (isCallActive) {
    hangUpCall();
  } else {
    startCall();
  }
});

btnMute.addEventListener("click", toggleMute);

btnToggleDrawer.addEventListener("click", () => {
  const panel = document.getElementById("transcript-panel");
  panel.classList.toggle("hidden");
  const container = document.querySelector(".dashboard-container");
  if (container) {
    container.classList.toggle("sidebar-hidden");
  }
});

// Setup visualizer to draw initial status (silent circles)
startVisualizer();
transitionState("disconnected");

// Preload voices
window.speechSynthesis.getVoices();
if (window.speechSynthesis.onvoiceschanged !== undefined) {
  window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
}

// Global handler for interactive Place Card action buttons
window.handleCardAction = async function(action, name, type) {
  console.log(`[Card Action] Executing ${action} on ${name} (${type})`);
  
  if (action === 'calendar') {
    // Show premium visual chime alert
    alert(`📅 Added "${name}" (${type}) to your travel calendar!`);
    return;
  }
  
  // Construct instruction for swap or remove command
  let command = "";
  if (action === 'swap') {
    command = `Swap ${type} "${name}" with another matching alternative in my itinerary.`;
  } else if (action === 'remove') {
    command = `Remove ${type} "${name}" from my itinerary completely.`;
  }
  
  // Transition call state to thinking and log message
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
  }
  
  logCallMessage('user', command);
  transitionState("thinking");
  
  try {
    const formData = new FormData();
    formData.append("text_query", command);
    formData.append("session_id", session_id);
    formData.append("top_k", 3);
    formData.append("language", prefLanguage.value);

    const response = await fetch("/api/chat/voice-input", {
      method: "POST",
      body: formData
    });

    if (!response.ok) {
      throw new Error(`Voice pipeline card action returned error ${response.status}`);
    }

    const data = await response.json();

    if (data.answer) {
      logCallMessage("bot", data.answer);
    }

    // Speak response
    if (data.audio_base64) {
      playSpeechResponse(data.audio_base64, data.answer);
    } else if (data.answer) {
      speakBrowserSynthesisFallback(data.answer);
    } else {
      resumeListening();
    }
  } catch (error) {
    console.error("Failed to execute card action voice submit:", error);
    logCallMessage("bot", "Sorry, I had trouble updating your itinerary. Let's try again.");
    setTimeout(resumeListening, 1000);
  }
};
