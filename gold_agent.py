"""
GoldScalperPro AI — Chart Analyzer
Upload a chart screenshot or type a question. That's it.
Run: python gold_agent.py  →  open http://localhost:5000
"""

import base64, os
from flask import Flask, request, jsonify
import anthropic

API_KEY = os.environ.get("ANTHROPIC_API_KEY",
    "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")

SYSTEM = """You are a professional Gold (XAU/USD) trading analyst.

When the user sends a chart image, analyze it using this structure:
**📊 TREND** — is price going up, down, or sideways? Which EMA stack?
**📍 KEY LEVELS** — exact support and resistance price levels visible on the chart
**📈 MOMENTUM** — what do RSI and MACD say?
**🎯 SIGNAL** — BUY / SELL / WAIT — be direct and decisive
**💰 TRADE PLAN** — entry price, stop loss, take profit 1, take profit 2
**⚠️ RISK** — what would invalidate this setup?

When the user asks a question without a chart, answer it directly and concisely.
Always give specific price levels. Never be vague. Be conversational and remember context."""

conversation = []

app = Flask(__name__)

@app.route("/")
def index():
    return HTML

@app.route("/clear", methods=["POST"])
def clear():
    conversation.clear()
    return jsonify({"ok": True})

@app.route("/chat", methods=["POST"])
def chat():
    text  = request.form.get("message", "").strip()
    chart = request.files.get("chart")

    content = []
    if chart:
        b64  = base64.standard_b64encode(chart.read()).decode()
        name = chart.filename.lower()
        mime = "image/png" if name.endswith(".png") else \
               "image/jpeg" if name.endswith((".jpg",".jpeg")) else "image/png"
        content.append({"type":"image","source":{"type":"base64","media_type":mime,"data":b64}})

    content.append({"type":"text","text": text or "Analyze this chart."})
    conversation.append({"role":"user","content":content})

    # Keep last 20 messages; strip old image bytes
    history = conversation[-20:]
    last_img = max((i for i,m in enumerate(history)
                    if isinstance(m["content"],list)
                    and any(c.get("type")=="image" for c in m["content"])), default=None)
    cleaned = []
    for i, m in enumerate(history):
        if isinstance(m["content"], list) and i != last_img:
            cleaned.append({"role":m["role"],
                             "content":[{"type":"text","text":"[earlier chart]"}
                                        if c.get("type")=="image" else c
                                        for c in m["content"]]})
        else:
            cleaned.append(m)

    try:
        resp = anthropic.Anthropic(api_key=API_KEY).messages.create(
            model="claude-sonnet-4-6", max_tokens=2048,
            system=SYSTEM, messages=cleaned)
        reply = resp.content[0].text
        conversation.append({"role":"assistant","content":reply})
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
body{background:#0d0f14;color:#e0e0e0;font-family:'Segoe UI',system-ui,sans-serif;
     height:100vh;display:flex;flex-direction:column;overflow:hidden}
#hdr{background:#111318;border-bottom:1px solid #1f2230;padding:11px 18px;
     display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
#hdr h1{color:#f5c518;font-size:1rem;font-weight:700}
#clr{background:transparent;border:1px solid #2a2d35;color:#888;border-radius:6px;
     padding:4px 11px;cursor:pointer;font-size:.75rem}
#clr:hover{border-color:#f5c518;color:#f5c518}
#msgs{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px}
#msgs::-webkit-scrollbar{width:4px}
#msgs::-webkit-scrollbar-thumb{background:#2a2d35;border-radius:4px}
.msg{max-width:84%;padding:10px 14px;border-radius:10px;font-size:.87rem;
     line-height:1.7;word-break:break-word}
