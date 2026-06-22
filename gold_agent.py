"""
Trading AI — Chat + Live Market Analysis
Type a question, attach any chart, or ask it to analyze any market live.
Pulls real-time data from your Capital.com account for any instrument.
Run:  python gold_agent.py
Open: http://localhost:5000
"""

import base64, os, pathlib, json
from flask import Flask, request, jsonify
import anthropic

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# ── Load .env from the same folder as this script ─────────────────────────────
# Built-in parser: handles UTF-8 BOM (PowerShell Out-File adds one) and quotes.
def _load_env():
    env_path = pathlib.Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip().lstrip("﻿")
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception as e:
        print(f"  Could not read .env: {e}")

_load_env()

API_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
CAP_KEY   = os.environ.get("CAPITAL_API_KEY", "")
CAP_PASS  = os.environ.get("CAPITAL_PASSWORD", "")
CAP_EMAIL = os.environ.get("CAPITAL_EMAIL", "")

# Try demo first (most users scan on a demo account), then live.
CAP_BASES = [
    "https://demo-api-capital.backend-capital.com/api/v1",
    "https://api-capital.backend-capital.com/api/v1",
]
_cap = {"cst": None, "sec": None, "base": None}

conversation = []

SYSTEM = """You are an elite professional trading analyst using a hybrid SMC/ICT framework. You grade every setup on a 4-level scale: A+ / A / WATCH / NO TRADE. You cover Gold, US100, US500, US30, forex, and crypto.

━━ THE 3 GATES (assessed per setup — their status determines the grade) ━━

GATE 1 — HTF STRUCTURE ALIGNMENT (hard rule — if this fails, maximum grade is NO TRADE)
Trade direction must match the higher-timeframe bias. Identify BOS (Break of Structure) and CHoCH (Change of Character). A bearish entry on a bullish HTF = NO TRADE regardless of anything else.

GATE 2 — SESSION QUALITY (affects grade, not a hard block)
• Gold: Primary = London (07:00–10:00 GMT) + NY (13:30–16:00 GMT). Secondary = any other hours. Outside primary sessions, downgrade the setup by one grade level. Gold is driven by real yields, not just DXY — treat them as separate signals.
• US100/US500/US30: Primary = NY cash open (13:30–16:30 GMT). Secondary = London open (07:00–09:00 GMT via futures). Outside both = downgrade one level. Asia/pre-market moves exist but need extra confluence.

GATE 3 — NEWS FILTER (affects grade, not a hard block)
• High-impact news within 15 min either side = NO TRADE (too close).
• High-impact news within 15–30 min = maximum grade is WATCH (flag setup, wait for clearance).
• News cleared = no grade penalty.
For Gold: CPI, FOMC, NFP, DXY events, geopolitics. For indices: same + earnings (especially mega-cap tech for US100), Fed speakers.

━━ THE 6 CONFLUENCE CONDITIONS (scored 0–6) ━━

1. TRIGGER CANDLE — Engulfing, liquidity sweep/fakeout (wick through level then close back), or strong rejection candle.
2. ORDER BLOCK or FAIR VALUE GAP — Price returning to an unfilled imbalance or origin of a prior impulse.
3. STRUCTURE EVENT — Confirmed BOS or CHoCH on the entry timeframe in the trade direction.
4. FIBONACCI LEVEL — Entry within the 0.618–0.79 retracement of the most recent impulse.
5. MOMENTUM — RSI divergence, candle body expansion in trade direction, or volume spike on the trigger.
6. S/R or LIQUIDITY LEVEL — Prior swing high/low, equal highs/lows (liquidity pool), or key round number.

━━ GRADING SYSTEM ━━

🏆 A+ SETUP — Enter now, highest conviction
   Gate 1 ✓ | Primary session ✓ | News clear ✓ | Confluence ≥ 5/6

✅ A SETUP — Solid trade, enter
   Gate 1 ✓ | Session OK (primary or secondary) | News clear ✓ | Confluence 3–4/6

👀 WATCH — Setup forming, not ready yet — set alert
   Gate 1 ✓ | Session secondary or pending | OR news within 15–30 min | OR confluence 2–3/6 but building
   → Tell user what needs to happen for it to upgrade to A or A+

❌ NO TRADE — Nothing actionable
   Gate 1 fails | OR news within 15 min | OR confluence < 2/6 | OR structure is choppy/unclear

━━ INSTRUMENT-SPECIFIC RULES ━━

ATR/STOP-LOSS: Never copy ATR distances across instruments. US100 beta is ~1.2–1.3 vs S&P (moves 20–30% more). US30 has large nominal point values — "tight" in % may be wide in points. Always derive SL from the instrument's own recent ATR and the structure invalidation level.

CORRELATION TRAP: US500/US100/US30 share mega-cap tech and are highly correlated. Same signal on all three = one trade at triple size, not three independent trades. Flag this explicitly when it happens. Gold trades independently.

R:R: A+ and A setups must show R:R ≥ 1:2. Flag if R:R < 1:2 — do not present the trade.

━━ OUTPUT FORMAT ━━

Grade: [🏆 A+ / ✅ A / 👀 WATCH / ❌ NO TRADE]
HTF Bias: [Bullish / Bearish / Ranging]
Gates: G1 [✓/✗] | G2 Session [Primary/Secondary/Outside] | G3 News [Clear/Caution/Block]
Confluence: [X]/6 — [list which conditions are met]

For A+ and A:
→ Direction: BUY / SELL
→ Entry: [price]
→ Stop-Loss: [price] (~[X] ATR)
→ Target 1: [price] | Target 2: [price] | R:R: [ratio]
→ Invalidation: [specific price/condition that cancels the setup]

For WATCH:
→ What to wait for: [specific trigger — e.g. "NY session open", "NFP clears in 20 min", "needs BOS confirmation on 15m"]
→ If triggered, expected grade: [A+ / A]

For NO TRADE:
→ Reason: [specific — wrong HTF, no confluence, news block, choppy structure]

You have a live market data tool — use it proactively for any real-time request. When the user attaches a chart, analyze it directly using the same framework. Remember the full conversation."""


