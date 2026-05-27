"""
GoldScalperPro AI Agent — Final Version
Login | Capital.com Live Account | TradingView Alerts | Conversational AI

pip install anthropic flask yfinance requests
set ANTHROPIC_API_KEY=... && set ACCESS_PASSWORD=gold2024 && python gold_agent.py
"""

import base64, os, json, threading, time, secrets, io
from datetime import datetime
from flask import Flask, request, jsonify, session, redirect, send_file
import anthropic

try:
    import requests as http
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

API_KEY         = os.environ.get("ANTHROPIC_API_KEY", "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")
ACCESS_PASSWORD = os.environ.get("ACCESS_PASSWORD", "gold2024")

# ── In-memory user store ──────────────────────────────────────────────────────
users = {}  # {username: {conversation, alerts, capital_client}}

def get_user(u):
    if u not in users:
        users[u] = {"conversation": [], "alerts": [], "capital": None}
    return users[u]

# ── Global price fallback ──────────────────────────────────────────────────────
live_price = {"price": None, "change": None, "updated": None}
price_lock = threading.Lock()

# ── Capital.com API client ─────────────────────────────────────────────────────
class CapitalClient:
    BASE = "https://api-capital.backend.gb.capitalise.ai"

    def __init__(self, api_key, identifier, password, demo=False):
        self.api_key    = api_key
        self.identifier = identifier
        self.password   = password
        self.demo       = demo
        self.cst        = None
        self.token      = None
        self.connected  = False
        self.error      = ""
        if demo:
            self.BASE = "https://api-capital.backend.gb.capitalise.ai"

    def _h(self):
        return {"X-CAP-API-KEY": self.api_key,
                "CST": self.cst or "",
                "X-SECURITY-TOKEN": self.token or "",
                "Content-Type": "application/json"}

    def login(self):
        try:
            r = http.post(f"{self.BASE}/api/v1/session",
                          headers={"X-CAP-API-KEY": self.api_key,
                                   "Content-Type": "application/json"},
                          json={"identifier": self.identifier,
                                "password":   self.password},
                          timeout=10)
            if r.status_code == 200:
                self.cst   = r.headers.get("CST")
                self.token = r.headers.get("X-SECURITY-TOKEN")
                self.connected = True
                self.error = ""
                return True
            self.error = f"Login failed ({r.status_code}): {r.text[:120]}"
        except Exception as e:
            self.error = str(e)
        self.connected = False
        return False

    def _get(self, path, params=None):
        try:
            r = http.get(f"{self.BASE}{path}", headers=self._h(),
                         params=params, timeout=10)
            if r.status_code == 401:
                if self.login():
                    r = http.get(f"{self.BASE}{path}", headers=self._h(),
                                 params=params, timeout=10)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return None

    def positions(self):
        data = self._get("/api/v1/positions")
        if not data:
            return []
        result = []
        for item in data.get("positions", []):
            pos = item.get("position", {})
            mkt = item.get("market", {})
            bid = mkt.get("bid", 0)
            offer = mkt.get("offer", 0)
            current = bid if pos.get("direction") == "BUY" else offer
            open_lvl = pos.get("level", 0)
            direction = pos.get("direction", "")
            pts = (current - open_lvl) if direction == "BUY" else (open_lvl - current)
            sl = pos.get("stopLevel")
            sl_dist = abs(current - sl) if sl else 9999
            result.append({
                "symbol":    mkt.get("instrumentName", mkt.get("epic","")),
                "direction": direction,
                "size":      pos.get("size", 0),
                "open":      round(open_lvl, 3),
                "current":   round(current, 3),
                "sl":        round(sl, 3) if sl else None,
                "tp":        round(pos.get("limitLevel"), 3) if pos.get("limitLevel") else None,
                "pnl":       round(pos.get("upl", 0), 2),
                "pts":       round(pts, 1),
                "near_sl":   sl_dist < 30
            })
        return result

    def gold_price(self):
        data = self._get("/api/v1/prices/GOLD",
                         {"resolution": "MINUTE", "max": 2})
        if data and "prices" in data and len(data["prices"]) >= 2:
            prices = data["prices"]
            p  = (prices[-1]["closePrice"]["bid"] + prices[-1]["closePrice"]["ask"]) / 2
            p0 = (prices[-2]["closePrice"]["bid"] + prices[-2]["closePrice"]["ask"]) / 2
            return round(p, 2), round(p - p0, 2)
        return None, None

    def account_info(self):
        data = self._get("/api/v1/accounts")
        if data and "accounts" in data:
            acc = data["accounts"][0]
            return {
                "balance":  acc.get("balance", {}).get("balance", 0),
                "equity":   acc.get("balance", {}).get("equity", 0),
                "currency": acc.get("currency", "USD")
            }
        return None

