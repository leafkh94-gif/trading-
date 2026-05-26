# Trading Tools — Gold (XAU/USD)

Two tools for Gold trading: an automated MT4 Expert Advisor and an AI-powered chart analysis agent.

---

## 1. GoldEA_TrailingStop.mq4 — MT4 Expert Advisor

Automated scalping EA for Gold (XAUUSD) on the 1-minute chart.

**Strategy:** EMA(8/21) crossover entry, filtered by RSI(14). Step-based trailing stop locks in profits as price moves in your favour.

### Installation
1. Copy `GoldEA_TrailingStop.mq4` to your MT4 `MQL4/Experts/` folder
2. Open MetaEditor (F4), compile the file — must show 0 errors
3. Attach to a XAUUSD M1 chart
4. Enable AutoTrading in the MT4 toolbar

### Key Parameters
| Parameter | Default | Description |
|---|---|---|
| `LotSize` | 0.01 | Trade volume |
| `StopLoss_Points` | 200 | Stop loss (20 pips on 5-digit broker) |
| `TakeProfit_Points` | 400 | Take profit (40 pips, 2:1 R/R) |
| `MaxSpreadPoints` | 50 | Skip entry if spread is wider than this |
| `TrailActivation_Pts` | 150 | Profit needed before trailing stop activates |
| `TrailDistance_Pts` | 100 | Points to keep SL behind current price |
| `TrailStep_Pts` | 25 | Minimum SL movement per update |
| `MagicNumber` | 20241 | Change if running multiple EA instances |

### Backtesting
- MT4 → View → Strategy Tester
- Model: **Every Tick** (required for accurate trailing stop simulation)
- Symbol: XAUUSD, Period: M1
- Check the Journal tab for initialization messages and any errors

---

## 2. chart_analyzer/ — AI Chart Analysis Agent

A local web app: upload any chart screenshot, ask a question, get an instant technical analysis with a Buy / Sell / Wait recommendation.

### Setup
```bash
cd chart_analyzer
cp .env.example .env
# Edit .env and add your Anthropic API key
pip install -r requirements.txt
python app.py
```

Then open **http://localhost:5000** in your browser.

### Usage
1. Drag and drop (or click to upload) a chart screenshot
2. Type your question — or use the default prompt
3. Click **Analyze Chart**
4. Review the structured analysis: trend, key levels, pattern, momentum, recommendation, and risk notes

### Requirements
- Python 3.9+
- Anthropic API key ([console.anthropic.com](https://console.anthropic.com/))
