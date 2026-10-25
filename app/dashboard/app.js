// QuantPilot Dashboard Polling & UI Logic

const POLL_INTERVAL_MS = 2000;

async function fetchStatus() {
  try {
    const res = await fetch("/api/status");
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById("engine-state-text").innerText = data.engine_state;
    const dot = document.getElementById("engine-dot");
    dot.className = "dot";
    if (data.engine_state === "RUNNING") dot.classList.add("running");
    else if (data.engine_state === "HALTED") dot.classList.add("halted");

    document.getElementById("symbol-val").innerText = data.symbol;
    document.getElementById("profile-sub").innerText = `Profile: ${data.active_profile}`;
    document.getElementById("regime-val").innerText = data.current_regime;
    document.getElementById("allocator-val").innerText = data.allocated_strategy || "STAND-ASIDE";
  } catch (err) {
    console.error("Failed to poll status:", err);
  }
}

async function fetchHealth() {
  try {
    const res = await fetch("/api/health");
    if (!res.ok) return;
    const data = await res.json();
    document.getElementById("health-val").innerText = data.status.toUpperCase();
    document.getElementById("drift-sub").innerText = `Clock Drift: ${data.clock_drift_seconds}s`;
  } catch (err) {
    console.error("Failed to poll health:", err);
  }
}

async function fetchDecisions() {
  try {
    const res = await fetch("/api/decisions?limit=5");
    if (!res.ok) return;
    const data = await res.json();
    const feed = document.getElementById("journal-feed");
    if (!data.decisions || data.decisions.length === 0) {
      feed.innerHTML = '<p class="placeholder-text">Listening for candle-close decisions...</p>';
      return;
    }

    feed.innerHTML = data.decisions
      .map(
        (d) => `
      <div class="journal-item">
        <div class="journal-header">
          <span><strong>Decision ${d.decision_id.slice(0, 8)}</strong> (${d.symbol} ${d.timeframe})</span>
          <span>${new Date(d.timestamp).toLocaleTimeString()}</span>
        </div>
        <div class="journal-narrative">${d.narrative}</div>
      </div>
    `
      )
      .join("");
  } catch (err) {
    console.error("Failed to poll decisions:", err);
  }
}

// Kill Switch Modal Handlers
const killBtn = document.getElementById("kill-btn");
const killModal = document.getElementById("kill-modal");
const cancelKill = document.getElementById("cancel-kill");
const confirmKill = document.getElementById("confirm-kill");
const secretInput = document.getElementById("secret-input");

killBtn.addEventListener("click", () => killModal.classList.remove("hidden"));
cancelKill.addEventListener("click", () => killModal.classList.add("hidden"));

confirmKill.addEventListener("click", async () => {
  const secret = secretInput.value.trim();
  if (!secret) {
    alert("Please enter the X-Control-Secret");
    return;
  }

  try {
    const res = await fetch("/api/control/kill", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Control-Secret": secret,
      },
      body: JSON.stringify({ reason: "Emergency kill triggered from dashboard UI" }),
    });

    if (res.ok) {
      alert("🚨 Trading halted! Positions closing via reduce-only.");
      killModal.classList.add("hidden");
      secretInput.value = "";
      fetchStatus();
    } else {
      const err = await res.json();
      alert(`Kill switch failed: ${err.detail || "Authentication error"}`);
    }
  } catch (err) {
    alert("Network error executing kill switch.");
  }
});

// Periodic polling
setInterval(() => {
  fetchStatus();
  fetchHealth();
  fetchDecisions();
}, POLL_INTERVAL_MS);

// Initial call
fetchStatus();
fetchHealth();
fetchDecisions();
