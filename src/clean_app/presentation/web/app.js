const messagesEl = document.getElementById("messages");
const chatForm = document.getElementById("chat-form");
const queryInput = document.getElementById("query-input");
const topKSelect = document.getElementById("top-k");
const sendBtn = document.getElementById("send-btn");
const stopBtn = document.getElementById("stop-btn");
const indexBtn = document.getElementById("index-btn");
const statusPill = document.getElementById("status-pill");
const statusText = document.getElementById("status-text");

// Drawer elements
const drawerOverlay = document.getElementById("drawer-overlay");
const tripDrawer = document.getElementById("trip-drawer");
const drawerCloseBtn = document.getElementById("drawer-close-btn");

// Voice controls
const micBtn = document.getElementById("mic-btn");
const voiceToggle = document.getElementById("voice-toggle");

// New DOM elements
const bookingsBtn = document.getElementById("bookings-btn");
const recordingOverlay = document.getElementById("recording-overlay");
const recordingStopBtn = document.getElementById("recording-stop-btn");

let activeController = null;
let tripsCache = {};
let session_id = "session_" + Math.random().toString(36).substr(2, 9); // unique session ID per page load

// Speech synthesis / Audio playback states
let activeAudio = null;
let lastSpokenIndex = 0;

function setStatus(text, state = "ok") {
  statusText.textContent = text;
  statusPill.classList.remove("loading", "error");
  if (state === "loading") {
    statusPill.classList.add("loading");
  } else if (state === "error") {
    statusPill.classList.add("error");
  }
}

function setStreaming(isStreaming) {
  sendBtn.disabled = isStreaming;
  indexBtn.disabled = isStreaming;
  queryInput.disabled = isStreaming;
  topKSelect.disabled = isStreaming;
  stopBtn.classList.toggle("hidden", !isStreaming);
}

function appendMessage(role, content = "", options = {}) {
  const message = document.createElement("div");
  message.className = `message ${role}${options.error ? " error" : ""}`;

  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = role === "user" ? "You" : "Assistant";

  const body = document.createElement("div");
  body.className = "message-body";
  if (options.streaming) {
    body.classList.add("streaming");
  }
  body.innerHTML = content;

  message.append(label, body);
  messagesEl.appendChild(message);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  return { message, body };
}

