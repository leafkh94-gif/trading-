"""
GoldScalperPro AI Agent v3
Multi-user | Login | Live Price | MT4 Monitor | TradingView | Conversational

Setup:  pip install anthropic flask yfinance
Run:    set ANTHROPIC_API_KEY=your_key && set ACCESS_PASSWORD=your_password && python gold_agent.py
Open:   http://localhost:5000
"""

import base64, os, json, threading, time, secrets, io
from datetime import datetime
from flask import Flask, request, jsonify, session, redirect, send_file
import anthropic

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

API_KEY         = os.environ.get("ANTHROPIC_API_KEY", "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")
ACCESS_PASSWORD = os.environ.get("ACCESS_PASSWORD", "gold2024")   # Change before sharing!

# ── Per-user storage (keyed by username) ──────────────────────────────────────
users = {}  # {username: {conversation, trades, alerts}}

def get_user(username):
    if username not in users:
        users[username] = {"conversation": [], "trades": [], "alerts": []}
    return users[username]

# ── Global live price ──────────────────────────────────────────────────────────
live_price = {"price": None, "change": None, "pct": None, "updated": None}
price_lock = threading.Lock()

# ── System prompt ──────────────────────────────────────────────────────────────
SYSTEM = """You are GoldScalperPro AI — a professional Gold (XAU/USD) trading assistant with real-time awareness.

You have access to:
- Live XAUUSD price (injected automatically)
- User's open MT4 positions (injected when available)
- TradingView alerts (injected when received)
- Full conversation history (you remember everything)

You think using the GoldScalperPro strategy:
TREND    → EMA 8/21/50 stack  |  MOMENTUM → RSI 14 + MACD histogram
LEVELS   → 20-bar swing high/low  |  SIGNALS → SCALP-BUY / SCALP-SELL / BREAK-BUY / BREAK-SELL / WAIT
SIZING   → 1% equity risk, SL = 1.5×ATR, TP1 = 3×ATR, TP2 = 5×ATR

Chart analysis format:
**📊 MARKET STRUCTURE** | **📍 KEY LEVELS** | **📈 INDICATORS** | **🎯 SIGNAL** | **💰 TRADE PLAN** | **⚠️ RISK NOTES**

Trade monitoring: flag SL within 30 pts, suggest trailing adjustments, validate thesis, recommend exit if momentum reversed.
Be conversational. Remember context. Give specific prices, not vague zones. Be direct."""

# ── Live price thread ──────────────────────────────────────────────────────────
def price_worker():
    while True:
        if HAS_YFINANCE:
            try:
                h = yf.Ticker("GC=F").history(period="2d", interval="1m")
                if not h.empty:
                    p, p0 = float(h["Close"].iloc[-1]), float(h["Close"].iloc[-2])
                    chg = round(p - p0, 2)
                    with price_lock:
                        live_price.update(price=round(p,2), change=chg,
                                          pct=round((chg/p0)*100,3) if p0 else 0,
                                          updated=datetime.now().strftime("%H:%M:%S"))
            except Exception:
                pass
        time.sleep(30)

# ── Flask ──────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(24))

def logged_in():
    return bool(session.get("username"))

def require_login():
    if not logged_in():
        return redirect("/login")
    return None

# ── Auth routes ────────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET","POST"])
def login():
    error = ""
    if request.method == "POST":
        username = request.form.get("username","").strip().lower()
        password = request.form.get("password","")
        if not username:
            error = "Please enter a username."
        elif password != ACCESS_PASSWORD:
            error = "Wrong password. Ask the admin for the password."
        else:
            session["username"] = username
            return redirect("/")
    return LOGIN_HTML.replace("{{ERROR}}", f'<p class="err">{error}</p>' if error else "")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ── Main UI ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    redir = require_login()
    if redir: return redir
    return MAIN_HTML.replace("{{USERNAME}}", session["username"])

# ── Live price (public — needed by UI before auth sometimes) ───────────────────
@app.route("/price")
def get_price():
    with price_lock:
        return jsonify(live_price)

# ── Download TradeMonitor.mq4 pre-configured for this user ────────────────────
@app.route("/download/TradeMonitor.mq4")
def download_monitor():
    redir = require_login()
    if redir: return redir
    username   = session["username"]
    server_url = request.host_url.rstrip("/")
    mq4 = TRADE_MONITOR_TEMPLATE \
            .replace("{{SERVER_URL}}", server_url) \
            .replace("{{USERNAME}}",   username)
    return send_file(io.BytesIO(mq4.encode()),
                     mimetype="application/octet-stream",
                     as_attachment=True,
                     download_name="TradeMonitor.mq4")

