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

SYSTEM = """You are a professional trading analyst. You cover every market — Gold, indices (NAS100, SP500, DOW), forex, stocks, crypto — any instrument the user mentions.

You have a LIVE data tool: get_live_market_data. It pulls real-time price and recent candles from the user's Capital.com account for ANY instrument.

USE THE TOOL whenever the user:
• Asks you to analyze, scan, check, or recommend on a market in real time
• Names an instrument (e.g. "gold", "nasdaq", "EUR/USD", "Tesla", "bitcoin") without attaching a chart
• Asks "what's the setup on X right now" or anything time-sensitive

After you receive the live data, give a structured analysis:
• Current price and short-term trend (Bullish / Bearish / Sideways)
• Key support and resistance levels from the candle data
• Momentum read (are recent candles expanding, contracting, reversing?)
• One clear decision: BUY / SELL / WAIT
• Entry price, stop-loss, and target(s) with a risk/reward note

When the user attaches a CHART IMAGE instead, analyze the image directly (same structure) — you don't need the tool.

If live data can't be fetched, say so plainly and offer to analyze a screenshot instead.

HONESTY RULE: If there is no clear, high-probability setup — say so directly. "No trade available right now" is a valid and valuable answer. Never force a trade recommendation just to give one. A choppy market, low confluence, or unclear structure is a reason to WAIT, not to fabricate a setup. Quality over quantity — only flag trades you would genuinely take.

Be concise and specific with price levels — no filler. Remember the full conversation."""


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