function renderSources(container, sources) {
  if (!sources?.length) {
    return;
  }

  const sourcesEl = document.createElement("div");
  sourcesEl.className = "sources";

  for (const source of sources) {
    const chip = document.createElement("div");
    chip.className = "source-chip";
    chip.innerHTML = `
      <strong>${escapeHtml(source.title)}</strong>
      <span>${escapeHtml(source.destination)} <span class="score-tag">score ${source.score}</span></span>
    `;
    
    // Wire up drawer open on click
    chip.addEventListener("click", () => {
      openTripDrawer(source.id);
    });

    sourcesEl.appendChild(chip);
  }

  container.appendChild(sourcesEl);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function loadTripsIntoCache() {
  try {
    const response = await fetch("/api/trips");
    if (response.ok) {
      const trips = await response.json();
      for (const trip of trips) {
        tripsCache[trip.id] = trip;
      }
    }
  } catch (error) {
    console.error("Failed to load trips catalog cache:", error);
  }
}

async function openTripDrawer(tripId) {
  // Try loading cache if not already populated
  if (!tripsCache[tripId]) {
    await loadTripsIntoCache();
  }

  const trip = tripsCache[tripId];
  if (!trip) {
    console.warn("Trip detail unavailable in current database cache:", tripId);
    return;
  }

  const drawerTitle = document.getElementById("drawer-title");
  const drawerBody = document.getElementById("drawer-body");

  drawerTitle.textContent = "Trip Details";

  // Format highlights
  let highlightsHtml = "";
  if (trip.highlights && trip.highlights.length > 0) {
    highlightsHtml = `
      <h3 class="drawer-section-title">Highlights</h3>
      <ul style="margin-left: 20px; color: var(--muted); font-size: 0.95rem; margin-top: 8px;">
        ${trip.highlights.map(h => `<li>${escapeHtml(h)}</li>`).join("")}
      </ul>
    `;
  }

  // Format itinerary
  let itineraryHtml = "";
  if (trip.itinerary && trip.itinerary.length > 0) {
    itineraryHtml = `
      <h3 class="drawer-section-title">Day-by-Day Itinerary</h3>
      <div class="itinerary-timeline">
        ${trip.itinerary.map(item => `
          <div class="timeline-item">
            <div class="timeline-day">Day ${item.day}</div>
            <div class="timeline-title">${escapeHtml(item.title)}</div>
            <div class="timeline-desc">${escapeHtml(item.description)}</div>
            ${item.activities && item.activities.length > 0 ? `
              <div class="timeline-activities">
                ${item.activities.map(act => `<span class="activity-tag">${escapeHtml(act)}</span>`).join("")}
              </div>
            ` : ""}
          </div>
        `).join("")}
      </div>
    `;
  }

  drawerBody.innerHTML = `
    <div class="trip-details">
      <h2 style="font-family:'Plus Jakarta Sans', sans-serif; font-weight:700; color:#0f172a; margin-bottom:4px;">${escapeHtml(trip.title)}</h2>
      <div class="trip-badge-row">
        <span class="badge badge-primary">${escapeHtml(trip.destination)}</span>
        <span class="badge badge-secondary">${trip.duration_days} Days</span>
        <span class="badge badge-secondary">${escapeHtml(trip.start_date || 'Year-round')}</span>
      </div>

      <div class="trip-price-section" style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <div class="price-label">Price starting from</div>
          <div class="price-amount">${trip.currency === 'INR' ? '₹' : '$'}${trip.price.toLocaleString()}</div>
        </div>
        <button type="button" class="btn btn-primary" id="drawer-book-btn" style="padding:10px 18px; border-radius:10px;">Book Package</button>
      </div>

      <h3 class="drawer-section-title">Overview</h3>
      <p class="trip-desc-text">${escapeHtml(trip.description)}</p>

      ${highlightsHtml}
      ${itineraryHtml}
    </div>
  `;

  // Wire up inline booking button
  const bookBtn = document.getElementById("drawer-book-btn");
  bookBtn.addEventListener("click", () => {
    bookTrip(trip.id);
  });

  tripDrawer.classList.add("active");
  drawerOverlay.classList.add("active");
}

function closeTripDrawer() {
  tripDrawer.classList.remove("active");
  drawerOverlay.classList.remove("active");
}

/* Audio Player logic */
function stopSpeech() {
  if (activeAudio) {
    activeAudio.pause();
    activeAudio = null;
  }
}

// Fallback browser speech synthesis if backend TTS is unavailable/fails
function speakBrowserFallback(text) {
  if (!voiceToggle.checked || !text) {
    return;
  }
  if (activeAudio) {
    activeAudio.pause();
    activeAudio = null;
  }
  window.speechSynthesis.cancel();

  const cleanText = text
    .replace(/\*\*/g, "")
    .replace(/\*/g, "")
    .replace(/-\s/g, "")
    .replace(/#+/g, "")
    .replace(/\n/g, " ")
    .trim();

  if (!cleanText) {
    return;
  }

  const utterance = new SpeechSynthesisUtterance(cleanText);

  // Try to find a nice Indian or English voice
  const voices = window.speechSynthesis.getVoices();
  const targetVoice = voices.find(v => v.lang === "hi-IN" || v.lang === "en-IN") || voices.find(v => v.lang.startsWith("en"));
  if (targetVoice) {
    utterance.voice = targetVoice;
  }

  window.speechSynthesis.speak(utterance);
}

function playSpeech(base64Audio, textFallback = "") {
  if (!voiceToggle.checked) {
    return;
  }
  stopSpeech();
  
  if (!base64Audio) {
    if (textFallback) {
      speakBrowserFallback(textFallback);
    }
    return;
  }
  
  const audioUrl = `data:audio/mp3;base64,${base64Audio}`;
  activeAudio = new Audio(audioUrl);
  activeAudio.play().catch(e => {
    console.warn("Audio play blocked by browser autoplay constraints:", e);
    if (textFallback) {
      speakBrowserFallback(textFallback);
    }
  });
}

async function playSpeechForText(text) {
  if (!voiceToggle.checked || !text || !text.trim()) {
    return;
  }
  stopSpeech();
  
  const cleanText = text
    .replace(/\*\*/g, "")
    .replace(/\n/g, " ")
    .replace(/-\s/g, "")
    .replace(/#+/g, "")
    .trim();

  if (!cleanText) return;
  
  try {
    const response = await fetch(`/api/chat/tts?text=${encodeURIComponent(cleanText)}`);
    if (response.ok) {
      const blob = await response.blob();
      const audioUrl = URL.createObjectURL(blob);
      activeAudio = new Audio(audioUrl);
      activeAudio.play().catch(e => {
        console.warn("Audio play failed, falling back to browser TTS:", e);
        speakBrowserFallback(cleanText);
      });
    } else {
      console.warn("Backend TTS returned non-ok response, falling back to browser TTS");
      speakBrowserFallback(cleanText);
    }
  } catch (error) {
    console.error("TTS request failed, falling back to browser TTS:", error);
    speakBrowserFallback(cleanText);
  }
}

/* Collapsible AI diagnostics details block */
function appendAiMetadata(bodyEl, intent, entities, validation) {
  const metaBox = document.createElement("div");
  metaBox.className = "ai-meta-box";
  
  const entitiesList = [];
  if (entities.destination) entitiesList.push(`Dest: <span class="ai-meta-tag">${escapeHtml(entities.destination)}</span>`);
  if (entities.max_budget) entitiesList.push(`Budget: <span class="ai-meta-tag">₹${escapeHtml(entities.max_budget)}</span>`);
  if (entities.duration_days) entitiesList.push(`Duration: <span class="ai-meta-tag">${escapeHtml(entities.duration_days)}d</span>`);
  if (entities.activities?.length) entitiesList.push(`Tags: <span class="ai-meta-tag">${escapeHtml(entities.activities.join(","))}</span>`);
  if (entities.trip_id) entitiesList.push(`TripRef: <span class="ai-meta-tag">${escapeHtml(entities.trip_id)}</span>`);
  
  const entitiesStr = entitiesList.length ? entitiesList.join(" | ") : "none";
  
  const safetyClass = validation.safety_ok ? "ok" : "flagged";
  const safetyText = validation.safety_ok ? "Passed" : "Flagged";
  const hallucinationClass = validation.hallucination_flagged ? "flagged" : "ok";
  const hallucinationText = validation.hallucination_flagged ? "Flagged" : "Passed";

  metaBox.innerHTML = `
    <div class="ai-meta-header" style="display:flex; justify-content:space-between; font-weight:700;">
      <span>🔍 AI Thought Logs</span>
      <span style="cursor:pointer; font-size:0.75rem; text-decoration:underline;">Toggle</span>
    </div>
    <div class="ai-meta-details">
      <div style="margin-top:6px;">
        <strong>Detected Intent:</strong> <span class="ai-meta-tag" style="background:rgba(16,185,129,0.1); color:var(--success);">${escapeHtml(intent)}</span>
      </div>
      <div style="margin-top:4px;">
        <strong>NER entities:</strong> ${entitiesStr}
      </div>
      <div style="margin-top:4px; display:flex; gap:10px;">
        <span><strong>Safety Check:</strong> <span class="validation-tag ${safetyClass}">${safetyText}</span></span>
        <span><strong>Grounded RAG:</strong> <span class="validation-tag ${hallucinationClass}">${hallucinationText}</span></span>
      </div>
    </div>
  `;
  
  // Wire toggle
  const header = metaBox.querySelector(".ai-meta-header");
  header.addEventListener("click", () => {
    metaBox.querySelector(".ai-meta-details").classList.toggle("active");
  });
  
  bodyEl.appendChild(metaBox);
}

async function refreshHealth() {
  try {
    const response = await fetch("/health");
    if (!response.ok) {
      throw new Error("Health check failed");
    }
    const payload = await response.json();
    setStatus(`${payload.indexed_trips} trips indexed`, "ok");
    // Pre-populate trips cache
    loadTripsIntoCache();
  } catch (error) {
    setStatus("API offline", "error");
    console.error(error);
  }
}

async function indexTrips() {
  setStatus("Syncing Catalog…", "loading");
  indexBtn.disabled = true;

  try {
    const response = await fetch("/api/trips/index", { method: "POST" });
    if (!response.ok) {
      throw new Error("Indexing failed");
    }
    const payload = await response.json();
    setStatus(`${payload.total_in_store} trips indexed`, "ok");
    // Reload cache
    await loadTripsIntoCache();
  } catch (error) {
    setStatus("Syncing failed", "error");
    appendMessage("assistant", "Could not synchronize catalog. Check backend logs.", {
      error: true,
    });
    console.error(error);
  } finally {
    indexBtn.disabled = false;
  }
}

/* Book trip backend caller */
async function bookTrip(tripId) {
  try {
    const response = await fetch("/api/bookings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trip_id: tripId, customer_name: "Explorer User" })
    });
    if (response.ok) {
      const booking = await response.json();
      appendMessage("assistant", `🎉 **Booking Confirmed!**\n\nI have successfully reserved your slot for **${booking.trip_title}**. Booking Code: **${booking.id}**.`);
      closeTripDrawer();
      openBookingsDrawer(); // reveal bookings list
    } else {
      const err = await response.json();
      alert(`Booking failed: ${err.detail || 'Server error'}`);
    }
  } catch (error) {
    console.error(error);
    alert("Could not process booking request.");
  }
}

/* List Bookings in drawer */
async function openBookingsDrawer() {
  const drawerTitle = document.getElementById("drawer-title");
  const drawerBody = document.getElementById("drawer-body");

  drawerTitle.textContent = "My Bookings";
  drawerBody.innerHTML = `<div style="text-align:center; color:var(--muted); margin-top:30px;">Loading bookings...</div>`;

  tripDrawer.classList.add("active");
  drawerOverlay.classList.add("active");

  try {
    const response = await fetch("/api/bookings");
    if (!response.ok) throw new Error("Could not fetch bookings");
    
    const bookings = await response.json();
    if (!bookings.length) {
      drawerBody.innerHTML = `
        <div style="text-align:center; color:var(--muted); margin-top:40px; font-size:0.95rem;">
          <svg viewBox="0 0 24 24" width="48" height="48" stroke="currentColor" stroke-width="1.5" fill="none" style="opacity:0.4; margin-bottom:12px;">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
            <line x1="16" y1="13" x2="8" y2="13"></line>
            <line x1="16" y1="17" x2="8" y2="17"></line>
            <polyline points="10 9 9 9 8 9"></polyline>
          </svg>
          <p>No trip bookings registered yet.</p>
        </div>
      `;
      return;
    }

    drawerBody.innerHTML = `
      <div class="booking-list">
        ${bookings.map(b => `
          <div class="booking-card">
            <div class="booking-card-header">
              <span>Code: ${escapeHtml(b.id)}</span>
              <span>Date: ${escapeHtml(b.booking_date)}</span>
            </div>
            <div class="booking-card-title">${escapeHtml(b.trip_title)}</div>
            <div class="booking-card-footer">
              <span class="booking-card-price">₹${b.price.toLocaleString()}</span>
              <span class="booking-badge confirmed">${escapeHtml(b.status)}</span>
            </div>
          </div>
        `).join("")}
      </div>
    `;
  } catch (error) {
    drawerBody.innerHTML = `<div style="text-align:center; color:var(--danger); margin-top:30px;">Error loading bookings.</div>`;
    console.error(error);
  }
}

async function streamChat(query, topK) {
  activeController = new AbortController();
  setStreaming(true);
  stopSpeech();

  appendMessage("user", escapeHtml(query));
  const { message, body } = appendMessage("assistant", "", { streaming: true });

  let answer = "";
  let sources = [];
  
  // Pipeline metadata
  let metadata = null;
  let validation = null;

  try {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, top_k: Number(topK), session_id }),
      signal: activeController.signal,
    });

    if (!response.ok || !response.body) {
      throw new Error(`Chat request failed (${response.status})`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() ?? "";

      for (const chunk of chunks) {
        const line = chunk.trim();
        if (!line.startsWith("data: ")) {
          continue;
        }

        const event = JSON.parse(line.slice(6));

        if (event.type === "metadata") {
          metadata = event;
        }

        if (event.type === "sources") {
          sources = event.sources ?? [];
        }

        if (event.type === "token" && event.content) {
          answer += event.content;
          body.innerHTML = formatMarkdown(answer);
          messagesEl.scrollTop = messagesEl.scrollHeight;
        }

        if (event.type === "done") {
          sources = event.sources ?? sources;
          validation = event.validation ?? null;
        }
      }
    }

    body.classList.remove("streaming");
    if (!answer) {
      body.textContent = "No answer was returned.";
    } else {
      // Play speech if voiceReplies checked
      if (voiceToggle.checked) {
        playSpeechForText(answer);
      }
    }
    
    // Append cited sources
    renderSources(message, sources);
    
    // Append diagnostic details
    if (metadata && validation) {
      appendAiMetadata(body, metadata.intent, metadata.entities, validation);
    }
  } catch (error) {
    stopSpeech();
    body.classList.remove("streaming");
    if (error.name === "AbortError") {
      body.innerHTML = answer ? `${formatMarkdown(answer)}\n\n<em>[Generation Stopped]</em>` : "<em>[Generation Stopped]</em>";
    } else {
      message.classList.add("error");
      body.textContent = error.message || "An unexpected error occurred while streaming.";
      console.error(error);
    }
  } finally {
    activeController = null;
    setStreaming(false);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }
}