# ── Fallback price thread ─────────────────────────────────────────────────────
def price_worker():
    while True:
        if HAS_YFINANCE:
            try:
                h = yf.Ticker("GC=F").history(period="2d", interval="1m")
                if not h.empty:
                    p = float(h["Close"].iloc[-1])
                    p0 = float(h["Close"].iloc[-2])
                    with price_lock:
                        live_price.update(price=round(p,2),
                                          change=round(p-p0,2),
                                          updated=datetime.now().strftime("%H:%M:%S"))
            except Exception:
                pass
        time.sleep(30)

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM = """You are GoldScalperPro AI — a professional Gold (XAU/USD) trading assistant.

You have real-time access to:
- Live XAUUSD price from the user's Capital.com account
- User's open Capital.com positions (size, direction, P&L, stop loss)
- Account balance and equity
- TradingView alerts (injected when received)
- Full conversation history

You think using the GoldScalperPro strategy:
TREND    → EMA 8/21/50 stack  |  MOMENTUM → RSI 14 + MACD
LEVELS   → 20-bar swing high/low  |  SIGNALS → SCALP-BUY / SCALP-SELL / BREAK-BUY / BREAK-SELL / WAIT
SIZING   → 1% equity risk per trade, SL = 1.5×ATR, TP1 = 3×ATR, TP2 = 5×ATR

When user asks "should I trade?" or "what should I do?":
1. Check their open positions first
2. Assess current price vs their entries
3. Give a clear action: Hold / Add / Cut / Wait for new setup
4. Give specific price levels

When analyzing a chart image:
**📊 MARKET STRUCTURE** | **📍 KEY LEVELS** | **📈 INDICATORS** | **🎯 SIGNAL** | **💰 TRADE PLAN** | **⚠️ RISK NOTES**

Trade monitoring rules:
- Warn immediately if any position has stop loss within 30 points of current price
- Suggest trailing stop adjustments
- Recommend exit if original thesis has been invalidated

Be conversational, direct, and decisive. Remember full conversation context.
Give specific prices. Never say "it depends" without giving a concrete recommendation."""

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(24))

def auth():
    if not session.get("username"):
        return redirect("/login")

@app.route("/login", methods=["GET","POST"])
def login():
    err = ""
    if request.method == "POST":
        uname = request.form.get("username","").strip().lower().replace(" ","_")
        pwd   = request.form.get("password","")
        if not uname:
            err = "Please enter a username."
        elif pwd != ACCESS_PASSWORD:
            err = "Wrong password."
        else:
            session["username"] = uname
            return redirect("/")
    return LOGIN_HTML.replace("{{ERR}}", f'<p class="err">{err}</p>' if err else "")

@app.route("/logout")
def logout():
    session.clear(); return redirect("/login")

@app.route("/")
def index():
    if not session.get("username"): return redirect("/login")
    return MAIN_HTML.replace("{{UN}}", session["username"])

# ── Capital.com connection ────────────────────────────────────────────────────
@app.route("/connect", methods=["POST"])
def connect():
    if not session.get("username"): return jsonify({"error":"not logged in"}), 401
    d    = request.get_json(silent=True) or {}
    demo = d.get("demo", False)
    client = CapitalClient(d.get("api_key",""), d.get("identifier",""),
                           d.get("password",""), demo)
    if client.login():
        get_user(session["username"])["capital"] = client
        info = client.account_info()
        return jsonify({"status":"connected", "account": info})
    return jsonify({"status":"error", "message": client.error}), 400

