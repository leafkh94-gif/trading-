"""
GoldScalperPro AI Agent v2
Conversational | Live Price | MT4 Trade Monitor | TradingView Alerts

Setup:  pip install anthropic flask yfinance
Run:    set ANTHROPIC_API_KEY=your_key && python gold_agent.py
Open:   http://localhost:5000
"""

import base64, os, json, threading, time
from datetime import datetime
from flask import Flask, request, jsonify
import anthropic

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "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")

# ── Global state ──────────────────────────────────────────────────────────────
conversation  = []          # Full chat history (Claude API format)
open_trades   = []          # Updated by TradeMonitor.mq4 via POST /trades
tv_alerts     = []          # Updated by TradingView webhook POST /webhook
live_price    = {"price": None, "change": None, "pct": None, "updated": None}
price_lock    = threading.Lock()

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM = """You are GoldScalperPro AI — a professional Gold (XAU/USD) trading assistant with real-time awareness.

You have access to:
- Live XAUUSD price (injected into each message automatically)
- User's open MT4 positions (injected when available)
- TradingView alerts (injected when received)
- Full conversation history (you remember everything we discussed)

You think using the GoldScalperPro strategy framework:

TREND    → EMA 8 / 21 / 50 stack (bullish: 8>21>50, bearish: 8<21<50)
MOMENTUM → RSI 14 (bull >55, bear <45) + MACD histogram direction
LEVELS   → 20-bar swing high/low as key S&R
SIGNALS  → SCALP-BUY, SCALP-SELL, BREAK-BUY, BREAK-SELL, or WAIT
SIZING   → 1% equity risk per trade, SL = 1.5×ATR, TP = 3×ATR (scalp) / 5×ATR (breakout)

When analyzing a chart image give this structure:
**📊 MARKET STRUCTURE** — trend + EMA read
**📍 KEY LEVELS** — support / resistance prices
**📈 INDICATORS** — RSI zone, MACD, volatility
**🎯 SIGNAL** — one of the 5 signal types + reason
**💰 TRADE PLAN** — entry / SL / TP1 / TP2 / lot sizing
**⚠️ RISK NOTES** — invalidation level + confidence

When monitoring open trades:
- Flag any trade whose stop is within 30 points of current price
- Suggest trailing stop adjustments based on current price action
- Validate whether the original entry thesis still holds
- Recommend partial close or full exit if momentum has reversed

Be conversational. Remember context. Ask clarifying questions when needed.
Give specific price levels, not vague ranges. Be direct — the user is actively trading."""

# ── Live price background thread ──────────────────────────────────────────────
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
                        live_price.update(price=p, change=chg, pct=pct,
                                          updated=datetime.now().strftime("%H:%M:%S"))
            except Exception:
                pass
        time.sleep(30)

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)

@app.route("/")
def index():
    return HTML

@app.route("/price")
def get_price():
    with price_lock:
        return jsonify(live_price)

@app.route("/trades", methods=["GET","POST"])
def trades_endpoint():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        with price_lock:
            open_trades.clear()
            open_trades.extend(data.get("trades", []))
        return jsonify({"status": "ok"})
    return jsonify({"trades": open_trades})

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    msg  = data.get("message") or data.get("text") or json.dumps(data)
    ts   = datetime.now().strftime("%H:%M:%S")
    tv_alerts.append({"time": ts, "message": msg})
    # Auto-inject alert into conversation
    conversation.append({"role":"user",
                         "content": f"[TradingView Alert {ts}]: {msg}"})
    return jsonify({"status": "ok"})

@app.route("/alerts")
def get_alerts():
    return jsonify({"alerts": tv_alerts[-20:]})

@app.route("/clear", methods=["POST"])
def clear():
    conversation.clear()
    return jsonify({"status": "cleared"})

