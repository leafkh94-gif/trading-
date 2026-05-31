"""
Gold Chart Analyzer
Upload a chart screenshot → get AI trading analysis
"""

import base64, os
from flask import Flask, request, jsonify
import anthropic

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

SYSTEM = """You are a professional Gold (XAU/USD) trading analyst.

When given a chart screenshot, always structure your response exactly like this:

TREND
State the current trend direction and what the EMAs show.

KEY LEVELS
List the main support and resistance price levels visible on the chart.

SIGNAL
State clearly: BUY / SELL / WAIT — and the reason in one sentence.

TRADE PLAN
Entry: [price]
Stop Loss: [price]
Take Profit: [price]

RISK NOTE
One sentence on what would invalidate this setup.

Be specific with prices. Be direct. No filler text."""

app = Flask(__name__)

@app.route("/")
def index():
    return HTML

@app.route("/analyze", methods=["POST"])
def analyze():
    chart = request.files.get("chart")
    if not chart:
        return jsonify({"error": "No chart uploaded"}), 400

    raw  = chart.read()
    b64  = base64.standard_b64encode(raw).decode()
    name = chart.filename.lower()
    mime = ("image/png"  if name.endswith(".png")  else
            "image/jpeg" if name.endswith((".jpg", ".jpeg")) else
            "image/webp" if name.endswith(".webp") else "image/png")

    try:
        client = anthropic.Anthropic(api_key=API_KEY)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                    {"type": "text", "text": "Analyze this Gold chart."}
                ]
            }]
        )
        return jsonify({"analysis": resp.content[0].text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Gold Chart Analyzer</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d0f14;color:#e0e0e0;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:30px 16px}
h1{color:#f5c518;font-size:1.3rem;font-weight:700;margin-bottom:6px;letter-spacing:.5px}
p.sub{color:#555;font-size:.85rem;margin-bottom:28px}
#drop-zone{width:100%;max-width:560px;border:2px dashed #2a2d35;border-radius:14px;padding:40px 20px;text-align:center;cursor:pointer;transition:border-color .2s,background .2s;margin-bottom:18px}
#drop-zone:hover,#drop-zone.over{border-color:#f5c518;background:#111318}
#drop-zone p{color:#555;font-size:.9rem;pointer-events:none}
#drop-zone.has-file p{color:#f5c518}
#preview{max-width:100%;max-height:260px;border-radius:10px;margin:12px auto 0;display:none;border:1px solid #1f2230}
#file-input{display:none}
#analyze-btn{width:100%;max-width:560px;background:#f5c518;color:#0d0f14;border:none;border-radius:10px;padding:13px;font-size:1rem;font-weight:700;cursor:pointer;transition:opacity .2s;margin-bottom:24px}
#analyze-btn:disabled{opacity:.4;cursor:not-allowed}
#result{width:100%;max-width:560px;background:#111318;border:1px solid #1f2230;border-radius:12px;padding:20px;font-size:.88rem;line-height:1.85;white-space:pre-wrap;display:none;color:#ddd}
#result b{color:#f5c518}
#spinner{display:none;width:100%;max-width:560px;text-align:center;color:#555;font-size:.85rem;padding:16px}
</style>
</head>
<body>

<h1>&#127941; Gold Chart Analyzer</h1>
<p class="sub">Upload a chart screenshot to get a trading analysis</p>

<div id="drop-zone" onclick="document.getElementById('file-input').click()"
     ondragover="ev(event,'over')" ondragleave="ev(event,'')" ondrop="drop(event)">
  <p id="drop-text">&#128206; Click or drag &amp; drop your chart here</p>
  <img id="preview"/>
</div>
<input type="file" id="file-input" accept="image/*" onchange="picked(this)"/>

<button id="analyze-btn" onclick="analyze()" disabled>Analyze Chart</button>

<div id="spinner">Analyzing your chart&#8230;</div>
<div id="result"></div>

<script>
let file = null;

function ev(e, cls){
  e.preventDefault();
  document.getElementById('drop-zone').className = cls ? 'over' : (file ? 'has-file' : '');
}

function drop(e){
  e.preventDefault();
  const f = e.dataTransfer.files[0];
  if(f && f.type.startsWith('image/')) setFile(f);
}

function picked(input){
  if(input.files[0]) setFile(input.files[0]);
}

function setFile(f){
  file = f;
  const prev = document.getElementById('preview');
  prev.src = URL.createObjectURL(f);
  prev.style.display = 'block';
  document.getElementById('drop-text').textContent = f.name;
  document.getElementById('drop-zone').className = 'has-file';
  document.getElementById('analyze-btn').disabled = false;
  document.getElementById('result').style.display = 'none';
}

async function analyze(){
  if(!file) return;
  document.getElementById('analyze-btn').disabled = true;
  document.getElementById('spinner').style.display = 'block';
  document.getElementById('result').style.display = 'none';

  const fd = new FormData();
  fd.append('chart', file, file.name);

  try{
    const res  = await fetch('/analyze', {method:'POST', body:fd});
    const data = await res.json();
    const out  = document.getElementById('result');
    const text = data.analysis || ('Error: ' + data.error);
    out.innerHTML = text
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/^(TREND|KEY LEVELS|SIGNAL|TRADE PLAN|RISK NOTE)/gm,'<b>$1</b>');
    out.style.display = 'block';
  } catch(e){
    const out = document.getElementById('result');
    out.textContent = 'Connection error. Is the server running?';
    out.style.display = 'block';
  }

  document.getElementById('spinner').style.display = 'none';
  document.getElementById('analyze-btn').disabled = false;
}
</script>
</body>
</html>"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n Gold Chart Analyzer")
    print(f" Open: http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