// Simple parser to format bold markdown, headers, bullet points, links, and custom cards/timelines to HTML
function formatMarkdown(text) {
  let html = escapeHtml(text);
  
  // Format bold **text** -> <strong>text</strong>
  html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  
  // Format links [text](url) -> <a href="url" target="_blank">text</a>
  html = html.replace(/\[(.*?)\]\((.*?)\)/g, (match, p1, p2) => {
    const cleanUrl = p2.replaceAll("&amp;", "&");
    return `<a href="${cleanUrl}" target="_blank" style="color: #22d3ee; text-decoration: underline; font-weight: 500; display: inline-flex; align-items: center; gap: 4px;">${p1} ↗</a>`;
  });

  const lines = html.split("\n");
  let inList = false;
  const processedLines = [];
  
  for (let line of lines) {
    const trimmed = line.trim();
    
    // Skip list wrapping for CARD or TIME tags
    if (trimmed.startsWith("[CARD:") || trimmed.startsWith("[TIME:")) {
      if (inList) {
        processedLines.push("</ul>");
        inList = false;
      }
      processedLines.push(trimmed);
      continue;
    }

    // Parse headers
    if (trimmed.startsWith("### ")) {
      if (inList) {
        processedLines.push("</ul>");
        inList = false;
      }
      processedLines.push(`<h4 style="color: #cbd5e1; margin-top: 14px; margin-bottom: 6px; font-weight: 600; font-size: 1.05rem;">${trimmed.slice(4)}</h4>`);
    } else if (trimmed.startsWith("## ")) {
      if (inList) {
        processedLines.push("</ul>");
        inList = false;
      }
      processedLines.push(`<h3 style="color: #f8fafc; margin-top: 18px; margin-bottom: 8px; font-weight: 700; font-size: 1.15rem; border-left: 3px solid #06b6d4; padding-left: 8px;">${trimmed.slice(3)}</h3>`);
    } else if (trimmed.startsWith("# ")) {
      if (inList) {
        processedLines.push("</ul>");
        inList = false;
      }
      processedLines.push(`<h2 style="color: #22d3ee; margin-top: 22px; margin-bottom: 10px; font-weight: 800; font-size: 1.3rem;">${trimmed.slice(2)}</h2>`);
    } else if (trimmed.startsWith("* ") || trimmed.startsWith("- ")) {
      if (!inList) {
        processedLines.push("<ul style='margin-left: 16px; margin-bottom: 8px;'>");
        inList = true;
      }
      processedLines.push(`<li style='margin-bottom: 4px;'>${trimmed.slice(2)}</li>`);
    } else {
      if (inList) {
        processedLines.push("</ul>");
        inList = false;
      }
      processedLines.push(line);
    }
  }
  if (inList) {
    processedLines.push("</ul>");
  }
  
  let result = processedLines.join("<br/>")
    .replace(/<br\/><ul>/g, "<ul>")
    .replace(/<\/ul><br\/>/g, "</ul>")
    .replace(/<br\/><h/g, "<h");

  // Parse CARD tags in final HTML
  result = result.replace(/\[CARD:\s*([\s\S]*?)\s*\]/g, (match, content) => {
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
  </div>
</div>
`;
    }
  });

  // Parse TRAVEL tags in final HTML
  result = result.replace(/\[TRAVEL:\s*([\s\S]*?)\s*\]/g, (match, content) => {
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

  // Parse TIME tags in final HTML (clean fallback)
  result = result.replace(/\[TIME:\s*(.*?)\s*\|\s*(.*?)\]/g, `
<div class="timeline-item">
  <div class="timeline-time">🕒 $1</div>
  <div class="timeline-content">$2</div>
</div>
`);

  // Parse ITINERARY_FORM tags in final HTML
  result = result.replace(/\[ITINERARY_FORM:\s*([\s\S]*?)\s*\]/g, (match, content) => {
    const parts = content.split("|");
    const data = {};
    for (let part of parts) {
      const idx = part.indexOf("=");
      if (idx !== -1) {
        const k = part.slice(0, idx).replace(/<br\s*\/?>/gi, "").trim().toLowerCase();
        const v = part.slice(idx + 1).replace(/<br\s*\/?>/gi, "").trim();
        data[k] = v;
      }
    }
    
    const destination = data.destination || "Manali";
    const days = data.days || "3";
    
    return `
<div class="itinerary-form-card">
  <h3>Configure Your ${destination} Trip Preferences</h3>
  <form class="trip-pref-form">
    <input type="hidden" name="destination" value="${destination}">
    
    <div class="form-row">
      <div class="form-group">
        <label>📅 Duration (Days)</label>
        <input type="number" name="days" value="${days}" min="1" max="15" required style="width: 100%;">
      </div>
      <div class="form-group">
        <label>👥 Travel Type</label>
        <select name="travel_type" style="width: 100%;">
          <option value="Solo">Solo</option>
          <option value="Couple" selected>Couple</option>
          <option value="Family">Family</option>
          <option value="Friends">Friends</option>
        </select>
      </div>
    </div>
    
    <div class="form-row" style="margin-top: 12px;">
      <div class="form-group">
        <label>🎯 Itinerary Style</label>
        <select name="style" style="width: 100%;">
          <option value="Relaxed">Relaxed (Paced & Calm)</option>
          <option value="Balanced" selected>Balanced (Standard)</option>
          <option value="Active">Active (Sightseeing heavy)</option>
          <option value="Adventure">Adventure (Action-focused)</option>
        </select>
      </div>
      <div class="form-group">
        <label>😊 Mood</label>
        <select name="mood" style="width: 100%;">
          <option value="Romantic">Romantic</option>
          <option value="Nature" selected>Nature</option>
          <option value="Fun">Fun</option>
          <option value="Peaceful">Peaceful</option>
          <option value="Photography">Photography</option>
        </select>
      </div>
    </div>
    
    <div class="form-row" style="margin-top: 12px;">
      <div class="form-group">
        <label>💰 Budget Preference</label>
        <select name="budget" style="width: 100%;">
          <option value="Budget">Budget</option>
          <option value="Mid-range" selected>Mid-range</option>
          <option value="Luxury">Luxury</option>
        </select>
      </div>
      <div class="form-group">
        <label>🚗 Transport Preference</label>
        <select name="transport" style="width: 100%;">
          <option value="Cab" selected>Cab (Chauffeur)</option>
          <option value="Bike">Bike (Motorcycle)</option>
          <option value="Self-drive">Self-drive Car</option>
          <option value="Walking">Walking / Public Transit</option>
        </select>
      </div>
    </div>
    
    <div class="form-row" style="margin-top: 12px;">
      <div class="form-group">
        <label>🏨 Stay Preference</label>
        <select name="stay" style="width: 100%;">
          <option value="Hotel" selected>Hotel</option>
          <option value="Resort">Resort</option>
          <option value="Homestay">Homestay</option>
        </select>
      </div>
      <div class="form-group">
        <label>🍽 Food Preference</label>
        <select name="food" style="width: 100%;">
          <option value="Veg" selected>Vegetarian</option>
          <option value="Non-Veg">Non-Vegetarian</option>
          <option value="Cafés">Cafés / Bakeries</option>
          <option value="Local Cuisine">Local Traditional Cuisine</option>
        </select>
      </div>
    </div>
    
    <div class="form-row" style="margin-top: 12px;">
      <div class="form-group" style="grid-column: span 2;">
        <label>🎢 Activity Preference</label>
        <select name="activity" style="width: 100%;">
          <option value="Sightseeing" selected>Sightseeing (Temples & Views)</option>
          <option value="Adventure">Adventure Sports</option>
          <option value="Shopping">Shopping & Local Bazaars</option>
          <option value="Waterfalls">Nature & Waterfalls</option>
          <option value="Cafés">Food & Café hopping</option>
        </select>
      </div>
    </div>
    
    <button type="submit" class="generate-btn">✨ Generate My Custom Itinerary</button>
  </form>
</div>
`;
  });

  // Clean up excessive linebreaks around cards and timelines
  result = result.replace(/<br\/>\s*<div class="place-card">/g, '<div class="place-card">')
                 .replace(/<\/div>\s*<br\/>\s*<div class="place-card">/g, '</div><div class="place-card">')
                 .replace(/<br\/>\s*<div class="travel-transition">/g, '<div class="travel-transition">')
                 .replace(/<\/div>\s*<br\/>\s*<div class="travel-transition">/g, '</div><div class="travel-transition">')
                 .replace(/<br\/>\s*<div class="timeline-item">/g, '<div class="timeline-item">')
                 .replace(/<\/div>\s*<br\/>\s*<div class="timeline-item">/g, '</div><div class="timeline-item">')
                 .replace(/<br\/>\s*<div class="itinerary-form-card">/g, '<div class="itinerary-form-card">')
                 .replace(/<\/div>\s*<br\/>\s*<div class="itinerary-form-card">/g, '</div><div class="itinerary-form-card">')
                 .replace(/<\/div>\s*<br\/>\s*<h/g, '</div><h');

  return result;
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = queryInput.value.trim();
  if (!query || activeController) {
    return;
  }

  queryInput.value = "";
  await streamChat(query, topKSelect.value);
});

stopBtn.addEventListener("click", () => {
  activeController?.abort();
  stopSpeech();
});

indexBtn.addEventListener("click", indexTrips);
bookingsBtn.addEventListener("click", openBookingsDrawer);

queryInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});

// Close drawer listeners
drawerCloseBtn.addEventListener("click", closeTripDrawer);
drawerOverlay.addEventListener("click", closeTripDrawer);

// Voice bot toggle listener
voiceToggle.addEventListener("change", () => {
  if (!voiceToggle.checked) {
    stopSpeech();
  }
});

// Custom Voice Recording (Speech-to-Text via Whisper on Backend)
let mediaRecorder = null;
let audioChunks = [];

async function startRecording() {
  stopSpeech();
  audioChunks = [];
  
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    alert("Microphone access is not supported by your browser in this context.\n\nNote: Modern browsers require a Secure Context (HTTPS or localhost) to access hardware interfaces like the microphone.");
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    
    // Choose appropriate mimeType for maximum browser compatibility
    let options = { mimeType: 'audio/webm' };
    if (!MediaRecorder.isTypeSupported('audio/webm')) {
      options = { mimeType: 'audio/ogg' };
    }
    
    mediaRecorder = new MediaRecorder(stream, options);
    
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data);
      }
    };
    
    mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(audioChunks, { type: options.mimeType });
      // Clean up media tracks
      stream.getTracks().forEach(track => track.stop());
      
      // Upload recorded audio to Whisper transcription and chat pipeline
      await uploadVoiceAudio(audioBlob);
    };
    
    // Reveal visual overlay
    recordingOverlay.classList.add("active");
    mediaRecorder.start();
  } catch (error) {
    console.error("Microphone access denied or error:", error);
    alert("Could not start recording. Please make sure microphone permission is granted.");
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
  }
  recordingOverlay.classList.remove("active");
}

async function uploadVoiceAudio(blob) {
  setStreaming(true);
  
  // Append temporary user placeholder
  appendMessage("user", "🎙️ <em>[Voice Input Audio]</em>");
  const { message, body } = appendMessage("assistant", "Transcribing and thinking...", { streaming: true });

  try {
    const formData = new FormData();
    formData.append("file", blob, "voice.webm");
    formData.append("session_id", session_id);
    formData.append("top_k", topKSelect.value);

    const response = await fetch("/api/chat/voice-input", {
      method: "POST",
      body: formData
    });

    if (!response.ok) {
      throw new Error(`Voice submission failed: ${response.status}`);
    }

    const data = await response.json();

    // Update user query with transcribed query text
    const lastUserMsg = messagesEl.querySelector(".message.user:last-of-type .message-body");
    if (lastUserMsg) {
      lastUserMsg.innerHTML = `🎙️ ${escapeHtml(data.query)}`;
    }

    // Output answer
    body.classList.remove("streaming");
    body.innerHTML = formatMarkdown(data.answer);
    
    // Play voice reply
    if (voiceToggle.checked) {
      playSpeech(data.audio_base64, data.answer);
    }

    // Render citations
    renderSources(message, data.sources);

    // Render diagnostics Accordion
    appendAiMetadata(body, data.intent, data.entities, data.validation);

  } catch (error) {
    body.classList.remove("streaming");
    message.classList.add("error");
    body.textContent = "Sorry, I could not transcribe or answer your voice message. Please check server logs.";
    console.error("Voice input upload error:", error);
  } finally {
    setStreaming(false);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }
}

// Wire voice recording triggers
micBtn.addEventListener("click", startRecording);
recordingStopBtn.addEventListener("click", stopRecording);

refreshHealth();

// Intercept preference form submissions to stream custom itinerary query back
document.addEventListener("submit", (e) => {
  const form = e.target.closest(".trip-pref-form");
  if (form) {
    e.preventDefault();
    const formData = new FormData(form);
    const dest = formData.get("destination");
    const days = formData.get("days");
    const travel_type = formData.get("travel_type");
    const style = formData.get("style");
    const mood = formData.get("mood");
    const budget = formData.get("budget");
    const transport = formData.get("transport");
    const stay = formData.get("stay");
    const food = formData.get("food");
    const activity = formData.get("activity");

    const submitMsg = `[ITINERARY_SUBMIT: destination=${dest} | days=${days} | travel_type=${travel_type} | style=${style} | mood=${mood} | budget=${budget} | transport=${transport} | stay=${stay} | food=${food} | activity=${activity}]`;
    
    // Trigger message streaming
    streamChat(submitMsg, topKSelect.value);
  }
});