# ── Per-user trades (MT4 posts here) ──────────────────────────────────────────
@app.route("/trades/<username>", methods=["GET","POST"])
def trades(username):
    u = get_user(username)
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        u["trades"] = data.get("trades", [])
        return jsonify({"status":"ok"})
    return jsonify({"trades": u["trades"]})

# ── Per-user TradingView webhook ───────────────────────────────────────────────
@app.route("/webhook/<username>", methods=["POST"])
def webhook(username):
    u    = get_user(username)
    data = request.get_json(silent=True) or {}
    msg  = data.get("message") or data.get("text") or json.dumps(data)
    ts   = datetime.now().strftime("%H:%M:%S")
    u["alerts"].append({"time": ts, "message": msg})
    u["conversation"].append({"role":"user",
                               "content": f"[TradingView Alert {ts}]: {msg}"})
    return jsonify({"status":"ok"})

@app.route("/my/trades")
def my_trades():
    redir = require_login()
    if redir: return redir
    return jsonify({"trades": get_user(session["username"])["trades"]})

@app.route("/my/alerts")
def my_alerts():
    redir = require_login()
    if redir: return redir
    return jsonify({"alerts": get_user(session["username"])["alerts"][-20:]})

@app.route("/clear", methods=["POST"])
def clear():
    redir = require_login()
    if redir: return redir
    get_user(session["username"])["conversation"].clear()
    return jsonify({"status":"cleared"})

# ── Conversational chat ────────────────────────────────────────────────────────
@app.route("/chat", methods=["POST"])
def chat():
    redir = require_login()
    if redir: return redir

    username = session["username"]
    u        = get_user(username)
    text     = request.form.get("message","").strip()
    chart    = request.files.get("chart")

    ctx = []
    with price_lock:
        if live_price["price"]:
            ctx.append(f"Live XAUUSD: ${live_price['price']} ({live_price['change']:+.2f} / {live_price['pct']:+.3f}%)")
    if u["trades"]:
        ctx.append("Open MT4 positions:\n" + json.dumps(u["trades"], indent=2))

    full_text = ("\n".join(ctx) + "\n\n" + text).strip() if ctx else text

    content = []
    if chart:
        b64  = base64.standard_b64encode(chart.read()).decode()
        fname = chart.filename.lower()
        mime  = ("image/png"  if fname.endswith(".png") else
                 "image/jpeg" if fname.endswith((".jpg",".jpeg")) else "image/png")
        content.append({"type":"image","source":{"type":"base64","media_type":mime,"data":b64}})
    content.append({"type":"text","text": full_text or "Analyze this chart."})

    u["conversation"].append({"role":"user","content":content})
    api_msgs = _clean_history(u["conversation"])

    try:
        resp  = anthropic.Anthropic(api_key=API_KEY).messages.create(
            model="claude-sonnet-4-6", max_tokens=2048,
            system=SYSTEM, messages=api_msgs)
        reply = resp.content[0].text
        u["conversation"].append({"role":"assistant","content":reply})
        return jsonify({"reply": reply})
    except Exception as e:
        u["conversation"].pop()
        return jsonify({"error": str(e)}), 500

def _clean_history(hist):
    trimmed = hist[-30:]
    last_img = max((i for i,m in enumerate(trimmed)
                    if isinstance(m["content"],list)
                    and any(c.get("type")=="image" for c in m["content"])), default=None)
    result = []
    for i, m in enumerate(trimmed):
        if isinstance(m["content"],list) and i != last_img:
            nc = [{"type":"text","text":"[chart image]"} if c.get("type")=="image" else c
                  for c in m["content"]]
            result.append({"role":m["role"],"content":nc})
        else:
            result.append(m)
    return result

