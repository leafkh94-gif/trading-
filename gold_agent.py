"""
Trading AI — Simple Chat
Type a question or attach any chart. Works for Gold, NAS100, stocks, anything.
Run:  python gold_agent.py
Open: http://localhost:5000
"""

import base64, os, pathlib
from flask import Flask, request, jsonify
import anthropic

# ── Load .env from the same folder as this script ─────────────────────────────
# Built-in parser: handles UTF-8 BOM (PowerShell Out-File adds one) and quotes.
# No external library needed.
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

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

conversation = []

SYSTEM = """You are a professional trading analyst. You cover every market — Gold, NAS100, SP500, DOW, forex, stocks, crypto — any instrument the user mentions.

When the user sends a chart image:
• State the trend clearly (Bullish / Bearish / Sideways)
• List key support and resistance price levels
• Identify any chart patterns
• Read visible indicators (RSI, MACD, MAs, volume)
• Give one clear decision: BUY / SELL / WAIT
• Provide entry price, stop-loss, and target(s)

When the user asks a text question about any trade or market:
• Give a direct, specific answer with price levels
• Include a clear trade recommendation and risk management
• Be concise — no filler, no vague language

You remember the full conversation. Build on prior context. Ask for the ticker or timeframe if it helps."""


app = Flask(__name__)


@app.route("/")
def index():
    return HTML


@app.route("/clear", methods=["POST"])
def clear():
    conversation.clear()
    return jsonify({"status": "cleared"})


@app.route("/chat", methods=["POST"])
def chat():
    global conversation

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
        for msg in conversation:
            if isinstance(msg["content"], list):
                for p in msg["content"]:
                    if p.get("type") == "image":
                        p.clear()
                        p.update({"type": "text", "text": "[earlier chart]"})

    content.append({"type": "text", "text": text if text else "Analyze this chart and give me a clear recommendation."})
    conversation.append({"role": "user", "content": content})

    try:
        client = anthropic.Anthropic(api_key=API_KEY)
        resp   = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SYSTEM,
            messages=conversation[-30:],
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
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"/>
<title>Trading AI</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;background:#0d0f14;color:#e0e0e0;font-family:'Segoe UI',system-ui,sans-serif;overflow:hidden}
body{display:flex;flex-direction:column}

/* Header */
#hdr{background:#111318;border-bottom:1px solid #1e2130;padding:10px 16px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
#hdr h1{font-size:.95rem;color:#f5c518;font-weight:700;letter-spacing:.4px}
#clear-btn{background:transparent;border:1px solid #2a2d35;color:#777;border-radius:6px;padding:4px 12px;cursor:pointer;font-size:.75rem}
#clear-btn:hover{border-color:#f5c518;color:#f5c518}

/* Messages */
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

/* Input bar */
#bar{border-top:1px solid #1e2130;padding:10px 12px;display:flex;align-items:flex-end;gap:8px;background:#111318;flex-shrink:0}

/* Attach — file input overlays the icon div */
#aw{position:relative;width:40px;height:40px;flex-shrink:0;border-radius:50%;background:#1a1d2a;border:1px solid #2a2d35;display:flex;align-items:center;justify-content:center;cursor:pointer;transition:border-color .15s}
#aw:hover{border-color:#f5c518}
#ai{font-size:1.1rem;pointer-events:none;user-select:none;line-height:1}
#file-input{position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:pointer;border-radius:50%}

/* Input center */
#ic{flex:1;min-width:0;display:flex;flex-direction:column;gap:5px}
#prev{display:none;align-items:center;gap:6px;background:#1a1d2a;border-radius:8px;padding:5px 8px}
#prev img{height:44px;width:auto;border-radius:5px;object-fit:cover}
#prev button{background:none;border:none;color:#777;cursor:pointer;font-size:.85rem;padding:2px 5px}
#prev button:hover{color:#ef5350}
#ti{width:100%;background:#0d0f14;border:1px solid #2a2d35;border-radius:20px;color:#e0e0e0;font-size:.9rem;padding:10px 16px;resize:none;height:42px;max-height:130px;font-family:inherit;outline:none;transition:border-color .2s;line-height:1.4;display:block}
#ti:focus{border-color:#f5c518}
#ti::placeholder{color:#444}

/* Send */
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
    <b>Ask anything. Attach any chart.</b><br>
    Any market · Any instrument · Any timeframe<br><br>
    Type a question <em>or</em> tap 📎 to attach a chart screenshot.<br>
    The AI will analyse it and give you a clear recommendation.
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
    <textarea id="ti" placeholder="Ask about any market, or attach a chart…"></textarea>
  </div>
  <button id="sb">➤</button>
</div>

<script>
var selFile = null;

// ── File attach ──────────────────────────────────────────────────────────────
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

// ── Send ─────────────────────────────────────────────────────────────────────
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

  // Remove hint
  var hint = box.querySelector('.hint');
  if(hint) hint.remove();

  // User bubble
  var u = document.createElement('div');
  u.className = 'msg user';
  if(selFile){
    var im = document.createElement('img');
    im.src = URL.createObjectURL(selFile);
    u.appendChild(im);
  }
  if(txt) u.appendChild(document.createTextNode(txt));
  box.appendChild(u);

  // Typing indicator
  var t = document.createElement('div');
  t.className = 'msg bot typing';
  t.textContent = 'Analysing…';
  box.appendChild(t);
  box.scrollTop = box.scrollHeight;

  // Build form data
  var fd = new FormData();
  if(txt) fd.append('message', txt);
  if(selFile) fd.append('chart', selFile, selFile.name);

  // Clear inputs
  ti.value = '';
  ti.style.height = '42px';
  var tmpFile = selFile;
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

    print("\n Trading AI ready at http://localhost:5000\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