.u{background:#1e2235;align-self:flex-end;border-bottom-right-radius:3px}
.b{background:#161920;border:1px solid #1f2230;align-self:flex-start;
   border-bottom-left-radius:3px}
.b strong{color:#f5c518}
.err{border-color:#ef5350!important;background:#2b1010!important;color:#ef5350!important}
.typ{color:#555;font-style:italic}
.ci{max-width:220px;border-radius:6px;margin-top:6px;display:block}
.wel{text-align:center;color:#555;font-size:.85rem;padding:48px 20px;line-height:2}
.wel b{color:#f5c518}
#ibar{border-top:1px solid #1f2230;padding:10px 12px;display:flex;
      align-items:flex-end;gap:8px;background:#111318;flex-shrink:0}
#att{background:#1e2235;border:1px solid #2a2d35;color:#888;border-radius:8px;
     padding:8px 10px;cursor:pointer;flex-shrink:0;font-size:1rem;transition:.15s}
#att:hover,#att.on{border-color:#f5c518;color:#f5c518}
#fi{display:none}
#ti{flex:1;background:#0d0f14;border:1px solid #2a2d35;border-radius:8px;
    color:#e0e0e0;font-size:.87rem;padding:9px 12px;resize:none;height:40px;
    max-height:120px;font-family:inherit;outline:none;transition:.15s;line-height:1.4}
#ti:focus{border-color:#f5c518}
#sb{background:#f5c518;color:#0d0f14;border:none;border-radius:8px;padding:9px 15px;
    cursor:pointer;font-weight:700;font-size:.9rem;flex-shrink:0}
#sb:disabled{opacity:.35;cursor:not-allowed}
</style>
</head>
<body>
<div id="hdr">
  <h1>🏆 GoldScalperPro AI</h1>
  <button id="clr" onclick="clearChat()">Clear chat</button>
</div>
<div id="msgs">
  <div class="wel">
    <b>Gold Trading Analyst</b><br>
    Attach a chart screenshot → get a full analysis<br>
    Or just type your question about Gold
  </div>
</div>
<div id="ibar">
  <button id="att" onclick="document.getElementById('fi').click()" title="Attach chart">📎</button>
  <input type="file" id="fi" accept="image/*" onchange="onFile(this)"/>
  <textarea id="ti" placeholder="Ask about Gold or attach a chart screenshot…"
            onkeydown="onKey(event)" oninput="ar(this)"></textarea>
  <button id="sb" onclick="send()">▶</button>
</div>
<script>
let file = null;
function onFile(i){ file=i.files[0]||null; document.getElementById('att').classList.toggle('on',!!file); }
function ar(el){ el.style.height='40px'; el.style.height=Math.min(el.scrollHeight,120)+'px'; }
function onKey(e){ if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();} }

function fmt(t){
  return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
          .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/\n/g,'<br>');
}

async function send(){
  const ti=document.getElementById('ti'), txt=ti.value.trim();
  if(!txt&&!file) return;
  const sb=document.getElementById('sb'); sb.disabled=true;
  const msgs=document.getElementById('msgs');
  msgs.querySelector('.wel')?.remove();

  const ud=document.createElement('div'); ud.className='msg u';
  if(file){ const img=document.createElement('img'); img.className='ci';
            img.src=URL.createObjectURL(file); ud.appendChild(img); }
  if(txt) ud.appendChild(document.createTextNode(txt));
  msgs.appendChild(ud);

  const typ=document.createElement('div'); typ.className='msg b typ';
  typ.textContent='Analyzing…'; msgs.appendChild(typ);
  msgs.scrollTop=msgs.scrollHeight;
  ti.value=''; ti.style.height='40px';

  const fd=new FormData();
  if(txt) fd.append('message',txt);
  if(file) fd.append('chart',file,file.name);
  file=null; document.getElementById('fi').value='';
  document.getElementById('att').classList.remove('on');

  try{
    const d=await(await fetch('/chat',{method:'POST',body:fd})).json();
    typ.remove();
    const bd=document.createElement('div');
    bd.className='msg b'+(d.error?' err':'');
    bd.innerHTML=fmt(d.reply||('⚠️ '+d.error));
    msgs.appendChild(bd);
  }catch(e){
    typ.remove();
    const bd=document.createElement('div'); bd.className='msg b err';
    bd.textContent='⚠️ Cannot reach server. Is the black window still open?';
    msgs.appendChild(bd);
  }
  msgs.scrollTop=msgs.scrollHeight; sb.disabled=false; ti.focus();
}

async function clearChat(){
  await fetch('/clear',{method:'POST'});
  document.getElementById('msgs').innerHTML=
    '<div class="wel"><b>Gold Trading Analyst</b><br>Chat cleared. Ready.</div>';
}
</script>
</body>
</html>"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n GoldScalperPro AI — Chart Analyzer")
    print(f" Open: http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