@app.route("/my/status")
def my_status():
    if not session.get("username"): return jsonify({"connected":False})
    c = get_user(session["username"]).get("capital")
    return jsonify({"connected": bool(c and c.connected)})

@app.route("/my/positions")
def my_positions():
    if not session.get("username"): return jsonify({"positions":[]})
    u = get_user(session["username"])
    c = u.get("capital")
    if c and c.connected:
        return jsonify({"positions": c.positions(), "source": "capital"})
    return jsonify({"positions": [], "source": "none"})

@app.route("/my/price")
def my_price():
    if not session.get("username"): return jsonify({})
    u = get_user(session["username"])
    c = u.get("capital")
    if c and c.connected:
        p, chg = c.gold_price()
        if p:
            return jsonify({"price": p, "change": chg, "source": "capital"})
    with price_lock:
        return jsonify({**live_price, "source": "yfinance"})

@app.route("/my/account")
def my_account():
    if not session.get("username"): return jsonify({})
    c = get_user(session["username"]).get("capital")
    if c and c.connected:
        return jsonify(c.account_info() or {})
    return jsonify({})

@app.route("/my/alerts")
def my_alerts():
    if not session.get("username"): return jsonify({"alerts":[]})
    return jsonify({"alerts": get_user(session["username"])["alerts"][-20:]})

# ── TradingView webhook ───────────────────────────────────────────────────────
@app.route("/webhook/<username>", methods=["POST"])
def webhook(username):
    u   = get_user(username)
    d   = request.get_json(silent=True) or {}
    msg = d.get("message") or d.get("text") or json.dumps(d)
    ts  = datetime.now().strftime("%H:%M:%S")
    u["alerts"].append({"time": ts, "message": msg})
    u["conversation"].append({"role":"user",
                               "content": f"[TradingView Alert {ts}]: {msg}\nPlease acknowledge and assess impact on my current positions."})
    return jsonify({"status":"ok"})

@app.route("/clear", methods=["POST"])
def clear():
    if session.get("username"):
        get_user(session["username"])["conversation"].clear()
    return jsonify({"status":"cleared"})

# ── Chat ──────────────────────────────────────────────────────────────────────
@app.route("/chat", methods=["POST"])
def chat():
    if not session.get("username"): return jsonify({"error":"not logged in"}), 401
    username = session["username"]
    u        = get_user(username)
    text     = request.form.get("message","").strip()
    chart    = request.files.get("chart")
    c        = u.get("capital")

    ctx = []
    if c and c.connected:
        p, chg = c.gold_price()
        if p: ctx.append(f"Live XAUUSD: ${p} ({chg:+.2f})")
        positions = c.positions()
        if positions: ctx.append("Open positions:\n" + json.dumps(positions, indent=2))
        info = c.account_info()
        if info: ctx.append(f"Account: Balance ${info.get('balance',0):.2f} | Equity ${info.get('equity',0):.2f}")
    else:
        with price_lock:
            if live_price["price"]:
                ctx.append(f"Live XAUUSD: ${live_price['price']} ({live_price['change']:+.2f}) [yfinance]")

    full_text = ("\n".join(ctx) + "\n\n" + text).strip() if ctx else text
    content = []
    if chart:
        b64   = base64.standard_b64encode(chart.read()).decode()
        fname = chart.filename.lower()
        mime  = "image/png" if fname.endswith(".png") else "image/jpeg"
        content.append({"type":"image","source":{"type":"base64","media_type":mime,"data":b64}})
    content.append({"type":"text","text": full_text or "What should I do right now with Gold?"})
    u["conversation"].append({"role":"user","content":content})

    try:
        resp = anthropic.Anthropic(api_key=API_KEY).messages.create(
            model="claude-sonnet-4-6", max_tokens=2048,
            system=SYSTEM, messages=_trim(u["conversation"]))
        reply = resp.content[0].text
        u["conversation"].append({"role":"assistant","content":reply})
        return jsonify({"reply": reply})
    except Exception as e:
        u["conversation"].pop()
        return jsonify({"error": str(e)}), 500

