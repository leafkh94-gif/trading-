"""
Gold Chart Analysis Agent — Flask backend
Uses Claude's vision API to analyze trading chart screenshots.
Run: python app.py  →  open http://localhost:5000
"""

import base64
import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import anthropic
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder=".")
CORS(app)

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are an expert technical analyst specializing in Gold (XAU/USD) trading.
When shown a trading chart, you provide a structured, actionable analysis.

Your response must follow this exact format:

**TREND**
State the current trend direction (Bullish / Bearish / Sideways) and explain briefly based on price action and structure.

**KEY LEVELS**
List the most important support and resistance levels visible on the chart with approximate price values.

**PATTERN**
Identify any chart patterns (e.g. bull flag, double top, wedge, triangle, engulfing candle, etc.). If none are clear, say so.

**MOMENTUM**
Comment on momentum — is it accelerating, slowing, or diverging? Reference visible indicators if shown.

**RECOMMENDATION**
Give one of: BUY / SELL / WAIT — with a clear one-sentence rationale.

**RISK NOTES**
Suggest a logical stop loss zone and note any risks or invalidation points for the recommendation.

Keep the analysis concise and direct. Base everything strictly on what is visible in the chart."""


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    if "chart" not in request.files:
        return jsonify({"error": "No chart image provided"}), 400

    chart_file = request.files["chart"]
    question = request.form.get("question", "Analyze this chart and give me a trading recommendation.")

    # Read and base64-encode the image
    image_bytes = chart_file.read()
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    # Detect media type from file extension
    filename = chart_file.filename.lower()
    if filename.endswith(".png"):
        media_type = "image/png"
    elif filename.endswith(".jpg") or filename.endswith(".jpeg"):
        media_type = "image/jpeg"
    elif filename.endswith(".gif"):
        media_type = "image/gif"
    elif filename.endswith(".webp"):
        media_type = "image/webp"
    else:
        media_type = "image/png"  # Default assumption for chart screenshots

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": question,
                        },
                    ],
                }
            ],
        )
        return jsonify({"analysis": response.content[0].text})

    except anthropic.APIError as e:
        return jsonify({"error": f"API error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


if __name__ == "__main__":
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set. Copy .env.example to .env and add your key.")
    else:
        print("Gold Chart Analysis Agent running at http://localhost:5000")
    app.run(debug=False, host="0.0.0.0", port=5000)
