"""
GoldScalperPro AI Agent
Chart analysis + Gold trading advisor

Setup:  pip install anthropic flask yfinance
Run:    python gold_agent.py
Open:   http://localhost:5000
"""

import base64, os, threading, time
from datetime import datetime
from flask import Flask, request, jsonify
import anthropic

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

API_KEY = os.environ.get(
    "ANTHROPIC_API_KEY",
    "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"
)

conversation = []
live_price   = {"price": None, "change": None, "pct": None}
price_lock   = threading.Lock()

SYSTEM = """You are GoldScalperPro AI — a professional Gold (XAU/USD) trading assistant.

You specialize in:
- Reading Gold chart screenshots (support/resistance, trend, patterns)
- EMA 8/21/50 crossover strategy
- RSI(14) momentum confirmation
- Scalping on M1/M5 and swing trades on H1/H4
- Risk management: 1% per trade, SL = 1.5×ATR, TP = 3×ATR

When analyzing a chart image:
**MARKET STRUCTURE** — trend direction + EMA stack
**KEY LEVELS** — support and resistance prices
**INDICATORS** — RSI zone, momentum
**SIGNAL** — BUY / SELL / WAIT with clear reason
**TRADE PLAN** — entry price, stop loss, take profit
**RISK NOTES** — invalidation level

When answering questions: be direct, give specific prices, remember the conversation.
You are talking to an active Gold trader."""

def price_worker():
    while True:
        if HAS_YFINANCE:
            try:
                t = yf.Ticker("GC=F")
                h = t.history(period="2d", interval="1m")
                if not h.empty:
                    p   = round(float(h["Close"].iloc[-1]), 2)
                    p0  = round(float(h["Close"].iloc[-2]), 2)
                    chg = round(p - p0, 2)
                    pct = round((chg / p0) * 100, 3) if p0 else 0
                    with price_lock:
                        live_price.update(price=p, change=chg, pct=pct)
            except Exception:
                pass
        time.sleep(30)

app = Flask(__name__)

@app.route("/")
def index():
    return HTML

@app.route("/price")
def get_price():
    with price_lock:
        return jsonify(live_price)

@app.route("/clear", methods=["POST"])
def clear():
    conversation.clear()
    return jsonify({"status": "cleared"})