@app.route("/chat", methods=["POST"])
def chat():
    text  = request.form.get("message", "").strip()
    chart = request.files.get("chart")

    # Build context prefix (price + trades)
    ctx = []
    with price_lock:
        if live_price["price"]:
            ctx.append(f"Live XAUUSD: ${live_price['price']} ({live_price['change']:+.2f} / {live_price['pct']:+.3f}%)")
    if open_trades:
        ctx.append("Open MT4 positions:\n" + json.dumps(open_trades, indent=2))

    full_text = ("\n".join(ctx) + "\n\n" + text).strip() if ctx else text

    # Build message content
    content = []
    if chart:
        raw   = chart.read()
        b64   = base64.standard_b64encode(raw).decode()
        fname = chart.filename.lower()
        mime  = ("image/png"  if fname.endswith(".png")  else
                 "image/jpeg" if fname.endswith((".jpg",".jpeg")) else
                 "image/webp" if fname.endswith(".webp")  else "image/png")
        content.append({"type":"image","source":{"type":"base64","media_type":mime,"data":b64}})

    content.append({"type":"text","text": full_text or "Analyze this chart with the GoldScalperPro framework."})
    conversation.append({"role":"user","content":content})

    # Keep history lean: strip image bytes from all but last image message
    api_messages = _clean_history(conversation)

    try:
        client = anthropic.Anthropic(api_key=API_KEY)
        resp   = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SYSTEM,
            messages=api_messages
        )
        reply = resp.content[0].text
        conversation.append({"role":"assistant","content":reply})
        return jsonify({"reply": reply})
    except Exception as e:
        conversation.pop()
        return jsonify({"error": str(e)}), 500

def _clean_history(hist):
    """Keep last 30 messages. Strip image bytes from all but the last image turn."""
    trimmed = hist[-30:]
    last_img_idx = None
    for i, m in enumerate(trimmed):
        if isinstance(m["content"], list):
            for c in m["content"]:
                if c.get("type") == "image":
                    last_img_idx = i
    result = []
    for i, m in enumerate(trimmed):
        if isinstance(m["content"], list) and i != last_img_idx:
            # Replace image blocks with a placeholder text
            new_content = []
            for c in m["content"]:
                if c.get("type") == "image":
                    new_content.append({"type":"text","text":"[chart image from earlier in conversation]"})
                else:
                    new_content.append(c)
            result.append({"role":m["role"],"content":new_content})
        else:
            result.append(m)
    return result

# ── Embedded HTML (single-file) ───────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>GoldScalperPro AI</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d0f14;color:#e0e0e0;font-family:'Segoe UI',system-ui,sans-serif;height:100vh;display:flex;flex-direction:column;overflow:hidden}

/* ── Header ── */
#header{background:#111318;border-bottom:1px solid #1f2230;padding:10px 16px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
#header h1{font-size:1rem;color:#f5c518;font-weight:700;letter-spacing:.5px}
#ticker{font-size:.95rem;font-weight:600}
#ticker.up{color:#26a69a}#ticker.down{color:#ef5350}#ticker.flat{color:#888}
#header-right{display:flex;align-items:center;gap:12px}
#clear-btn{background:transparent;border:1px solid #2a2d35;color:#888;border-radius:6px;padding:4px 10px;cursor:pointer;font-size:.75rem;transition:border-color .2s,color .2s}
#clear-btn:hover{border-color:#f5c518;color:#f5c518}

/* ── Layout ── */
#body{display:flex;flex:1;overflow:hidden}

/* ── Chat panel ── */
#chat-panel{flex:1;display:flex;flex-direction:column;min-width:0}
#messages{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px}
#messages::-webkit-scrollbar{width:4px}
#messages::-webkit-scrollbar-thumb{background:#2a2d35;border-radius:4px}