# ── Capital.com live data ─────────────────────────────────────────────────────
def cap_login():
    if not (HAS_REQUESTS and CAP_KEY and CAP_PASS and CAP_EMAIL):
        return False
    for base in CAP_BASES:
        try:
            r = requests.post(
                f"{base}/session",
                headers={"X-CAP-API-KEY": CAP_KEY, "Content-Type": "application/json"},
                json={"identifier": CAP_EMAIL, "password": CAP_PASS},
                timeout=12,
            )
            if r.status_code == 200:
                _cap["cst"]  = r.headers.get("CST")
                _cap["sec"]  = r.headers.get("X-SECURITY-TOKEN")
                _cap["base"] = base
                print(f"  Capital.com connected ({'demo' if 'demo' in base else 'live'})")
                return True
        except Exception:
            continue
    return False


def _cap_headers():
    return {"X-CAP-API-KEY": CAP_KEY, "CST": _cap["cst"], "X-SECURITY-TOKEN": _cap["sec"]}


def _mid(x):
    """Capital prices come as {bid, ask}; return the mid value."""
    if isinstance(x, dict):
        b, a = x.get("bid"), x.get("ask")
        if b is not None and a is not None:
            return round((b + a) / 2, 5)
        return b if b is not None else a
    return x


def cap_market_data(search_term, resolution="MINUTE_15", bars=40):
    """Search for an instrument and return live snapshot + recent candles."""
    if not (CAP_KEY and CAP_PASS and CAP_EMAIL):
        return {"error": "Capital.com not configured. Add CAPITAL_API_KEY, CAPITAL_PASSWORD and CAPITAL_EMAIL to your .env."}
    if not HAS_REQUESTS:
        return {"error": "The 'requests' library is not installed. Run: pip install requests"}
    if not _cap["cst"] and not cap_login():
        return {"error": "Could not log in to Capital.com. Check your API key, password and email."}

    def _search():
        return requests.get(f"{_cap['base']}/markets", headers=_cap_headers(),
                            params={"searchTerm": search_term}, timeout=12)

    r = _search()
    if r.status_code == 401:           # session expired — re-login once
        if not cap_login():
            return {"error": "Capital.com session expired and re-login failed."}
        r = _search()
    if r.status_code != 200:
        return {"error": f"Capital.com market search failed (HTTP {r.status_code})."}

    markets = r.json().get("markets", [])
    if not markets:
        return {"error": f"No instrument found on Capital.com matching '{search_term}'."}

    m    = markets[0]
    epic = m.get("epic")
    name = m.get("instrumentName", epic)

    pr = requests.get(f"{_cap['base']}/prices/{epic}", headers=_cap_headers(),
                      params={"resolution": resolution, "max": bars}, timeout=15)

    snapshot = {
        "bid":        m.get("bid"),
        "offer":      m.get("offer"),
        "netChange":  m.get("netChange"),
        "pctChange":  m.get("percentageChange"),
        "high":       m.get("high"),
        "low":        m.get("low"),
        "updateTime": m.get("updateTime"),
    }

    if pr.status_code != 200:
        return {"instrument": name, "epic": epic, "snapshot": snapshot,
                "candles": [], "note": f"Live quote available; candle history unavailable (HTTP {pr.status_code})."}

    candles = []
    for p in pr.json().get("prices", []):
        candles.append({
            "t": p.get("snapshotTime"),
            "o": _mid(p.get("openPrice")),
            "h": _mid(p.get("highPrice")),
            "l": _mid(p.get("lowPrice")),
            "c": _mid(p.get("closePrice")),
            "v": p.get("lastTradedVolume"),
        })

    return {"instrument": name, "epic": epic, "resolution": resolution,
            "snapshot": snapshot, "candles": candles}