@app.route("/chat", methods=["POST"])
def chat():
    text  = request.form.get("message", "").strip()
    chart = request.files.get("chart")

    with price_lock:
        price_ctx = f"Live XAUUSD: ${live_price['price']}" if live_price["price"] else ""

    full_text = (price_ctx + "\n\n" + text).strip() if price_ctx else text

    content = []
    if chart:
        raw  = chart.read()
        b64  = base64.standard_b64encode(raw).decode()
        name = chart.filename.lower()
        mime = ("image/png"  if name.endswith(".png")  else
                "image/jpeg" if name.endswith((".jpg", ".jpeg")) else
                "image/webp" if name.endswith(".webp") else "image/png")
        content.append({"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}})

    content.append({"type": "text", "text": full_text or "Analyze this chart."})
    conversation.append({"role": "user", "content": content})

    # Keep last 30 messages; strip old images to save tokens
    trimmed = conversation[-30:]
    last_img = None
    for i, m in enumerate(trimmed):
        if isinstance(m["content"], list):
            for c in m["content"]:
                if c.get("type") == "image":
                    last_img = i
    api_msgs = []
    for i, m in enumerate(trimmed):
        if isinstance(m["content"], list) and i != last_img:
            cleaned = [{"type": "text", "text": "[chart uploaded earlier]"} if c.get("type") == "image" else c
                       for c in m["content"]]
            api_msgs.append({"role": m["role"], "content": cleaned})
        else:
            api_msgs.append(m)

    try:
        client = anthropic.Anthropic(api_key=API_KEY)
        resp   = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SYSTEM,
            messages=api_msgs
        )
        reply = resp.content[0].text
        conversation.append({"role": "assistant", "content": reply})
        return jsonify({"reply": reply})
    except Exception as e:
        conversation.pop()
        return jsonify({"error": str(e)}), 500

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>GoldScalperPro AI</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d0f14;color:#e0e0e0;font-family:'Segoe UI',system-ui,sans-serif;height:100vh;display:flex;flex-direction:column;overflow:hidden}
#header{background:#111318;border-bottom:1px solid #1f2230;padding:12px 18px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
#header h1{font-size:1.05rem;color:#f5c518;font-weight:700;letter-spacing:.5px}
#ticker{font-size:.92rem;font-weight:600;color:#888}
#ticker.up{color:#26a69a}#ticker.down{color:#ef5350}
#clear-btn{background:transparent;border:1px solid #2a2d35;color:#666;border-radius:6px;padding:4px 10px;cursor:pointer;font-size:.75rem}
#clear-btn:hover{border-color:#f5c518;color:#f5c518}
#messages{flex:1;overflow-y:auto;padding:18px;display:flex;flex-direction:column;gap:12px}
#messages::-webkit-scrollbar{width:4px}
#messages::-webkit-scrollbar-thumb{background:#2a2d35;border-radius:4px}
.msg{max-width:84%;padding:11px 14px;border-radius:10px;font-size:.875rem;line-height:1.7;word-break:break-word}
.msg.user{background:#1e2235;align-self:flex-end;border-bottom-right-radius:3px;color:#c8cfe0}
.msg.bot{background:#161920;align-self:flex-start;border-bottom-left-radius:3px;border:1px solid #1f2230}
.msg.bot strong{color:#f5c518}
.msg img{max-width:200px;border-radius:6px;margin-top:6px;display:block}
.msg.typing{color:#555;font-style:italic}
.welcome{text-align:center;color:#444;font-size:.85rem;padding:60px 20px;line-height:1.9}
.welcome big{font-size:2.2rem;display:block;margin-bottom:12px}
#input-bar{border-top:1px solid #1f2230;padding:10px 12px;display:flex;align-items:flex-end;gap:8px;background:#111318;flex-shrink:0}
#attach-btn{background:#1e2235;border:1px solid #2a2d35;color:#888;border-radius:8px;padding:8px 11px;cursor:pointer;font-size:1rem;flex-shrink:0}
#attach-btn:hover,#attach-btn.has-file{border-color:#f5c518;color:#f5c518}
#file-input{display:none}
#msg-input{flex:1;background:#0d0f14;border:1px solid #2a2d35;border-radius:8px;color:#e0e0e0;font-size:.875rem;padding:9px 13px;resize:none;height:40px;max-height:120px;font-family:inherit;outline:none}
#msg-input:focus{border-color:#f5c518}
#send-btn{background:#f5c518;color:#0d0f14;border:none;border-radius:8px;padding:9px 15px;cursor:pointer;font-weight:700;font-size:.9rem;flex-shrink:0}
#send-btn:disabled{opacity:.4;cursor:not-allowed}
</style>
</head>
<body>

<div id="header">
  <h1>&#127941; GoldScalperPro AI</h1>
  <span id="ticker">XAUUSD —</span>
  <button id="clear-btn" onclick="clearChat()">Clear</button>
</div>

<div id="messages">
  <div class="welcome">
    <big>&#128200;</big>
    Ask me anything about Gold (XAU/USD).<br>
    Attach a chart screenshot for a full technical analysis.<br>
    I remember our conversation and see the live price.
  </div>
</div>

<div id="input-bar">
  <button id="attach-btn" onclick="document.getElementById('file-input').click()" title="Attach chart">&#128206;</button>
  <input type="file" id="file-input" accept="image/*" onchange="onFile(this)"/>
  <textarea id="msg-input" placeholder="Ask about Gold or attach a chart…" onkeydown="onKey(event)" oninput="resize(this)"></textarea>
  <button id="send-btn" onclick="send()">&#9654;</button>
</div>

<script>
let file = null;

function onFile(input){
  file = input.files[0] || null;
  const b = document.getElementById('attach-btn');
  b.classList.toggle('has-file', !!file);
  b.title = file ? file.name : 'Attach chart';
}

function resize(el){
  el.style.height = '40px';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

function onKey(e){
  if(e.key === 'Enter' && !e.shiftKey){ e.preventDefault(); send(); }
}

function fmt(text){
  return text
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/\n/g,'<br>');
}

async function send(){
  const inp  = document.getElementById('msg-input');
  const text = inp.value.trim();
  if(!text && !file) return;

  const btn  = document.getElementById('send-btn');
  btn.disabled = true;

  const box = document.getElementById('messages');
  box.querySelector('.welcome')?.remove();

  const uDiv = document.createElement('div');
  uDiv.className = 'msg user';
  if(file){
    const img = document.createElement('img');
    img.src = URL.createObjectURL(file);
    uDiv.appendChild(img);
  }
  if(text) uDiv.appendChild(document.createTextNode(text));
  box.appendChild(uDiv);

  const wait = document.createElement('div');
  wait.className = 'msg bot typing';
  wait.textContent = 'Analyzing…';
  box.appendChild(wait);
  box.scrollTop = box.scrollHeight;

  inp.value = '';
  inp.style.height = '40px';

  const fd = new FormData();
  if(text) fd.append('message', text);
  if(file) fd.append('chart', file, file.name);
  file = null;
  document.getElementById('file-input').value = '';
  document.getElementById('attach-btn').classList.remove('has-file');
  document.getElementById('attach-btn').title = 'Attach chart';

  try{
    const res  = await fetch('/chat', {method:'POST', body:fd});
    const data = await res.json();
    wait.remove();
    const bDiv = document.createElement('div');
    bDiv.className = 'msg bot';
    bDiv.innerHTML = fmt(data.reply || ('Error: ' + data.error));
    box.appendChild(bDiv);
  } catch(e){
    wait.remove();
    const eDiv = document.createElement('div');
    eDiv.className = 'msg bot';
    eDiv.textContent = 'Connection error. Is the server running?';
    box.appendChild(eDiv);
  }

  box.scrollTop = box.scrollHeight;
  btn.disabled = false;
  inp.focus();
}

async function clearChat(){
  await fetch('/clear', {method:'POST'});
  document.getElementById('messages').innerHTML =
    '<div class="welcome"><big>&#128200;</big>Chat cleared. Ready for new session.</div>';
}

async function updatePrice(){
  try{
    const d  = await (await fetch('/price')).json();
    const el = document.getElementById('ticker');
    if(d.price){
      const s = d.change >= 0 ? '+' : '';
      el.textContent = 'XAUUSD $' + d.price + '  ' + s + d.change + ' (' + s + d.pct + '%)';
      el.className = d.change > 0 ? 'up' : d.change < 0 ? 'down' : '';
    }
  } catch(e){}
}

updatePrice();
setInterval(updatePrice, 30000);
</script>
</body>
</html>"""

if __name__ == "__main__":
    if HAS_YFINANCE:
        threading.Thread(target=price_worker, daemon=True).start()
        print(" Live price feed active (XAUUSD via yfinance)")

    port = int(os.environ.get("PORT", 5000))
    print("\n GoldScalperPro AI Agent")
    print(f" Open this in your browser: http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