def _trim(hist):
    t = hist[-30:]
    last_img = max((i for i,m in enumerate(t)
                    if isinstance(m["content"],list)
                    and any(c.get("type")=="image" for c in m["content"])), default=None)
    out = []
    for i, m in enumerate(t):
        if isinstance(m["content"],list) and i != last_img:
            nc = [{"type":"text","text":"[chart]"} if c.get("type")=="image" else c
                  for c in m["content"]]
            out.append({"role":m["role"],"content":nc})
        else:
            out.append(m)
    return out

# ── HTML templates ────────────────────────────────────────────────────────────
LOGIN_HTML = """<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>GoldScalperPro AI</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d0f14;display:flex;align-items:center;justify-content:center;min-height:100vh;font-family:'Segoe UI',system-ui,sans-serif}
.box{background:#161920;border:1px solid #2a2d35;border-radius:14px;padding:40px 32px;width:100%;max-width:380px}
h1{color:#f5c518;font-size:1.3rem;text-align:center;margin-bottom:4px}
.sub{color:#888;font-size:.82rem;text-align:center;margin-bottom:28px}
label{display:block;color:#888;font-size:.72rem;text-transform:uppercase;letter-spacing:.8px;margin-bottom:5px}
input{width:100%;background:#0d0f14;border:1px solid #2a2d35;border-radius:7px;color:#e0e0e0;font-size:.9rem;padding:11px 13px;outline:none;margin-bottom:16px;font-family:inherit;transition:border-color .2s}
input:focus{border-color:#f5c518}
button{width:100%;background:#f5c518;color:#0d0f14;border:none;border-radius:8px;padding:12px;font-weight:700;font-size:.95rem;cursor:pointer}
.err{color:#ef5350;font-size:.82rem;text-align:center;margin-bottom:12px}
</style></head><body>
<div class="box">
  <h1>🏆 GoldScalperPro AI</h1>
  <p class="sub">Your personal Gold trading assistant</p>
  {{ERR}}
  <form method="post">
    <label>Your name</label>
    <input name="username" placeholder="e.g. lea" autocomplete="username" required/>
    <label>Access password</label>
    <input name="password" type="password" placeholder="Enter password" required/>
    <button>Sign In →</button>
  </form>
</div></body></html>"""

