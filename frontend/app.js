/* ==========================================================================
   J.A.R.V.I.S. HUD Core Controller
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
    // Generate a unique session ID for chat tracking
    const sessionId = "gui_sess_" + Math.random().toString(36).substring(2, 10);
    
    // Cache UI Elements
    const sseStatus = document.getElementById("sse-status");
    const voiceIndicator = document.getElementById("voice-indicator");
    const voiceStateText = document.getElementById("voice-state-text");
    const voiceStartBtn = document.getElementById("voice-start-btn");
    const voiceStopBtn = document.getElementById("voice-stop-btn");
    const chatLogs = document.getElementById("chat-logs");
    const chatInputForm = document.getElementById("chat-input-form");
    const chatInput = document.getElementById("chat-input");
    const agentPlansContainer = document.getElementById("agent-plans-container");
    
    // Settings elements
    const settingsToggleBtn = document.getElementById("settings-toggle-btn");
    const settingsModal = document.getElementById("settings-modal");
    const settingsCloseBtn = document.getElementById("settings-close-btn");
    const settingsForm = document.getElementById("settings-form");
    
    // Canvas visualizer details
    const canvas = document.getElementById("waveform-canvas");
    const ctx = canvas.getContext("2d");
    const visualizerOverlay = document.getElementById("visualizer-overlay");

    let voiceActive = false;
    let voiceState = "idle"; // idle, listening, processing, speaking
    let animationFrameId = null;
    let wavePhase = 0;

    // --- 1. Start Canvas Waveform Loop ---
    function drawWaveform() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        ctx.lineWidth = 2;
        ctx.strokeStyle = "#00f2fe";
        ctx.beginPath();
        
        const width = canvas.width;
        const height = canvas.height;
        const midY = height / 2;
        
        // Define wave parameters based on conversation states
        let amplitude = 0;
        let frequency = 0.02;
        let speed = 0.05;

        if (voiceState === "listening") {
            amplitude = 25;
            frequency = 0.04;
            speed = 0.15;
            visualizerOverlay.textContent = "LISTENING...";
            visualizerOverlay.style.color = "#00ff87";
        } else if (voiceState === "speaking") {
            amplitude = 35;
            frequency = 0.03;
            speed = 0.25;
            visualizerOverlay.textContent = "JARVIS SPEAKING";
            visualizerOverlay.style.color = "#00f2fe";
        } else if (voiceState === "processing") {
            amplitude = 8;
            frequency = 0.06;
            speed = 0.08;
            visualizerOverlay.textContent = "PROCESSING...";
            visualizerOverlay.style.color = "#4facfe";
        } else {
            amplitude = 2; // Flat line/noise
            frequency = 0.01;
            speed = 0.01;
            visualizerOverlay.textContent = voiceActive ? "WAKE WORD ACTIVE" : "MIC INACTIVE";
            visualizerOverlay.style.color = "rgba(226, 241, 255, 0.6)";
        }
        
        for (let x = 0; x < width; x++) {
            // Apply sinusoidal calculation with fade-out envelopes at boundaries
            const envelope = Math.sin((x / width) * Math.PI);
            const y = midY + Math.sin(x * frequency + wavePhase) * amplitude * envelope;
            
            if (x === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        }
        
        ctx.stroke();
        
        // Draw secondary visual layers for advanced HUD aesthetic
        if (voiceState === "listening" || voiceState === "speaking") {
            ctx.strokeStyle = "rgba(79, 172, 254, 0.3)";
            ctx.lineWidth = 1;
            ctx.beginPath();
            for (let x = 0; x < width; x++) {
                const envelope = Math.sin((x / width) * Math.PI);
                const y = midY + Math.sin(x * (frequency * 1.5) - wavePhase) * (amplitude * 0.6) * envelope;
                if (x === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.stroke();
        }
        
        wavePhase += speed;
        animationFrameId = requestAnimationFrame(drawWaveform);
    }
    
    // Start drawing loops
    drawWaveform();

    // --- 2. Initialize Status & Configs ---
    async function loadStatus() {
        try {
            const res = await fetch("/gui/status");
            if (res.ok) {
                const data = await res.json();
                updateVoiceState(data.voice_active, data.voice_state);
                renderPlans(data.active_plans);
            }
        } catch (e) {
            console.error("Failed to load initial status:", e);
        }
    }
    
    async function loadSettings() {
        try {
            const res = await fetch("/gui/settings");
            if (res.ok) {
                const data = await res.json();
                document.getElementById("wake-word-enabled").value = data.WAKE_WORD_ENABLED.toString();
                document.getElementById("wake-word-threshold").value = data.WAKE_WORD_THRESHOLD;
                document.getElementById("wake-word").value = data.WAKE_WORD;
                document.getElementById("voice-name").value = data.VOICE_NAME;
                document.getElementById("stt-provider").value = data.STT_PROVIDER;
                document.getElementById("tts-provider").value = data.TTS_PROVIDER;
                document.getElementById("stt-model").value = data.STT_MODEL;
            }
        } catch (e) {
            console.error("Failed to load settings configuration:", e);
        }
    }

    loadStatus();
    loadSettings();

    // --- 3. Connect Server-Sent Events (SSE) ---
    function connectSSE() {
        const eventSource = new EventSource("/gui/events");
        
        eventSource.onopen = () => {
            sseStatus.textContent = "CONNECTED";
            sseStatus.className = "stat-value text-green";
        };
        
        eventSource.onerror = () => {
            sseStatus.textContent = "DISCONNECTED";
            sseStatus.className = "stat-value text-red";
        };
        
        eventSource.onmessage = (event) => {
            try {
                const payload = JSON.parse(event.data);
                if (payload.type === "voice_status") {
                    updateVoiceState(payload.data.active, payload.data.state);
                } else if (payload.type === "agent_status") {
                    renderPlans([payload.data]);
                } else if (payload.type === "settings_updated") {
                    console.log("Settings changed in background:", payload.data);
                }
            } catch (e) {
                console.error("Failed to parse SSE payload:", e);
            }
        };
    }
    
    connectSSE();

    // --- 4. State Update Helper ---
    function updateVoiceState(active, state) {
        voiceActive = active;
        voiceState = state.toLowerCase();
        
        // Update glow indicators
        voiceIndicator.className = "voice-indicator-glow";
        if (active) {
            voiceIndicator.classList.add(voiceState);
            voiceStateText.textContent = voiceState.toUpperCase();
            
            voiceStartBtn.classList.add("hidden");
            voiceStopBtn.classList.remove("hidden");
        } else {
            voiceStateText.textContent = "INACTIVE";
            voiceStartBtn.classList.remove("hidden");
            voiceStopBtn.classList.add("hidden");
        }
    }

    // --- 5. UI Render Helper for Cognitive Plans ---
    function renderPlans(plans) {
        if (!plans || plans.length === 0) {
            agentPlansContainer.innerHTML = `<div class="no-plans-text">No active cognitive plans generated.</div>`;
            return;
        }
        
        agentPlansContainer.innerHTML = "";
        
        plans.forEach(plan => {
            const card = document.createElement("div");
            card.className = "plan-card";
            
            const badgeClass = plan.status.toLowerCase();
            
            card.innerHTML = `
                <div class="plan-card-header">
                    <span>PLAN: #${plan.plan_id.substring(0, 8)}</span>
                    <span class="plan-status-badge ${badgeClass}">${plan.status}</span>
                </div>
                <div class="plan-card-body">
                    <div class="plan-goal"><strong>GOAL:</strong> ${plan.goal}</div>
                    <ul class="plan-steps-list">
                        ${plan.steps.map(step => {
                            const stepClass = step.status.toLowerCase();
                            return `
                                <li class="step-item ${stepClass}">
                                    <div class="step-dot"></div>
                                    <div class="step-desc">
                                        <div><strong>Step ${step.step_id}:</strong> ${step.description}</div>
                                        ${step.selected_tool ? `<div class="step-tool text-cyan">Tool: ${step.selected_tool}</div>` : ""}
                                        ${step.error ? `<div class="step-error text-red">Error: ${step.error}</div>` : ""}
                                    </div>
                                </li>
                            `;
                        }).join("")}
                    </ul>
                </div>
            `;
            
            agentPlansContainer.appendChild(card);
        });
    }

    // --- 6. Voice Controls actions ---
    voiceStartBtn.addEventListener("click", async () => {
        try {
            await fetch("/gui/voice/start", { method: "POST" });
        } catch (e) {
            console.error("Error starting voice loop:", e);
        }
    });
    
    voiceStopBtn.addEventListener("click", async () => {
        try {
            await fetch("/gui/voice/stop", { method: "POST" });
        } catch (e) {
            console.error("Error stopping voice loop:", e);
        }
    });

    // --- 7. Chat Submission & Dialogue Rendering ---
    chatInputForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const msg = chatInput.value.trim();
        if (!msg) return;
        
        chatInput.value = "";
        appendMessage("user", "USER", msg);
        
        // Show temporary typing state
        const typingEl = appendMessage("jarvis", "JARVIS", "...");
        
        try {
            const res = await fetch("/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: msg,
                    session_id: sessionId,
                    is_voice: false
                })
            });
            
            if (res.ok) {
                const data = await res.json();
                typingEl.remove();
                appendMessage("jarvis", "JARVIS", data.response);
            } else {
                typingEl.remove();
                appendMessage("jarvis", "JARVIS", "Communication channel failure. Please verify settings.");
            }
        } catch (error) {
            typingEl.remove();
            appendMessage("jarvis", "JARVIS", "Failed to reach backend API. Offline.");
            console.error(error);
        }
    });
    
    function appendMessage(senderClass, label, text) {
        const msgDiv = document.createElement("div");
        msgDiv.className = `chat-message ${senderClass}`;
        
        const senderSpan = document.createElement("span");
        senderSpan.className = "message-sender";
        senderSpan.textContent = `${label}:`;
        
        const textP = document.createElement("p");
        textP.className = "message-text";
        textP.textContent = text;
        
        msgDiv.appendChild(senderSpan);
        msgDiv.appendChild(textP);
        
        chatLogs.appendChild(msgDiv);
        chatLogs.scrollTop = chatLogs.scrollHeight;
        
        return msgDiv;
    }

    // --- 8. Settings Sidebar Actions ---
    settingsToggleBtn.addEventListener("click", () => {
        settingsModal.classList.add("show");
    });
    
    settingsCloseBtn.addEventListener("click", () => {
        settingsModal.classList.remove("show");
    });
    
    // Close modal if user clicks background
    window.addEventListener("click", (e) => {
        if (e.target === settingsModal) {
            settingsModal.classList.remove("show");
        }
    });
    
    settingsForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const updates = {
            WAKE_WORD_ENABLED: document.getElementById("wake-word-enabled").value === "true",
            WAKE_WORD_THRESHOLD: parseFloat(document.getElementById("wake-word-threshold").value),
            WAKE_WORD: document.getElementById("wake-word").value,
            VOICE_NAME: document.getElementById("voice-name").value,
            VOICE_ENABLED: true, // Keep voice active
            STT_PROVIDER: document.getElementById("stt-provider").value,
            TTS_PROVIDER: document.getElementById("tts-provider").value,
            STT_MODEL: document.getElementById("stt-model").value
        };
        
        try {
            const res = await fetch("/gui/settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(updates)
            });
            if (res.ok) {
                settingsModal.classList.remove("show");
                loadStatus(); // refresh
            } else {
                const errData = await res.json();
                alert("Save Failed: " + (errData.detail || "Validation Error"));
            }
        } catch (error) {
            console.error("Error saving settings config:", error);
            alert("Connection error. Config not persisted.");
        }
    });
});