.msg{max-width:82%;padding:10px 13px;border-radius:10px;font-size:.88rem;line-height:1.65;word-break:break-word}
.msg.user{background:#1e2235;align-self:flex-end;border-bottom-right-radius:3px;color:#c8cfe0}
.msg.bot{background:#161920;align-self:flex-start;border-bottom-left-radius:3px;border:1px solid #1f2230}
.msg.bot strong{color:#f5c518}
.msg img{max-width:200px;border-radius:6px;margin-top:6px;display:block}
.msg.typing{color:#555;font-style:italic}

/* ── Input bar ── */
#input-bar{border-top:1px solid #1f2230;padding:10px 12px;display:flex;align-items:flex-end;gap:8px;flex-shrink:0;background:#111318}
#attach-btn{background:#1e2235;border:1px solid #2a2d35;color:#888;border-radius:8px;padding:8px 10px;cursor:pointer;font-size:1rem;flex-shrink:0;transition:border-color .2s}
#attach-btn:hover{border-color:#f5c518}
#attach-btn.has-file{border-color:#f5c518;color:#f5c518}
#file-input{display:none}
#msg-input{flex:1;background:#0d0f14;border:1px solid #2a2d35;border-radius:8px;color:#e0e0e0;font-size:.88rem;padding:9px 12px;resize:none;height:40px;max-height:120px;font-family:inherit;outline:none;transition:border-color .2s;line-height:1.4}
#msg-input:focus{border-color:#f5c518}
#send-btn{background:#f5c518;color:#0d0f14;border:none;border-radius:8px;padding:9px 14px;cursor:pointer;font-weight:700;font-size:.9rem;flex-shrink:0;transition:opacity .2s}
#send-btn:disabled{opacity:.4;cursor:not-allowed}

/* ── Sidebar ── */
#sidebar{width:260px;border-left:1px solid #1f2230;display:flex;flex-direction:column;overflow:hidden;flex-shrink:0}
.panel{border-bottom:1px solid #1f2230;display:flex;flex-direction:column}
.panel-header{padding:10px 12px;font-size:.72rem;text-transform:uppercase;letter-spacing:1px;color:#888;font-weight:600;background:#111318;flex-shrink:0}
.panel-body{padding:10px 12px;font-size:.8rem;overflow-y:auto;max-height:200px;flex:1}
.panel-body::-webkit-scrollbar{width:3px}
.panel-body::-webkit-scrollbar-thumb{background:#2a2d35}

.trade-card{background:#0d0f14;border:1px solid #1f2230;border-radius:6px;padding:8px;margin-bottom:7px}
.trade-card .symbol{font-weight:700;font-size:.82rem;color:#e0e0e0}
.trade-card .dir{display:inline-block;padding:1px 6px;border-radius:3px;font-size:.7rem;font-weight:700;margin-left:5px}
.dir.buy{background:#0d2b2b;color:#26a69a}
.dir.sell{background:#2b0d0d;color:#ef5350}
.trade-card .detail{color:#888;font-size:.75rem;margin-top:3px}
.trade-card .pnl{font-weight:600;font-size:.82rem;margin-top:2px}
.pnl.pos{color:#26a69a}.pnl.neg{color:#ef5350}
.no-data{color:#444;font-style:italic;font-size:.78rem}

.alert-item{border-left:2px solid #f5c518;padding:4px 8px;margin-bottom:6px;font-size:.76rem;color:#bbb}
.alert-item .alert-time{color:#888;font-size:.7rem}

#tv-setup{padding:10px 12px;font-size:.75rem;color:#555;line-height:1.5;flex:1}
#tv-setup a{color:#f5c518}

@media(max-width:640px){#sidebar{display:none}}

/* Welcome message */
.welcome{text-align:center;color:#444;font-size:.85rem;padding:40px 20px;line-height:1.8}
.welcome span{font-size:2rem;display:block;margin-bottom:10px}
</style>
</head>
<body>

<div id="header">
  <h1>🏆 GoldScalperPro AI</h1>
  <div id="header-right">
    <span id="ticker" class="flat">XAUUSD —</span>
    <button id="clear-btn" onclick="clearChat()">Clear chat</button>
  </div>
</div>

<div id="body">

  <!-- Chat -->
  <div id="chat-panel">
    <div id="messages">
      <div class="welcome">
        <span>📈</span>
        Ask me anything about Gold trading.<br>
        Attach a chart screenshot for a full GoldScalperPro analysis.<br>
        I can see your live price and open MT4 trades in real time.
      </div>
    </div>

    <div id="input-bar">
      <button id="attach-btn" onclick="document.getElementById('file-input').click()" title="Attach chart">📎</button>
      <input type="file" id="file-input" accept="image/*" onchange="onFileSelected(this)"/>
      <textarea id="msg-input" placeholder="Ask about Gold, attach a chart, or say 'check my trades'…" onkeydown="onKey(event)" oninput="autoResize(this)"></textarea>
      <button id="send-btn" onclick="sendMessage()">▶</button>
    </div>
  </div>

  <!-- Sidebar -->
  <div id="sidebar">

    <div class="panel" style="flex:0 0 auto">
      <div class="panel-header">📊 Open MT4 Trades</div>
      <div class="panel-body" id="trades-panel">
        <div class="no-data">No trades received yet.<br>Run TradeMonitor.mq4 in MT4.</div>
      </div>
    </div>

    <div class="panel" style="flex:1">
      <div class="panel-header">⚡ TradingView Alerts</div>
      <div class="panel-body" id="alerts-panel">
        <div class="no-data" id="no-alerts">No alerts yet.</div>
      </div>
    </div>

    <div id="tv-setup">
      <b style="color:#888">Set up TV alerts:</b><br>
      In TradingView → Alert → Notifications → Webhook URL:<br>
      <code style="color:#f5c518">http://YOUR-IP:5000/webhook</code>
    </div>

  </div>
</div>

<script>
let selectedFile = null;

// ── File attach ──────────────────────────────────────────────────
function onFileSelected(input){
  selectedFile = input.files[0] || null;
  const btn = document.getElementById('attach-btn');
  btn.classList.toggle('has-file', !!selectedFile);
  btn.title = selectedFile ? selectedFile.name : 'Attach chart';
}

// ── Auto-resize textarea ─────────────────────────────────────────
function autoResize(el){
  el.style.height='40px';
  el.style.height = Math.min(el.scrollHeight, 120)+'px';
}

// ── Send on Enter (Shift+Enter = newline) ────────────────────────
function onKey(e){
  if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); sendMessage(); }
}

// ── Send message ─────────────────────────────────────────────────
async function sendMessage(){
  const input = document.getElementById('msg-input');
  const text  = input.value.trim();
  if(!text && !selectedFile) return;

  const sendBtn = document.getElementById('send-btn');
  sendBtn.disabled = true;

  // Show user message
  const msgs = document.getElementById('messages');
  // Remove welcome if present
  const welcome = msgs.querySelector('.welcome');
  if(welcome) welcome.remove();

  const userDiv = document.createElement('div');
  userDiv.className = 'msg user';
  if(selectedFile){
    const img = document.createElement('img');
    img.src = URL.createObjectURL(selectedFile);
    userDiv.appendChild(img);
  }
  if(text) userDiv.appendChild(document.createTextNode(text));
  msgs.appendChild(userDiv);

  // Show typing indicator
  const typing = document.createElement('div');
  typing.className = 'msg bot typing';
  typing.textContent = 'Analyzing…';
  msgs.appendChild(typing);
  msgs.scrollTop = msgs.scrollHeight;

  input.value = '';
  input.style.height = '40px';

  // Build form data
  const fd = new FormData();
  if(text) fd.append('message', text);
  if(selectedFile) fd.append('chart', selectedFile, selectedFile.name);

  // Reset file
  selectedFile = null;
  document.getElementById('file-input').value = '';
  document.getElementById('attach-btn').classList.remove('has-file');
  document.getElementById('attach-btn').title = 'Attach chart';

  try{
    const res  = await fetch('/chat', {method:'POST', body:fd});
    const data = await res.json();
    typing.remove();

    const botDiv = document.createElement('div');
    botDiv.className = 'msg bot';
    botDiv.innerHTML = formatMsg(data.reply || ('Error: ' + data.error));
    msgs.appendChild(botDiv);
  } catch(e){
    typing.remove();
    const errDiv = document.createElement('div');
    errDiv.className = 'msg bot';
    errDiv.textContent = 'Connection error. Is the server running?';
    msgs.appendChild(errDiv);
  }

  msgs.scrollTop = msgs.scrollHeight;
  sendBtn.disabled = false;
  input.focus();
}

// ── Format bot message (markdown bold + line breaks) ─────────────
function formatMsg(text){
  return text
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/\n/g,'<br>');
}

// ── Clear conversation ────────────────────────────────────────────
async function clearChat(){
  await fetch('/clear',{method:'POST'});
  const msgs = document.getElementById('messages');
  msgs.innerHTML = '<div class="welcome"><span>📈</span>Chat cleared. Ready for a new session.</div>';
}

// ── Live price ────────────────────────────────────────────────────
async function updatePrice(){
  try{
    const d = await (await fetch('/price')).json();
    const el = document.getElementById('ticker');
    if(d.price){
      const sign = d.change >= 0 ? '+' : '';
      el.textContent = `XAUUSD $${d.price}  ${sign}${d.change} (${sign}${d.pct}%)`;
      el.className = d.change > 0 ? 'up' : d.change < 0 ? 'down' : 'flat';
    }
  } catch(e){}
}

// ── Open trades ───────────────────────────────────────────────────
async function updateTrades(){
  try{
    const d = await (await fetch('/trades')).json();
    const panel = document.getElementById('trades-panel');
    if(!d.trades || !d.trades.length){
      panel.innerHTML = '<div class="no-data">No open trades.<br>Run TradeMonitor.mq4 in MT4.</div>';
      return;
    }
    panel.innerHTML = d.trades.map(t => {
      const pnlClass = t.pnl >= 0 ? 'pos' : 'neg';
      const sign     = t.pnl >= 0 ? '+' : '';
      const dirClass = t.direction === 'BUY' ? 'buy' : 'sell';
      return `<div class="trade-card">
        <div><span class="symbol">${t.symbol}</span>
             <span class="dir ${dirClass}">${t.direction}</span></div>
        <div class="detail">Lots: ${t.lots} | Open: ${t.open}</div>
        <div class="detail">SL: ${t.sl||'—'} | TP: ${t.tp||'—'}</div>
        <div class="pnl ${pnlClass}">${sign}$${t.pnl.toFixed(2)} (${t.pips.toFixed(1)} pts)</div>
      </div>`;
    }).join('');
  } catch(e){}
}

// ── TradingView alerts ────────────────────────────────────────────
async function updateAlerts(){
  try{
    const d = await (await fetch('/alerts')).json();
    const panel = document.getElementById('alerts-panel');
    if(!d.alerts || !d.alerts.length) return;
    document.getElementById('no-alerts')?.remove();
    panel.innerHTML = d.alerts.slice().reverse().map(a =>
      `<div class="alert-item"><div class="alert-time">${a.time}</div>${escHtml(a.message)}</div>`
    ).join('');
  } catch(e){}
}

function escHtml(s){ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') }

// ── Polling ───────────────────────────────────────────────────────
updatePrice();  setInterval(updatePrice,  30000);
updateTrades(); setInterval(updateTrades, 10000);
updateAlerts(); setInterval(updateAlerts, 15000);
</script>
</body>
</html>"""

if __name__ == "__main__":
    if HAS_YFINANCE:
        threading.Thread(target=price_worker, daemon=True).start()
        print(" Live price feed active (XAUUSD via yfinance)")
    else:
        print(" TIP: Run 'pip install yfinance' to enable live price feed")

    print("\n GoldScalperPro AI Agent v2")
    print(" Chat  : http://localhost:5000")
    print(" Trades: POST http://localhost:5000/trades  (from TradeMonitor.mq4)")
    print(" Alerts: POST http://localhost:5000/webhook (from TradingView)\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