MAIN_HTML = """<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>GoldScalperPro AI</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d0f14;color:#e0e0e0;font-family:'Segoe UI',system-ui,sans-serif;height:100vh;display:flex;flex-direction:column;overflow:hidden}
#hdr{background:#111318;border-bottom:1px solid #1f2230;padding:9px 16px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
#hdr h1{font-size:.95rem;color:#f5c518;font-weight:700}
#ticker{font-size:.88rem;font-weight:600;padding:2px 8px;border-radius:4px}
.up{color:#26a69a}.down{color:#ef5350}.flat{color:#888}
.hbtn{background:transparent;border:1px solid #2a2d35;color:#888;border-radius:5px;padding:3px 9px;cursor:pointer;font-size:.71rem;margin-left:5px;text-decoration:none;transition:all .15s}
.hbtn:hover{border-color:#f5c518;color:#f5c518}
#body{display:flex;flex:1;overflow:hidden}
#chat{flex:1;display:flex;flex-direction:column;min-width:0}
#msgs{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px}
#msgs::-webkit-scrollbar{width:3px}
#msgs::-webkit-scrollbar-thumb{background:#2a2d35;border-radius:3px}
.msg{max-width:85%;padding:9px 12px;border-radius:10px;font-size:.85rem;line-height:1.7;word-break:break-word}
.u{background:#1e2235;align-self:flex-end;border-bottom-right-radius:3px}
.b{background:#161920;border:1px solid #1f2230;align-self:flex-start;border-bottom-left-radius:3px}
.b strong{color:#f5c518}
.b img.ci{max-width:180px;border-radius:5px;margin-top:5px;display:block}
.typ{color:#444;font-style:italic}
.wel{text-align:center;color:#444;font-size:.83rem;padding:32px 16px;line-height:1.9}
.wel b{color:#f5c518}
#ibar{border-top:1px solid #1f2230;padding:9px 11px;display:flex;align-items:flex-end;gap:7px;background:#111318;flex-shrink:0}
#att{background:#1e2235;border:1px solid #2a2d35;color:#888;border-radius:7px;padding:7px 9px;cursor:pointer;flex-shrink:0;transition:all .15s}
#att:hover,#att.on{border-color:#f5c518;color:#f5c518}
#fi{display:none}
#ti{flex:1;background:#0d0f14;border:1px solid #2a2d35;border-radius:7px;color:#e0e0e0;font-size:.85rem;padding:8px 11px;resize:none;height:38px;max-height:110px;font-family:inherit;outline:none;transition:border-color .2s;line-height:1.4}
#ti:focus{border-color:#f5c518}
#sb{background:#f5c518;color:#0d0f14;border:none;border-radius:7px;padding:8px 13px;cursor:pointer;font-weight:700;font-size:.88rem;flex-shrink:0}
#sb:disabled{opacity:.4;cursor:not-allowed}
#side{width:240px;border-left:1px solid #1f2230;display:flex;flex-direction:column;overflow-y:auto;flex-shrink:0;font-size:.77rem}
#side::-webkit-scrollbar{width:3px}
.sec{border-bottom:1px solid #1f2230}
.sh{padding:8px 11px;font-size:.68rem;text-transform:uppercase;letter-spacing:1px;color:#888;background:#111318;position:sticky;top:0}
.sb2{padding:10px 11px}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px}
.dot.on{background:#26a69a}.dot.off{background:#555}
.cf label{display:block;color:#666;font-size:.68rem;margin-bottom:3px;margin-top:7px}
.cf input{width:100%;background:#0d0f14;border:1px solid #2a2d35;border-radius:5px;color:#e0e0e0;font-size:.75rem;padding:5px 7px;outline:none;font-family:inherit}
.cf input:focus{border-color:#f5c518}
.cbtn{width:100%;background:#1e2235;border:1px solid #2a2d35;color:#f5c518;border-radius:6px;padding:6px;cursor:pointer;font-size:.75rem;font-weight:600;margin-top:9px;transition:background .15s}
.cbtn:hover{background:#252b40}
.cerr{color:#ef5350;font-size:.7rem;margin-top:4px}
.tc{background:#0d0f14;border:1px solid #1f2230;border-radius:5px;padding:7px;margin-bottom:6px}
.tc .sym{font-weight:700;font-size:.78rem}
.dir{display:inline-block;padding:1px 5px;border-radius:3px;font-size:.66rem;font-weight:700;margin-left:3px}
.buy{background:#0d2b2b;color:#26a69a}.sell{background:#2b0d0d;color:#ef5350}
.td{color:#666;font-size:.7rem;margin-top:2px}
.pnl{font-weight:600;font-size:.77rem;margin-top:2px}
.pos{color:#26a69a}.neg{color:#ef5350}
.warn{color:#f5c518;font-size:.68rem;margin-top:1px}
.nd{color:#444;font-style:italic;font-size:.73rem}
.al{border-left:2px solid #f5c518;padding:3px 7px;margin-bottom:4px}
.at{color:#888;font-size:.67rem}
.acbx{background:#0d0f14;border-radius:5px;padding:7px;font-size:.77rem}
.acbx .lbl{color:#888;font-size:.68rem}
.acbx .val{color:#e0e0e0;font-weight:600}
.tvurl{word-break:break-all;color:#f5c518;font-size:.69rem;background:#0d0f14;padding:5px 7px;border-radius:4px;border:1px solid #1f2230;margin-top:4px}
@media(max-width:600px){#side{display:none}}
</style></head><body>

<div id="hdr">
  <h1>🏆 GoldScalperPro AI</h1>
  <div style="display:flex;align-items:center">
    <span id="ticker" class="flat">XAUUSD —</span>
    <span style="color:#555;font-size:.72rem;margin-left:8px">{{UN}}</span>
    <button class="hbtn" onclick="clearChat()">Clear</button>
    <a class="hbtn" href="/logout">Sign out</a>
  </div>
</div>

<div id="body">
  <div id="chat">
    <div id="msgs">
      <div class="wel">
        Welcome back, <b>{{UN}}</b> 👋<br>
        Connect your Capital.com account in the sidebar →<br>
        Then ask me anything: <em>"Should I trade Gold right now?"</em><br>
        or attach a chart for a full analysis.
      </div>
    </div>
    <div id="ibar">
      <button id="att" onclick="document.getElementById('fi').click()" title="Attach chart">📎</button>
      <input type="file" id="fi" accept="image/*" onchange="onFile(this)"/>
      <textarea id="ti" placeholder="Ask about Gold, attach a chart, or say 'check my trades'…" onkeydown="onKey(event)" oninput="ar(this)"></textarea>
      <button id="sb" onclick="send()">▶</button>
    </div>
  </div>

  <div id="side">

    <!-- Account -->
    <div class="sec">
      <div class="sh">💳 Capital.com Account</div>
      <div class="sb2">
        <div id="conn-status"><span class="dot off"></span>Not connected</div>
        <div id="acct-info" style="display:none" class="acbx" style="margin-top:8px"></div>
        <div id="conn-form" class="cf">
          <label>API Key</label>
          <input id="c-key" placeholder="From Capital.com settings"/>
          <label>Email</label>
          <input id="c-id" placeholder="your@email.com" type="email"/>
          <label>Password</label>
          <input id="c-pw" placeholder="Capital.com password" type="password"/>
          <label style="display:flex;align-items:center;gap:5px;cursor:pointer;color:#888;margin-top:7px">
            <input type="checkbox" id="c-demo" style="width:auto"> Demo account
          </label>
          <button class="cbtn" onclick="connectCapital()">Connect Account</button>
          <div class="cerr" id="cerr"></div>
        </div>
      </div>
    </div>

    <!-- Positions -->
    <div class="sec">
      <div class="sh">📊 Open Positions</div>
      <div class="sb2" id="pos-panel"><div class="nd">Connect account to see positions.</div></div>
    </div>

    <!-- TV Alerts -->
    <div class="sec">
      <div class="sh">⚡ TradingView Alerts</div>
      <div class="sb2" id="al-panel"><div class="nd">No alerts yet.</div></div>
      <div class="sb2" style="padding-top:0">
        <div style="color:#666;font-size:.68rem;margin-bottom:4px">Your webhook URL:</div>
        <div class="tvurl" id="tvurl">—</div>
      </div>
    </div>

  </div>
</div>

<script>
let selFile = null;
document.getElementById('tvurl').textContent = window.location.origin + '/webhook/{{UN}}';

function onFile(i){ selFile=i.files[0]||null; document.getElementById('att').classList.toggle('on',!!selFile); }
function ar(el){ el.style.height='38px'; el.style.height=Math.min(el.scrollHeight,110)+'px'; }
function onKey(e){ if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();} }

async function send(){
  const ti=document.getElementById('ti'), txt=ti.value.trim();
  if(!txt&&!selFile) return;
  const sb=document.getElementById('sb'); sb.disabled=true;
  const msgs=document.getElementById('msgs');
  msgs.querySelector('.wel')?.remove();

  const ud=document.createElement('div'); ud.className='msg u';
  if(selFile){const img=document.createElement('img');img.className='ci';img.src=URL.createObjectURL(selFile);ud.appendChild(img);}
  if(txt) ud.appendChild(document.createTextNode(txt));
  msgs.appendChild(ud);

  const typ=document.createElement('div'); typ.className='msg b typ'; typ.textContent='Analyzing…';
  msgs.appendChild(typ); msgs.scrollTop=msgs.scrollHeight;
  ti.value=''; ti.style.height='38px';

  const fd=new FormData();
  if(txt) fd.append('message',txt);
  if(selFile) fd.append('chart',selFile,selFile.name);
  selFile=null; document.getElementById('fi').value=''; document.getElementById('att').classList.remove('on');

  try{
    const d=await(await fetch('/chat',{method:'POST',body:fd})).json();
    typ.remove();
    const bd=document.createElement('div'); bd.className='msg b';
    bd.innerHTML=fmt(d.reply||'Error: '+(d.error||'?')); msgs.appendChild(bd);
  }catch(e){ typ.remove(); addMsg('Connection error.'); }
  msgs.scrollTop=msgs.scrollHeight; sb.disabled=false; ti.focus();
}

function addMsg(t){ const d=document.createElement('div'); d.className='msg b'; d.textContent=t; document.getElementById('msgs').appendChild(d); }
function fmt(t){ return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/\n/g,'<br>'); }
async function clearChat(){ await fetch('/clear',{method:'POST'}); document.getElementById('msgs').innerHTML='<div class="wel">Chat cleared.</div>'; }

async function connectCapital(){
  const cerr=document.getElementById('cerr');
  cerr.textContent='Connecting…';
  const body={api_key:document.getElementById('c-key').value.trim(),
               identifier:document.getElementById('c-id').value.trim(),
               password:document.getElementById('c-pw').value,
               demo:document.getElementById('c-demo').checked};
  try{
    const d=await(await fetch('/connect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
    if(d.status==='connected'){
      cerr.textContent='';
      document.getElementById('conn-form').style.display='none';
      document.getElementById('conn-status').innerHTML='<span class="dot on"></span>Connected ✓';
      if(d.account){
        const ai=document.getElementById('acct-info');
        ai.style.display='block';
        ai.innerHTML=`<div class="lbl">Balance</div><div class="val">$${d.account.balance?.toFixed(2)||'—'} ${d.account.currency||''}</div><div class="lbl" style="margin-top:4px">Equity</div><div class="val">$${d.account.equity?.toFixed(2)||'—'}</div>`;
      }
      refreshPositions(); refreshAlerts();
    } else { cerr.textContent = d.message||'Connection failed. Check credentials.'; }
  }catch(e){ cerr.textContent='Server error. Try again.'; }
}

async function refreshPrice(){
  try{
    const d=await(await fetch('/my/price')).json();
    if(d.price){
      const el=document.getElementById('ticker');
      const s=d.change>=0?'+':'';
      el.textContent=`XAUUSD $${d.price}  ${s}${d.change}`;
      el.className=d.change>0?'up':d.change<0?'down':'flat';
    }
  }catch(e){}
}

async function refreshPositions(){
  try{
    const d=await(await fetch('/my/positions')).json();
    const p=document.getElementById('pos-panel');
    if(!d.positions?.length){ p.innerHTML='<div class="nd">No open positions.</div>'; return; }
    p.innerHTML=d.positions.map(t=>{
      const pc=t.pnl>=0?'pos':'neg', sg=t.pnl>=0?'+':'', dc=t.direction==='BUY'?'buy':'sell';
      return `<div class="tc"><span class="sym">${t.symbol}</span><span class="dir ${dc}">${t.direction}</span>
        <div class="td">Size:${t.size} | Open:${t.open}</div>
        <div class="td">SL:${t.sl||'—'} | TP:${t.tp||'—'}</div>
        <div class="pnl ${pc}">${sg}$${t.pnl.toFixed(2)} (${t.pts}pts)</div>
        ${t.near_sl?'<div class="warn">⚠ Near stop loss!</div>':''}</div>`;
    }).join('');
  }catch(e){}
}

async function refreshAlerts(){
  try{
    const d=await(await fetch('/my/alerts')).json();
    if(!d.alerts?.length) return;
    document.getElementById('al-panel').innerHTML=d.alerts.slice().reverse().map(a=>
      `<div class="al"><div class="at">${a.time}</div>${a.message.replace(/</g,'&lt;')}</div>`
    ).join('');
  }catch(e){}
}

refreshPrice(); setInterval(refreshPrice,30000);
refreshPositions(); setInterval(refreshPositions,10000);
refreshAlerts(); setInterval(refreshAlerts,12000);
</script></body></html>"""

if __name__ == "__main__":
    if HAS_YFINANCE:
        threading.Thread(target=price_worker, daemon=True).start()
    print(f"\n GoldScalperPro AI — Final Version")
    print(f" Open   : http://localhost:5000")
    print(f" Password: {ACCESS_PASSWORD}  (change: set ACCESS_PASSWORD=yourpassword)\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
