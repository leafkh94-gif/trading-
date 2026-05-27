"""
Gold Chart Analysis Agent
=========================
Single-file AI trading assistant powered by Claude vision.

Setup (one time only):
    pip install anthropic flask

Run:
    Windows:  set ANTHROPIC_API_KEY=your_key_here && python gold_agent.py
    Mac/Linux: ANTHROPIC_API_KEY=your_key_here python gold_agent.py

Then open: http://localhost:5000
"""

import base64
import os
import anthropic
from flask import Flask, request, jsonify

API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not API_KEY:
    raise SystemExit("ERROR: ANTHROPIC_API_KEY environment variable is not set.")

SYSTEM_PROMPT = """You are GoldScalperPro AI — an elite Gold (XAU/USD) technical analyst that thinks exactly like a professional scalping bot.

You apply the EXACT same strategy framework as the GoldScalperPro MT4 expert advisor:

═══════════════════════════════════════════════
ANALYSIS FRAMEWORK (apply every step):
═══════════════════════════════════════════════

1. TREND HIERARCHY (3 EMAs)
   - Look for EMA 8 (fast), EMA 21 (mid), EMA 50 (slow) if visible
   - Bullish stack: EMA8 > EMA21 > EMA50
   - Bearish stack: EMA8 < EMA21 < EMA50
   - Otherwise: ranging / no trend
   - If EMAs aren't drawn, infer trend from price structure (higher highs/lows vs lower highs/lows)

2. RSI MOMENTUM (RSI 14)
   - Bullish confirmation: RSI > 55
   - Bearish confirmation: RSI < 45
   - Neutral zone (45-55): no momentum edge
   - Overbought (>70) or oversold (<30): reversal risk

3. MACD MOMENTUM
   - Histogram rising above zero = bullish momentum
   - Histogram falling below zero = bearish momentum
   - Divergence with price = early reversal warning

4. SUPPORT & RESISTANCE (last 20 bars)
   - Identify the highest high and lowest low of the recent swing
   - A close beyond these levels (+ buffer) signals breakout

5. VOLATILITY (ATR concept)
   - Estimate average candle range
   - Stop loss zone = ~1.5x typical candle range
   - Take profit zone (scalp) = ~3x typical range
   - Take profit zone (breakout) = ~5x typical range

═══════════════════════════════════════════════
SIGNAL TYPES (match the bot exactly):
═══════════════════════════════════════════════

SCALP-BUY  → All four must align: EMA8 crossing above EMA21, price above EMA50, RSI > 55, MACD bullish
SCALP-SELL → Mirror of above
BREAK-BUY  → Price closes above 20-bar swing high WITH RSI > 55
BREAK-SELL → Price closes below 20-bar swing low WITH RSI < 45
WAIT       → Any conflicting signals OR no clean setup

═══════════════════════════════════════════════
RESPONSE FORMAT (use this exact structure):
═══════════════════════════════════════════════

**📊 MARKET STRUCTURE**
Trend direction + EMA stack assessment (bullish/bearish/sideways) + brief reasoning.

**📍 KEY LEVELS**
- Resistance: [price]
- Support: [price]
- Recent swing high/low: [price]

**📈 INDICATOR READ**
- EMA alignment: [bullish stack / bearish stack / mixed]
- RSI: [estimated value, zone]
- MACD: [bullish / bearish / neutral momentum]
- Volatility: [low / medium / high]

**🎯 SIGNAL**
[SCALP-BUY / SCALP-SELL / BREAK-BUY / BREAK-SELL / WAIT]
One-sentence reason.

**💰 TRADE PLAN** (only if signal is not WAIT)
- Entry: [price zone]
- Stop Loss: [price] — risk in pips/points
- Take Profit 1: [price] — 1:1 R/R
- Take Profit 2: [price] — 1:2 R/R
- Position size: Risk 1% of equity, calculate lots from SL distance

**⚠️ RISK NOTES**
- Invalidation: [price level that voids the setup]
- Watch out for: [news, session timing, low liquidity, etc.]
- Confidence: [Low / Medium / High] — based on how many indicators align

Be direct, decisive, and base everything on what is actually visible. Do not hedge — give a clear signal.
This is technical analysis for educational purposes; the user makes the final decision."""

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Gold Chart Analysis Agent</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{background:#0d0f14;color:#e0e0e0;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:32px 16px}
    header{text-align:center;margin-bottom:28px}
    header h1{font-size:1.5rem;color:#f5c518;letter-spacing:.5px}
    header p{color:#888;font-size:.88rem;margin-top:6px}
    .card{background:#161920;border:1px solid #2a2d35;border-radius:12px;padding:22px;width:100%;max-width:760px;margin-bottom:18px}
    .card h2{font-size:.8rem;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:12px}
    #drop-zone{border:2px dashed #2e3340;border-radius:10px;padding:36px 20px;text-align:center;cursor:pointer;transition:border-color .2s,background .2s;position:relative}
    #drop-zone:hover,#drop-zone.drag-over{border-color:#f5c518;background:#1a1d24}
    #drop-zone input[type=file]{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%}
    #drop-zone .icon{font-size:2.2rem;margin-bottom:8px}
    #drop-zone .label{color:#e0e0e0;font-size:.95rem;font-weight:500;margin-bottom:4px}
    #drop-zone p{color:#888;font-size:.85rem}
    #preview-wrap{display:none;margin-top:14px;position:relative}
    #preview-wrap img{width:100%;max-height:300px;object-fit:contain;border-radius:8px;border:1px solid #2a2d35;background:#0d0f14}
    #remove-btn{position:absolute;top:8px;right:8px;background:rgba(0,0,0,.75);color:#f5c518;border:none;border-radius:6px;padding:4px 10px;cursor:pointer;font-size:.78rem}
    #question{width:100%;background:#0d0f14;border:1px solid #2a2d35;border-radius:8px;color:#e0e0e0;font-size:.92rem;padding:11px 13px;resize:vertical;min-height:68px;font-family:inherit;outline:none;transition:border-color .2s}
    #question:focus{border-color:#f5c518}
    #analyze-btn{width:100%;max-width:760px;padding:13px;background:#f5c518;color:#0d0f14;font-weight:700;font-size:.95rem;border:none;border-radius:10px;cursor:pointer;margin-bottom:18px;transition:opacity .2s}
    #analyze-btn:disabled{opacity:.4;cursor:not-allowed}
    #result-card{display:none}
    .result-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
    #result-body{background:#0d0f14;border:1px solid #2a2d35;border-radius:8px;padding:16px;font-size:.9rem;line-height:1.75;white-space:pre-wrap;color:#d4d4d4;max-height:500px;overflow-y:auto}
    #result-body strong{color:#f5c518}
    #reset-btn{background:transparent;border:1px solid #2a2d35;color:#888;border-radius:6px;padding:4px 11px;cursor:pointer;font-size:.78rem;transition:border-color .2s,color .2s}
    #reset-btn:hover{border-color:#f5c518;color:#f5c518}
    .spinner{display:inline-block;width:16px;height:16px;border:2px solid #0d0f14;border-top-color:transparent;border-radius:50%;animation:spin .7s linear infinite;vertical-align:middle;margin-right:7px}
    @keyframes spin{to{transform:rotate(360deg)}}
    #error-msg{display:none;color:#e05252;font-size:.85rem;margin-top:8px;text-align:center}
    footer{color:#444;font-size:.75rem;margin-top:14px;text-align:center}
  </style>
</head>
<body>
  <header>
    <h1>Gold Chart Analysis Agent</h1>
    <p>Upload a chart screenshot — get an instant AI analysis and trade recommendation</p>
  </header>

  <div class="card">
    <h2>Chart Screenshot</h2>
    <div id="drop-zone">
      <input type="file" id="file-input" accept="image/*"/>
      <div class="icon">📈</div>
      <div class="label">Drop your chart here</div>
      <p>or click to browse — PNG, JPG, WebP supported</p>
    </div>
    <div id="preview-wrap">
      <img id="preview-img" src="" alt="preview"/>
      <button id="remove-btn">✕ Remove</button>
    </div>
  </div>

  <div class="card">
    <h2>Your Question</h2>
    <textarea id="question">Apply the GoldScalperPro framework to this chart. Tell me the signal and exact entry/SL/TP levels.</textarea>
  </div>

  <button id="analyze-btn" disabled>Analyze Chart</button>
  <p id="error-msg"></p>

  <div class="card" id="result-card">
    <div class="result-header">
      <h2>Analysis</h2>
      <button id="reset-btn">New Analysis</button>
    </div>
    <div id="result-body"></div>
  </div>

  <footer>Powered by Claude Vision &nbsp;·&nbsp; For educational purposes only &nbsp;·&nbsp; Not financial advice</footer>

  <script>
    const dropZone=document.getElementById('drop-zone'),fileInput=document.getElementById('file-input'),
    previewWrap=document.getElementById('preview-wrap'),previewImg=document.getElementById('preview-img'),
    removeBtn=document.getElementById('remove-btn'),questionEl=document.getElementById('question'),
    analyzeBtn=document.getElementById('analyze-btn'),resultCard=document.getElementById('result-card'),
    resultBody=document.getElementById('result-body'),errorMsg=document.getElementById('error-msg'),
    resetBtn=document.getElementById('reset-btn');
    let selectedFile=null;

    dropZone.addEventListener('dragover',e=>{e.preventDefault();dropZone.classList.add('drag-over')});
    dropZone.addEventListener('dragleave',()=>dropZone.classList.remove('drag-over'));
    dropZone.addEventListener('drop',e=>{e.preventDefault();dropZone.classList.remove('drag-over');if(e.dataTransfer.files.length)handleFile(e.dataTransfer.files[0])});
    fileInput.addEventListener('change',()=>{if(fileInput.files.length)handleFile(fileInput.files[0])});

    function handleFile(file){
      if(!file.type.startsWith('image/')){showError('Please upload an image file.');return}
      selectedFile=file;
      const r=new FileReader();
      r.onload=e=>{previewImg.src=e.target.result;previewWrap.style.display='block';fileInput.style.display='none';analyzeBtn.disabled=false;hideError()};
      r.readAsDataURL(file);
    }

    removeBtn.addEventListener('click',reset);
    function reset(){selectedFile=null;previewWrap.style.display='none';previewImg.src='';fileInput.value='';fileInput.style.display='';analyzeBtn.disabled=true}

    analyzeBtn.addEventListener('click',async()=>{
      if(!selectedFile)return;
      analyzeBtn.disabled=true;analyzeBtn.innerHTML='<span class="spinner"></span>Analyzing…';
      resultCard.style.display='none';hideError();
      const fd=new FormData();
      fd.append('chart',selectedFile,selectedFile.name);
      fd.append('question',questionEl.value.trim()||'Apply the GoldScalperPro framework to this chart. Tell me the signal and exact entry/SL/TP levels.');
      try{
        const res=await fetch('/analyze',{method:'POST',body:fd});
        const data=await res.json();
        if(data.error){showError(data.error)}
        else{resultBody.innerHTML=data.analysis.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');resultCard.style.display='block';resultCard.scrollIntoView({behavior:'smooth',block:'start'})}
      }catch(e){showError('Could not connect. Make sure gold_agent.py is running.')}
      finally{analyzeBtn.disabled=false;analyzeBtn.textContent='Analyze Chart'}
    });

    resetBtn.addEventListener('click',()=>{resultCard.style.display='none';reset();questionEl.value='Apply the GoldScalperPro framework to this chart. Tell me the signal and exact entry/SL/TP levels.'});
    function showError(m){errorMsg.textContent='⚠ '+m;errorMsg.style.display='block'}
    function hideError(){errorMsg.style.display='none'}
  </script>
</body>
</html>"""


app = Flask(__name__)

@app.route("/")
def index():
    return HTML

@app.route("/analyze", methods=["POST"])
def analyze():
    if "chart" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    f = request.files["chart"]
    question = request.form.get("question", "Apply the GoldScalperPro framework to this chart. Tell me the signal and exact entry/SL/TP levels.")

    img_b64 = base64.standard_b64encode(f.read()).decode()
    fname = f.filename.lower()
    media = "image/png" if fname.endswith(".png") else \
            "image/jpeg" if fname.endswith((".jpg", ".jpeg")) else \
            "image/webp" if fname.endswith(".webp") else "image/png"

    try:
        client = anthropic.Anthropic(api_key=API_KEY)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media, "data": img_b64}},
                {"type": "text", "text": question}
            ]}]
        )
        return jsonify({"analysis": resp.content[0].text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("\n Gold Chart Analysis Agent")
    print(" Open your browser at: http://localhost:5000\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