# ── Embedded TradeMonitor MQ4 template ────────────────────────────────────────
TRADE_MONITOR_TEMPLATE = r"""//+------------------------------------------------------------------+
//| TradeMonitor.mq4 — Auto-configured for: {{USERNAME}}            |
//| Sends open trades to GoldScalperPro AI Agent in real time.      |
//|                                                                  |
//| SETUP (one time):                                                |
//| MT4 → Tools → Options → Expert Advisors                         |
//| ✓ Allow WebRequest for listed URL: {{SERVER_URL}}                |
//+------------------------------------------------------------------+
#property strict
#property version "1.0"

input string AgentURL     = "{{SERVER_URL}}/trades/{{USERNAME}}";
input string Username     = "{{USERNAME}}";
input int    SendInterval = 5;

datetime g_last = 0;

int OnInit(){ Print("TradeMonitor: Sending to ",AgentURL); EventSetTimer(SendInterval); return INIT_SUCCEEDED; }
void OnDeinit(const int r){ EventKillTimer(); SendTrades("[]"); }
void OnTimer(){ SendTrades(BuildJSON()); }
void OnTick(){ if(TimeCurrent()-g_last<SendInterval) return; g_last=TimeCurrent(); SendTrades(BuildJSON()); }

string BuildJSON(){
   string t=""; int n=0;
   for(int i=0;i<OrdersTotal();i++){
      if(!OrderSelect(i,SELECT_BY_POS,MODE_TRADES)) continue;
      if(OrderType()>OP_SELL) continue;
      double cur=(OrderType()==OP_BUY)?MarketInfo(OrderSymbol(),MODE_BID):MarketInfo(OrderSymbol(),MODE_ASK);
      double pt=MarketInfo(OrderSymbol(),MODE_POINT);
      double pips=(OrderType()==OP_BUY)?(cur-OrderOpenPrice())/pt:(OrderOpenPrice()-cur)/pt;
      double pnl=OrderProfit()+OrderSwap()+OrderCommission();
      double slDist=(OrderStopLoss()>0)?MathAbs(cur-OrderStopLoss())/pt:9999;
      if(n>0) t+=",";
      t+=StringFormat("{\"ticket\":%d,\"symbol\":\"%s\",\"direction\":\"%s\",\"lots\":%.2f,\"open\":%.3f,\"current\":%.3f,\"sl\":%.3f,\"tp\":%.3f,\"pnl\":%.2f,\"pips\":%.1f,\"near_sl\":%s}",
         OrderTicket(),OrderSymbol(),(OrderType()==OP_BUY)?"BUY":"SELL",OrderLots(),
         OrderOpenPrice(),cur,OrderStopLoss(),OrderTakeProfit(),pnl,pips,slDist<30?"true":"false");
      n++;
   }
   return "["+t+"]";
}

void SendTrades(string tradesJSON){
   string body="{\"trades\":"+tradesJSON+"}";
   string hdr="Content-Type: application/json\r\n";
   char post[],res[]; string rh;
   int len=StringLen(body); ArrayResize(post,len);
   StringToCharArray(body,post,0,len);
   int r=WebRequest("POST",AgentURL,hdr,3000,post,res,rh);
   if(r==-1){ int e=GetLastError();
      if(e==4060) Print("Allow WebRequest in MT4 Tools->Options->Expert Advisors. URL: {{SERVER_URL}}");
      else Print("TradeMonitor error: ",e); }
}
"""

# ── Login HTML ─────────────────────────────────────────────────────────────────
LOGIN_HTML = """<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>GoldScalperPro AI — Login</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d0f14;display:flex;align-items:center;justify-content:center;min-height:100vh;font-family:'Segoe UI',system-ui,sans-serif}
.box{background:#161920;border:1px solid #2a2d35;border-radius:14px;padding:36px 32px;width:100%;max-width:360px}
h1{color:#f5c518;font-size:1.25rem;text-align:center;margin-bottom:6px}
.sub{color:#888;font-size:.82rem;text-align:center;margin-bottom:24px}
label{display:block;color:#888;font-size:.75rem;text-transform:uppercase;letter-spacing:.8px;margin-bottom:5px}
input{width:100%;background:#0d0f14;border:1px solid #2a2d35;border-radius:7px;color:#e0e0e0;font-size:.9rem;padding:10px 12px;outline:none;margin-bottom:14px;font-family:inherit;transition:border-color .2s}
input:focus{border-color:#f5c518}
button{width:100%;background:#f5c518;color:#0d0f14;border:none;border-radius:8px;padding:11px;font-weight:700;font-size:.95rem;cursor:pointer;margin-top:4px}
.err{color:#ef5350;font-size:.82rem;text-align:center;margin-top:-8px;margin-bottom:10px}
</style></head><body>
<div class="box">
  <h1>🏆 GoldScalperPro AI</h1>
  <p class="sub">Sign in to your trading assistant</p>
  {{ERROR}}
  <form method="post">
    <label>Username</label>
    <input name="username" placeholder="e.g. lea" autocomplete="username" required/>
    <label>Password</label>
    <input name="password" type="password" placeholder="Enter access password" autocomplete="current-password" required/>
    <button type="submit">Sign In →</button>
  </form>
</div>
</body></html>"""