TOOLS = [{
    "name": "get_live_market_data",
    "description": (
        "Fetch LIVE real-time market data (current bid/offer price plus recent OHLC candles) "
        "from the user's Capital.com account for ANY instrument — gold, stock indices, forex, "
        "individual stocks, or crypto. Call this whenever the user wants a real-time analysis, "
        "scan, or recommendation on a market, or names an instrument without attaching a chart image."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "search_term": {
                "type": "string",
                "description": "The instrument to look up, e.g. 'Gold', 'US 100', 'Nasdaq', 'EUR/USD', 'Tesla', 'Bitcoin'.",
            },
            "resolution": {
                "type": "string",
                "enum": ["MINUTE", "MINUTE_5", "MINUTE_15", "MINUTE_30", "HOUR", "HOUR_4", "DAY"],
                "description": "Candle timeframe. Default to MINUTE_15 for intraday; use HOUR or DAY for swing analysis.",
            },
        },
        "required": ["search_term"],
    },
}]


app = Flask(__name__)


@app.route("/")
def index():
    return HTML


@app.route("/clear", methods=["POST"])
def clear():
    conversation.clear()
    return jsonify({"status": "cleared"})


def _history():
    """Send a trimmed window, but never start on an orphaned tool_result."""
    h = conversation[-24:]
    while h:
        first = h[0]
        c = first["content"]
        orphan = isinstance(c, list) and any(
            isinstance(p, dict) and p.get("type") == "tool_result" for p in c)
        if first["role"] != "user" or orphan:
            h = h[1:]
        else:
            break
    return h


