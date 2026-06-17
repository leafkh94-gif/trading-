"""
scalp_dashboard.py
==================
Live web dashboard for Quick Swing signals.
Runs on Flask, auto-refreshes every 5 minutes.

Start with: python scalp_dashboard.py
Then open:  http://localhost:5000  (or your Render URL)

Add this file to your trading- repo root.
"""

from flask import Flask, jsonify, render_template_string
from apscheduler.schedulers.background import BackgroundScheduler
from quick_swing import run_scan, latest_signals, get_active_session
from datetime import datetime, timezone
import threading

app = Flask(__name__)
lock = threading.Lock()
last_scan_time = "Not yet run"

# ─────────────────────────────────────────────
# SCHEDULER — scan every 15 minutes
# ─────────────────────────────────────────────

def scheduled_scan():
    global last_scan_time
    with lock:
        run_scan()
        last_scan_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

scheduler = BackgroundScheduler()
scheduler.add_job(scheduled_scan, "interval", minutes=15, id="quick_swing_scan")
scheduler.start()

# Run once immediately on startup
scheduled_scan()


# ─────────────────────────────────────────────
# DASHBOARD HTML
# ─────────────────────────────────────────────

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="refresh" content="300">
  <title>Quick Swing Dashboard</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background: #0d0f14;
      color: #e0e0e0;
      font-family: 'Segoe UI', Arial, sans-serif;
      min-height: 100vh;
    }

    header {
      background: #141720;
      border-bottom: 2px solid #2a2d3e;
      padding: 18px 28px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    header h1 {
      font-size: 1.3rem;
      color: #f0c040;
      letter-spacing: 1px;
    }

    .session-badge {
      background: #1e2235;
      border: 1px solid #3a3f5c;
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 0.8rem;
      color: #a0b0d0;
    }

    .meta {
      text-align: center;
      padding: 12px;
      font-size: 0.78rem;
      color: #5a6070;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 20px;
      padding: 24px;
      max-width: 1200px;
      margin: 0 auto;
    }

    .card {
      background: #141720;
      border-radius: 12px;
      border: 1px solid #2a2d3e;
      padding: 22px;
      transition: transform 0.2s;
    }
    .card:hover { transform: translateY(-2px); }

    .card.buy  { border-top: 3px solid #22c55e; }
    .card.sell { border-top: 3px solid #ef4444; }
    .card.none { border-top: 3px solid #3a3f5c; opacity: 0.6; }

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }

    .instrument {
      font-size: 1.1rem;
      font-weight: 700;
      color: #ffffff;
    }

    .direction-badge {
      padding: 4px 12px;
      border-radius: 20px;
      font-size: 0.78rem;
      font-weight: 700;
    }
    .direction-badge.buy  { background: #14532d; color: #22c55e; }
    .direction-badge.sell { background: #450a0a; color: #ef4444; }
    .direction-badge.none { background: #1e2235; color: #5a6070; }

    .row {
      display: flex;
      justify-content: space-between;
      padding: 7px 0;
      border-bottom: 1px solid #1e2235;
      font-size: 0.87rem;
    }
    .row:last-child { border-bottom: none; }

    .label { color: #7080a0; }
    .value { color: #ffffff; font-weight: 600; }
    .value.green { color: #22c55e; }
    .value.red   { color: #ef4444; }
    .value.gold  { color: #f0c040; }

    .rr-bar {
      height: 4px;
      background: #1e2235;
      border-radius: 2px;
      margin-top: 6px;
    }
    .rr-fill {
      height: 100%;
      background: #f0c040;
      border-radius: 2px;
    }

    .no-signal {
      text-align: center;
      padding: 30px 0;
      color: #3a4060;
      font-size: 0.9rem;
    }

    .refresh-btn {
      display: block;
      margin: 0 auto 24px;
      background: #f0c040;
      color: #0d0f14;
      border: none;
      padding: 10px 28px;
      border-radius: 20px;
      font-size: 0.85rem;
      font-weight: 700;
      cursor: pointer;
    }
    .refresh-btn:hover { background: #ffd700; }

    .disclaimer {
      text-align: center;
      padding: 16px;
      font-size: 0.72rem;
      color: #3a4060;
    }
  </style>
</head>
<body>

<header>
  <h1>⚡ Quick Swing Dashboard</h1>
  <span class="session-badge" id="session">Loading...</span>
</header>

<div class="meta" id="meta">Last scan: checking...</div>

<div class="grid" id="grid">Loading signals...</div>

<div style="text-align:center; padding: 10px;">
  <button class="refresh-btn" onclick="fetchSignals()">🔄 Refresh Now</button>
</div>

<div class="disclaimer">
  ⚠️ Not financial advice. Always manage your own risk.
  &nbsp;|&nbsp; Auto-refreshes every 5 min
</div>

<script>
const INSTRUMENTS = ["GOLD", "US500", "US100", "US30"];

async function fetchSignals() {
  const res  = await fetch("/api/signals");
  const data = await res.json();

  document.getElementById("session").textContent = "📍 " + data.session;
  document.getElementById("meta").textContent    = "Last scan: " + data.last_scan;

  const grid = document.getElementById("grid");
  grid.innerHTML = "";

  for (const name of INSTRUMENTS) {
    const s = data.signals[name];
    const card = document.createElement("div");

    if (!s) {
      card.className = "card none";
      card.innerHTML = `
        <div class="card-header">
          <span class="instrument">${name}</span>
          <span class="direction-badge none">NO SIGNAL</span>
        </div>
        <div class="no-signal">⏭️ No setup detected<br>Waiting for next scan...</div>
      `;
    } else {
      const isBuy   = s.direction === "BUY";
      const rrPct   = Math.min((s.rr / 3) * 100, 100);
      card.className = "card " + s.direction.toLowerCase();
      card.innerHTML = `
        <div class="card-header">
          <span class="instrument">${name}</span>
          <span class="direction-badge ${isBuy ? 'buy' : 'sell'}">${isBuy ? '⬆️ BUY' : '⬇️ SELL'}</span>
        </div>
        <div class="row">
          <span class="label">Entry</span>
          <span class="value">${s.entry}</span>
        </div>
        <div class="row">
          <span class="label">Stop Loss</span>
          <span class="value red">${s.sl}</span>
        </div>
        <div class="row">
          <span class="label">Take Profit</span>
          <span class="value green">${s.tp}</span>
        </div>
        <div class="row">
          <span class="label">R:R Ratio</span>
          <span class="value gold">1 : ${s.rr}</span>
        </div>
        <div class="rr-bar"><div class="rr-fill" style="width:${rrPct}%"></div></div>
        <div class="row" style="margin-top:10px">
          <span class="label">RSI</span>
          <span class="value">${s.rsi}</span>
        </div>
        <div class="row">
          <span class="label">Candle Body</span>
          <span class="value">${s.candle_strength}%</span>
        </div>
        <div class="row">
          <span class="label">Session</span>
          <span class="value">${s.session}</span>
        </div>
        <div class="row">
          <span class="label">Time</span>
          <span class="value" style="font-size:0.78rem">${s.timestamp}</span>
        </div>
      `;
    }
    grid.appendChild(card);
  }
}

fetchSignals();
setInterval(fetchSignals, 300000); // refresh every 5 min
</script>
</body>
</html>
"""


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@app.route("/")
def dashboard():
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/signals")
def api_signals():
    return jsonify({
        "signals":   latest_signals,
        "session":   get_active_session(),
        "last_scan": last_scan_time,
    })


@app.route("/api/scan", methods=["POST"])
def api_manual_scan():
    """Trigger a manual scan (for testing)."""
    with lock:
        results = run_scan()
        return jsonify({"triggered": True, "signals_found": len(results)})


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