# ── Main app HTML ──────────────────────────────────────────────────────────────
MAIN_HTML = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>GoldScalperPro AI</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d0f14;color:#e0e0e0;font-family:'Segoe UI',system-ui,sans-serif;height:100vh;display:flex;flex-direction:column;overflow:hidden}
#header{background:#111318;border-bottom:1px solid #1f2230;padding:9px 16px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
#header h1{font-size:.95rem;color:#f5c518;font-weight:700}
#ticker{font-size:.9rem;font-weight:600}
#ticker.up{color:#26a69a}#ticker.down{color:#ef5350}#ticker.flat{color:#888}
.hbtn{background:transparent;border:1px solid #2a2d35;color:#888;border-radius:6px;padding:4px 10px;cursor:pointer;font-size:.72rem;transition:border-color .2s,color .2s;margin-left:6px;text-decoration:none}
.hbtn:hover{border-color:#f5c518;color:#f5c518}
#body{display:flex;flex:1;overflow:hidden}
#chat-panel{flex:1;display:flex;flex-direction:column;min-width:0}
#messages{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px}
#messages::-webkit-scrollbar{width:4px}
#messages::-webkit-scrollbar-thumb{background:#2a2d35;border-radius:4px}
.msg{max-width:84%;padding:10px 13px;border-radius:10px;font-size:.86rem;line-height:1.7;word-break:break-word}
.msg.user{background:#1e2235;align-self:flex-end;border-bottom-right-radius:3px}
.msg.bot{background:#161920;align-self:flex-start;border:1px solid #1f2230;border-bottom-left-radius:3px}
.msg.bot strong{color:#f5c518}
.msg img{max-width:200px;border-radius:6px;margin-top:6px;display:block}
.msg.typing{color:#444;font-style:italic}
.welcome{text-align:center;color:#444;font-size:.84rem;padding:40px 20px;line-height:1.9}
.welcome span{font-size:2rem;display:block;margin-bottom:10px}
#input-bar{border-top:1px solid #1f2230;padding:10px 12px;display:flex;align-items:flex-end;gap:8px;background:#111318;flex-shrink:0}
#attach-btn{background:#1e2235;border:1px solid #2a2d35;color:#888;border-radius:8px;padding:8px 10px;cursor:pointer;font-size:1rem;flex-shrink:0;transition:border-color .2s}
#attach-btn:hover,#attach-btn.has-file{border-color:#f5c518;color:#f5c518}
#file-input{display:none}
#msg-input{flex:1;background:#0d0f14;border:1px solid #2a2d35;border-radius:8px;color:#e0e0e0;font-size:.86rem;padding:9px 12px;resize:none;height:40px;max-height:120px;font-family:inherit;outline:none;transition:border-color .2s;line-height:1.4}
#msg-input:focus{border-color:#f5c518}
#send-btn{background:#f5c518;color:#0d0f14;border:none;border-radius:8px;padding:9px 14px;cursor:pointer;font-weight:700;font-size:.9rem;flex-shrink:0;transition:opacity .2s}
#send-btn:disabled{opacity:.4;cursor:not-allowed}
#sidebar{width:250px;border-left:1px solid #1f2230;display:flex;flex-direction:column;overflow:hidden;flex-shrink:0}
.panel{border-bottom:1px solid #1f2230;display:flex;flex-direction:column}
.ph{padding:9px 12px;font-size:.7rem;text-transform:uppercase;letter-spacing:1px;color:#888;background:#111318;flex-shrink:0}
.pb{padding:10px 12px;font-size:.78rem;overflow-y:auto;max-height:190px}
.pb::-webkit-scrollbar{width:3px}
.pb::-webkit-scrollbar-thumb{background:#2a2d35}
.trade-card{background:#0d0f14;border:1px solid #1f2230;border-radius:6px;padding:8px;margin-bottom:6px}
.tc-sym{font-weight:700;font-size:.8rem}
.dir{display:inline-block;padding:1px 6px;border-radius:3px;font-size:.68rem;font-weight:700;margin-left:4px}
.dir.buy{background:#0d2b2b;color:#26a69a}.dir.sell{background:#2b0d0d;color:#ef5350}
.tc-det{color:#888;font-size:.72rem;margin-top:2px}
.pnl{font-weight:600;font-size:.78rem;margin-top:2px}
.pnl.pos{color:#26a69a}.pnl.neg{color:#ef5350}
.near-sl{color:#f5c518;font-size:.7rem;margin-top:2px}
.no-data{color:#444;font-style:italic;font-size:.76rem}
.alert-item{border-left:2px solid #f5c518;padding:4px 8px;margin-bottom:5px;font-size:.74rem;color:#bbb}
.at{color:#888;font-size:.68rem}
#dl-section{padding:12px;border-top:1px solid #1f2230;flex-shrink:0}
#dl-section p{font-size:.72rem;color:#888;margin-bottom:6px;line-height:1.5}
#dl-section a{display:block;text-align:center;background:#1e2235;border:1px solid #2a2d35;color:#f5c518;border-radius:7px;padding:7px;font-size:.78rem;font-weight:600;text-decoration:none;transition:background .2s}
#dl-section a:hover{background:#252b40}
#tv-info{padding:10px 12px;font-size:.72rem;color:#555;line-height:1.6;border-top:1px solid #1f2230}
code{color:#f5c518;font-size:.7rem;word-break:break-all}
@media(max-width:640px){#sidebar{display:none}}
</style></head><body>

<div id="header">
  <h1>🏆 GoldScalperPro AI</h1>
  <div style="display:flex;align-items:center;gap:4px">
    <span id="ticker" class="flat">XAUUSD —</span>
    <span style="color:#555;font-size:.75rem;margin-left:8px">{{USERNAME}}</span>
    <button class="hbtn" onclick="clearChat()">Clear</button>
    <a class="hbtn" href="/logout">Sign out</a>
  </div>
</div>

<div id="body">
  <div id="chat-panel">
    <div id="messages">
      <div class="welcome">
        <span>📈</span>
        Welcome, <strong style="color:#f5c518">{{USERNAME}}</strong>!<br>
        Ask anything about Gold, attach a chart for analysis,<br>
        or type <em>"check my trades"</em> to review your open positions.
      </div>
    </div>
    <div id="input-bar">
      <button id="attach-btn" onclick="document.getElementById('file-input').click()" title="Attach chart">📎</button>
      <input type="file" id="file-input" accept="image/*" onchange="onFileSelected(this)"/>
      <textarea id="msg-input" placeholder="Ask about Gold, attach a chart, or say 'check my trades'…" onkeydown="onKey(event)" oninput="autoResize(this)"></textarea>
      <button id="send-btn" onclick="sendMessage()">▶</button>
    </div>
  </div>

  <div id="sidebar">
    <div class="panel">
      <div class="ph">📊 My Open MT4 Trades</div>
      <div class="pb" id="trades-panel">
        <div class="no-data">No trades yet.<br>Download TradeMonitor below.</div>
      </div>
    </div>

    <div class="panel" style="flex:1">
      <div class="ph">⚡ TradingView Alerts</div>
      <div class="pb" id="alerts-panel">
        <div class="no-data" id="no-alerts">No alerts yet.</div>
      </div>
    </div>

    <div id="dl-section">
      <p>Connect your MT4 account — download your personal TradeMonitor (pre-configured):</p>
      <a href="/download/TradeMonitor.mq4">⬇ Download TradeMonitor.mq4</a>
    </div>

    <div id="tv-info">
      <strong style="color:#888">TradingView webhook URL:</strong><br>
      <code id="tv-url">Loading…</code>
    </div>
  </div>
</div>

<script>
let selectedFile = null;

// Show personalised TradingView webhook URL
document.getElementById('tv-url').textContent = window.location.origin + '/webhook/{{USERNAME}}';

function onFileSelected(input){
  selectedFile = input.files[0]||null;
  document.getElementById('attach-btn').classList.toggle('has-file',!!selectedFile);
}
function autoResize(el){ el.style.height='40px'; el.style.height=Math.min(el.scrollHeight,120)+'px'; }
function onKey(e){ if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage();} }

async function sendMessage(){
  const input = document.getElementById('msg-input');
  const text  = input.value.trim();
  if(!text && !selectedFile) return;

  const sendBtn = document.getElementById('send-btn');
  sendBtn.disabled = true;

  const msgs = document.getElementById('messages');
  msgs.querySelector('.welcome')?.remove();

  const ud = document.createElement('div');
  ud.className = 'msg user';
  if(selectedFile){ const img=document.createElement('img'); img.src=URL.createObjectURL(selectedFile); ud.appendChild(img); }
  if(text) ud.appendChild(document.createTextNode(text));
  msgs.appendChild(ud);

  const typing = document.createElement('div');
  typing.className = 'msg bot typing';
  typing.textContent = 'Analyzing…';
  msgs.appendChild(typing);
  msgs.scrollTop = msgs.scrollHeight;

  input.value = ''; input.style.height = '40px';

  const fd = new FormData();
  if(text) fd.append('message', text);
  if(selectedFile) fd.append('chart', selectedFile, selectedFile.name);

  selectedFile = null;
  document.getElementById('file-input').value = '';
  document.getElementById('attach-btn').classList.remove('has-file');

  try{
    const data = await (await fetch('/chat',{method:'POST',body:fd})).json();
    typing.remove();
    const bd = document.createElement('div');
    bd.className = 'msg bot';
    bd.innerHTML = fmt(data.reply || 'Error: '+(data.error||'unknown'));
    msgs.appendChild(bd);
  } catch(e){
    typing.remove();
    const ed=document.createElement('div'); ed.className='msg bot';
    ed.textContent='Connection error.'; msgs.appendChild(ed);
  }
  msgs.scrollTop = msgs.scrollHeight;
  sendBtn.disabled = false;
  input.focus();
}

function fmt(t){
  return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
          .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/\n/g,'<br>');
}

async function clearChat(){
  await fetch('/clear',{method:'POST'});
  const msgs=document.getElementById('messages');
  msgs.innerHTML='<div class="welcome"><span>📈</span>Chat cleared.</div>';
}

async function updatePrice(){
  try{
    const d=await (await fetch('/price')).json();
    if(d.price){
      const el=document.getElementById('ticker');
      const s=d.change>=0?'+':'';
      el.textContent=`XAUUSD $${d.price}  ${s}${d.change}`;
      el.className=d.change>0?'up':d.change<0?'down':'flat';
    }
  }catch(e){}
}

async function updateTrades(){
  try{
    const d=await (await fetch('/my/trades')).json();
    const p=document.getElementById('trades-panel');
    if(!d.trades?.length){ p.innerHTML='<div class="no-data">No open trades.</div>'; return; }
    p.innerHTML=d.trades.map(t=>{
      const pc=t.pnl>=0?'pos':'neg', s=t.pnl>=0?'+':'', dc=t.direction==='BUY'?'buy':'sell';
      return `<div class="trade-card">
        <div><span class="tc-sym">${t.symbol}</span><span class="dir ${dc}">${t.direction}</span></div>
        <div class="tc-det">Lots:${t.lots} | Open:${t.open} | Now:${t.current}</div>
        <div class="tc-det">SL:${t.sl||'—'} | TP:${t.tp||'—'}</div>
        <div class="pnl ${pc}">${s}$${t.pnl.toFixed(2)} (${t.pips.toFixed(1)}pts)</div>
        ${t.near_sl?'<div class="near-sl">⚠ Price near stop loss!</div>':''}
      </div>`;
    }).join('');
  }catch(e){}
}

async function updateAlerts(){
  try{
    const d=await (await fetch('/my/alerts')).json();
    if(!d.alerts?.length) return;
    document.getElementById('no-alerts')?.remove();
    document.getElementById('alerts-panel').innerHTML=d.alerts.slice().reverse().map(a=>
      `<div class="alert-item"><div class="at">${a.time}</div>${a.message.replace(/</g,'&lt;')}</div>`
    ).join('');
  }catch(e){}
}

updatePrice();  setInterval(updatePrice,  30000);
updateTrades(); setInterval(updateTrades, 8000);
updateAlerts(); setInterval(updateAlerts, 12000);
</script></body></html>"""

if __name__ == "__main__":
    if HAS_YFINANCE:
        threading.Thread(target=price_worker, daemon=True).start()
        print(" Live price feed active")
    print(f"\n GoldScalperPro AI Agent v3")
    print(f" URL      : http://localhost:5000")
    print(f" Password : {ACCESS_PASSWORD}")
    print(f" Change password: set ACCESS_PASSWORD=yourpassword before running\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