@app.route("/chat", methods=["POST"])
def chat():
    if not API_KEY:
        return jsonify({"error": "API key missing. Run: $env:ANTHROPIC_API_KEY='sk-...' then restart."}), 500

    text  = request.form.get("message", "").strip()
    chart = request.files.get("chart")

    if not text and not chart:
        return jsonify({"error": "Send a message or attach a chart."}), 400

    content = []
    if chart:
        raw  = chart.read()
        b64  = base64.standard_b64encode(raw).decode()
        ext  = chart.filename.lower()
        mime = ("image/png"  if ext.endswith(".png")  else
                "image/jpeg" if ext.endswith((".jpg", ".jpeg")) else
                "image/webp" if ext.endswith(".webp")  else "image/jpeg")
        content.append({"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}})
        # strip image bytes from earlier turns to keep memory + tokens down
        for msg in conversation:
            if isinstance(msg["content"], list):
                for p in msg["content"]:
                    if isinstance(p, dict) and p.get("type") == "image":
                        p.clear()
                        p.update({"type": "text", "text": "[earlier chart]"})

    content.append({"type": "text", "text": text if text else "Analyze this chart and give me a clear recommendation."})
    conversation.append({"role": "user", "content": content})

    try:
        client = anthropic.Anthropic(api_key=API_KEY)

        # Agentic loop: let Claude call the live-data tool, then analyze the result.
        for _ in range(5):
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=SYSTEM,
                tools=TOOLS,
                messages=_history(),
            )

            assistant_content = []
            for b in resp.content:
                if b.type == "text":
                    assistant_content.append({"type": "text", "text": b.text})
                elif b.type == "tool_use":
                    assistant_content.append({"type": "tool_use", "id": b.id,
                                              "name": b.name, "input": b.input})
            conversation.append({"role": "assistant", "content": assistant_content})

            if resp.stop_reason == "tool_use":
                results = []
                for blk in assistant_content:
                    if blk["type"] == "tool_use" and blk["name"] == "get_live_market_data":
                        data = cap_market_data(
                            blk["input"].get("search_term", ""),
                            blk["input"].get("resolution", "MINUTE_15"),
                        )
                        results.append({"type": "tool_result", "tool_use_id": blk["id"],
                                        "content": json.dumps(data)[:7000]})
                conversation.append({"role": "user", "content": results})
                continue

            reply = "".join(b["text"] for b in assistant_content if b["type"] == "text")
            return jsonify({"reply": reply or "(no response)"})

        return jsonify({"reply": "Stopped after several steps — please try again."})

    except Exception as e:
        # roll back the half-finished turn
        if conversation and conversation[-1]["role"] == "user":
            conversation.pop()
        return jsonify({"error": str(e)}), 500


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"/>
<title>Trading AI</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;background:#0d0f14;color:#e0e0e0;font-family:'Segoe UI',system-ui,sans-serif;overflow:hidden}
body{display:flex;flex-direction:column}

#hdr{background:#111318;border-bottom:1px solid #1e2130;padding:10px 16px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
#hdr h1{font-size:.95rem;color:#f5c518;font-weight:700;letter-spacing:.4px}
#clear-btn{background:transparent;border:1px solid #2a2d35;color:#777;border-radius:6px;padding:4px 12px;cursor:pointer;font-size:.75rem}
#clear-btn:hover{border-color:#f5c518;color:#f5c518}

#messages{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px}
#messages::-webkit-scrollbar{width:4px}
#messages::-webkit-scrollbar-thumb{background:#1e2130;border-radius:4px}

.msg{max-width:85%;padding:10px 14px;border-radius:12px;font-size:.88rem;line-height:1.65;word-break:break-word;white-space:pre-wrap}
.msg.user{background:#1e2235;align-self:flex-end;border-bottom-right-radius:3px;color:#c8cfe0}
.msg.bot{background:#161920;align-self:flex-start;border-bottom-left-radius:3px;border:1px solid #1e2130}
.msg.bot strong{color:#f5c518}
.msg img{max-width:180px;border-radius:6px;margin-bottom:6px;display:block}
.msg.typing{color:#444;font-style:italic}
.hint{text-align:center;color:#333;font-size:.82rem;padding:40px 20px;line-height:1.9}
.hint b{color:#555}

#bar{border-top:1px solid #1e2130;padding:10px 12px;display:flex;align-items:flex-end;gap:8px;background:#111318;flex-shrink:0}

#aw{position:relative;width:40px;height:40px;flex-shrink:0;border-radius:50%;background:#1a1d2a;border:1px solid #2a2d35;display:flex;align-items:center;justify-content:center;cursor:pointer;transition:border-color .15s}
#aw:hover{border-color:#f5c518}
#ai{font-size:1.1rem;pointer-events:none;user-select:none;line-height:1}
#file-input{position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:pointer;border-radius:50%}

#ic{flex:1;min-width:0;display:flex;flex-direction:column;gap:5px}
#prev{display:none;align-items:center;gap:6px;background:#1a1d2a;border-radius:8px;padding:5px 8px}
#prev img{height:44px;width:auto;border-radius:5px;object-fit:cover}
#prev button{background:none;border:none;color:#777;cursor:pointer;font-size:.85rem;padding:2px 5px}
#prev button:hover{color:#ef5350}
#ti{width:100%;background:#0d0f14;border:1px solid #2a2d35;border-radius:20px;color:#e0e0e0;font-size:.9rem;padding:10px 16px;resize:none;height:42px;max-height:130px;font-family:inherit;outline:none;transition:border-color .2s;line-height:1.4;display:block}
#ti:focus{border-color:#f5c518}
#ti::placeholder{color:#444}

#sb{background:#f5c518;color:#0d0f14;border:none;border-radius:50%;width:40px;height:40px;cursor:pointer;font-size:1.15rem;flex-shrink:0;display:flex;align-items:center;justify-content:center;transition:opacity .15s,transform .1s}
#sb:hover{transform:scale(1.07)}
#sb:disabled{opacity:.3;cursor:not-allowed;transform:none}
</style>
</head>
<body>

<div id="hdr">
  <h1>📊 Trading AI</h1>
  <button id="clear-btn">Clear</button>
</div>

<div id="messages">
  <div class="hint">
    <b>Live market analysis — any instrument.</b><br>
    Try: "analyze gold now" · "scan nas100 on the 15m" · "what's the setup on EUR/USD"<br><br>
    Or tap 📎 to attach a chart screenshot instead.<br>
    The AI pulls live data from your Capital.com and gives a clear recommendation.
  </div>
</div>

<div id="bar">
  <div id="aw" title="Attach chart">
    <span id="ai">📎</span>
    <input type="file" id="file-input" accept="image/*">
  </div>
  <div id="ic">
    <div id="prev">
      <img id="prev-img" src="" alt="">
      <button id="rm-btn">✕</button>
    </div>
    <textarea id="ti" placeholder="Ask to analyze any market live, or attach a chart…"></textarea>
  </div>
  <button id="sb">➤</button>
</div>

<script>
var selFile = null;

document.getElementById('file-input').addEventListener('change', function(){
  var f = this.files[0];
  if(!f) return;
  selFile = f;
  var reader = new FileReader();
  reader.onload = function(e){
    document.getElementById('prev-img').src = e.target.result;
    document.getElementById('prev').style.display = 'flex';
    document.getElementById('aw').style.borderColor = '#f5c518';
  };
  reader.readAsDataURL(f);
});

document.getElementById('rm-btn').addEventListener('click', function(){
  selFile = null;
  document.getElementById('file-input').value = '';
  document.getElementById('prev').style.display = 'none';
  document.getElementById('prev-img').src = '';
  document.getElementById('aw').style.borderColor = '';
});

document.getElementById('sb').addEventListener('click', send);
document.getElementById('ti').addEventListener('keydown', function(e){
  if(e.key === 'Enter' && !e.shiftKey){ e.preventDefault(); send(); }
});
document.getElementById('ti').addEventListener('input', function(){
  this.style.height = '42px';
  this.style.height = Math.min(this.scrollHeight, 130) + 'px';
});
document.getElementById('clear-btn').addEventListener('click', function(){
  fetch('/clear', {method:'POST'}).then(function(){
    document.getElementById('messages').innerHTML =
      '<div class="hint"><b>Chat cleared.</b><br>Ready for a new session.</div>';
  });
});

async function send(){
  var ti  = document.getElementById('ti');
  var txt = ti.value.trim();
  if(!txt && !selFile) return;

  var sb  = document.getElementById('sb');
  var box = document.getElementById('messages');
  sb.disabled = true;

  var hint = box.querySelector('.hint');
  if(hint) hint.remove();

  var u = document.createElement('div');
  u.className = 'msg user';
  if(selFile){
    var im = document.createElement('img');
    im.src = URL.createObjectURL(selFile);
    u.appendChild(im);
  }
  if(txt) u.appendChild(document.createTextNode(txt));
  box.appendChild(u);

  var t = document.createElement('div');
  t.className = 'msg bot typing';
  t.textContent = 'Fetching live data & analysing…';
  box.appendChild(t);
  box.scrollTop = box.scrollHeight;

  var fd = new FormData();
  if(txt) fd.append('message', txt);
  if(selFile) fd.append('chart', selFile, selFile.name);

  ti.value = '';
  ti.style.height = '42px';
  selFile = null;
  document.getElementById('file-input').value = '';
  document.getElementById('prev').style.display = 'none';
  document.getElementById('prev-img').src = '';
  document.getElementById('aw').style.borderColor = '';

  try{
    var res  = await fetch('/chat', {method:'POST', body:fd});
    var data = await res.json();
    t.remove();
    var b = document.createElement('div');
    b.className = 'msg bot';
    b.innerHTML = fmt(data.reply || ('⚠ ' + (data.error || 'Unknown error')));
    box.appendChild(b);
  }catch(e){
    t.remove();
    var b = document.createElement('div');
    b.className = 'msg bot';
    b.textContent = '⚠ Connection error — is the server running?';
    box.appendChild(b);
  }

  box.scrollTop = box.scrollHeight;
  sb.disabled = false;
  ti.focus();
}

function fmt(s){
  return s
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/\*\*(.+?)\*\*/gs,'<strong>$1</strong>');
}
</script>
</body>
</html>"""


if __name__ == "__main__":
    if not API_KEY:
        print("\n  ⚠  ANTHROPIC_API_KEY not set!")
        print("     Stop this server and run:")
        print('     $env:ANTHROPIC_API_KEY="sk-ant-..." ; python gold_agent.py\n')

    if CAP_KEY and CAP_PASS and CAP_EMAIL:
        cap_login()   # warm the session so the first analysis is fast
    else:
        print("  TIP: add CAPITAL_API_KEY / CAPITAL_PASSWORD / CAPITAL_EMAIL to .env for live market data")

    print("\n Trading AI ready at http://localhost:5000\n")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
