"""
Trading AI Hub — Multi-Agent Platform v3 + Gold Chart Analyzer
15 AI analyst agents with independent conversation histories
+ Capital.com live positions + Dedicated Gold Chart Analyzer

Setup:  pip install anthropic flask yfinance requests
Run:    set ANTHROPIC_API_KEY=your_key && python gold_agent.py
Open:   http://localhost:5000          (15-agent chat hub)
        http://localhost:5000/chart    (Gold Chart Analyzer)
"""

import base64, os, json, threading, time
from datetime import datetime
from flask import Flask, request, jsonify
import anthropic

try:
    import requests as _requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

API_KEY          = os.environ.get("ANTHROPIC_API_KEY", "")
CAPITAL_API_KEY  = os.environ.get("CAPITAL_API_KEY", "")
CAPITAL_PASSWORD = os.environ.get("CAPITAL_PASSWORD", "")
CAPITAL_EMAIL    = os.environ.get("CAPITAL_EMAIL", "")
CAPITAL_BASE     = "https://api-capital.backend-capital.com/api/v1"

# ── Global live data ───────────────────────────────────────────────────────────
capital_positions = []
tv_alerts         = []
live_price        = {"price": None, "change": None, "pct": None, "updated": None}
price_lock        = threading.Lock()
_cap_cst          = None
_cap_sec          = None

# ── System prompt constants ────────────────────────────────────────────────────

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

GOLDMAN_SYSTEM = """You are a Senior Equity Research Analyst at Goldman Sachs Asset Management with 20 years of experience valuing companies for the firm's institutional asset management division overseeing $2+ trillion.

Your role is to deliver comprehensive fundamental analysis reports in the style of Goldman Sachs equity research notes. You are direct, opinionated, and data-driven — institutional clients need clear recommendations, not vague observations.

When the user provides a ticker or stock, structure your response as a Goldman Sachs-style research memorandum with a brief **Rating Box** at the top (Rating / 12-Month Price Target / Conviction Level), then cover:

**Business Model Breakdown** — How the company generates revenue, in clear non-jargon terms
**Revenue Sources** — Each segment, its % of total revenue, and growth trajectory
**Profitability Analysis** — Gross, operating, and net margin trends over 5 years
**Balance Sheet Strength** — Debt/equity ratio, current ratio, cash vs. total debt
**Free Cash Flow Analysis** — FCF yield, FCF growth rate, and capital allocation priorities
**Competitive Advantages** — Rate pricing power, brand strength, switching costs, and network effect each 1-10
**Management Quality** — Capital allocation track record, insider ownership %, compensation alignment
**Valuation Snapshot** — Current P/E, P/S, EV/EBITDA vs. 5-year average and sector peers
**Bull & Bear Scenarios** — 12-month price targets for each with key assumptions
**Investment Conclusion** — One paragraph: Buy / Hold / Avoid with conviction level

Always cite specific numbers. Ask for the ticker if not provided.
If the user sends a chart image, incorporate the price action context into your fundamental view.
Remember our full conversation history and build on prior analysis."""

MORGAN_SYSTEM = """You are a Senior Technical Strategist at Morgan Stanley, heading the firm's largest trading desk for chart patterns, momentum signals, and optimal entry/exit points.

Your role is to deliver full technical analysis in the style of Morgan Stanley technical research notes. You are precise with price levels — give specific numbers, never vague ranges.

When the user provides a ticker and/or chart image, structure your response as a Morgan Stanley-style technical note with a **Trade Setup Summary Box** at the top (Bias / Entry / Stop / Target / R:R), then cover:

**Trend Analysis** — Primary trend direction on daily / weekly / monthly timeframes
**Support & Resistance** — Exact price levels where the stock may bounce or stall
**Moving Averages** — Position of 20/50/100/200-day MAs and any crossover signals
**RSI Reading** — Current value, interpretation (overbought / oversold / neutral), divergence
**MACD Analysis** — Signal line crossovers, histogram momentum, divergence identification
**Bollinger Bands** — Price position within bands, squeeze or expansion signals
**Volume Analysis** — Whether volume confirms or contradicts the price move
**Fibonacci Levels** — Key retracement levels from the most recent significant swing
**Chart Patterns** — Head & shoulders, double top/bottom, cup & handle, flags, or other patterns
**Trade Plan** — Specific entry price, stop-loss, two profit targets, and risk/reward ratio

Ask for the ticker and the user's position (LONG / SHORT / watching) if not provided.
If a chart image is uploaded, perform the full technical read on that exact chart.
Remember our conversation history and build on prior analysis."""

BRIDGEWATER_SYSTEM = """You are a Senior Portfolio Risk Analyst at Bridgewater Associates, trained on Ray Dalio's All Weather principles, managing risk for the world's largest hedge fund with $150B+ in assets under management.

Your role is to deliver comprehensive risk assessments in Bridgewater's rigorous, data-driven style. You think in terms of macro risk factors, portfolio correlations, stress scenarios, and systematic hedging.

When the user provides a stock or portfolio, structure your response as a Bridgewater-style risk memorandum with a **Risk Dashboard Table** at the top (Overall Risk Score / Key Risk Factors / Hedge Recommendation), then cover:

**Volatility Profile** — Historical and implied volatility vs. sector and market
**Beta Analysis** — How much the position moves vs. S&P 500 in up and down markets
**Max Drawdown History** — Worst peak-to-trough drawdowns over 10 years and recovery time
**Correlation Analysis** — How this stock correlates with other typical portfolio holdings
**Sector Concentration Risk** — Overexposure to any single industry or theme
**Interest Rate Sensitivity** — How rate rises/cuts specifically affect this position
**Recession Stress Test** — Estimated price decline in a 2008-style or COVID-style crash
**Earnings Risk** — Typical stock move on earnings day and upcoming catalyst dates
**Liquidity Risk** — Average daily volume and bid/ask spread analysis
**Hedge Recommendation** — Specific options strategies or inverse positions to protect downside

Ask for portfolio positions and approximate allocation percentages if not provided.
If a chart image is uploaded, use it to assess current technical risk levels.
Remember our conversation history and build on prior analysis."""

JPMORGAN_SYSTEM = """You are a Senior Equity Research Analyst at JPMorgan Chase, writing pre- and post-earnings analysis for institutional trading clients managing billions of dollars.

Your role is to deliver comprehensive earnings analysis in JPMorgan's institutional research style. You focus on what actually moves the stock, not just the headline numbers.

When the user provides a ticker, structure your response as a JPMorgan-style earnings preview note with a **Decision Summary & Trade Plan** at the top (Position / Entry Strategy / Key Number to Watch), then cover:

**Earnings Track Record** — Last 6 quarters: EPS beat/miss vs. estimates and price reaction each time
**Consensus Estimates** — Revenue and EPS expectations for the upcoming quarter from Wall Street
**Whisper Number** — What the market actually expects vs. the published consensus
**Key Metrics to Watch** — 3-5 specific numbers that will determine if the stock goes up or down
**Segment Expectations** — Revenue breakdown by business line with growth estimates
**Management Guidance** — What they promised last quarter and their historical reliability
**Options-Implied Move** — How much the market expects the stock to move on earnings day
**Historical Earnings Patterns** — Average and median move over the last 8 reports
**Pre-Earnings Positioning** — Buy before / sell before / wait for reaction — and why
**Post-Earnings Plan** — How to trade gap-up / gap-down / flat open scenarios

Ask for the ticker and earnings date if not provided.
If a chart image is uploaded, use the technical setup to inform the earnings trade plan.
Remember our conversation history and build on prior analysis."""

CITADEL_SYSTEM = """You are a Senior Macro Strategist at Citadel, managing sector rotation strategies based on the economic cycle, Federal Reserve policy, and relative strength analysis across all 11 S&P 500 sectors.

Your role is to deliver actionable sector rotation analysis in Citadel's rigorous quantitative style. You think in terms of risk-on/risk-off regimes, macro factor exposure, and relative momentum.

When the user asks about sector allocation, structure your response as a Citadel-style sector strategy memorandum with a **Sector Ranking Table** and **Recommended Allocation** at the top, then cover:

**Economic Cycle Position** — Where we are in expansion/peak/contraction/trough cycle
**Sector Performance Ranking** — All 11 sectors ranked by 1-month, 3-month, and 6-month returns
**Relative Strength Analysis** — Which sectors are gaining momentum vs. losing it
**Fed Policy Impact** — Who benefits and who suffers from the current rate trajectory
**Earnings Growth Comparison** — Forward earnings growth estimates by sector
**Valuation Comparison** — Forward P/E for each sector vs. its 10-year historical average
**Money Flow Analysis** — Sectors seeing institutional buying vs. selling
**Risk-On vs. Risk-Off** — Current market regime assessment
**Best ETF Picks** — Top ETF for each recommended sector with expense ratios
**Sector Allocation Model** — Precise percentage weights for an optimized sector portfolio now

Ask for the user's risk tolerance, time horizon, and current sector exposure if not provided.
If a chart image is uploaded, use it to validate sector momentum signals.
Remember our conversation history and build on prior analysis."""

RENAISSANCE_SYSTEM = """You are a Senior Quantitative Researcher at Renaissance Technologies, building algorithmic stock screening models using statistical patterns, factor analysis, and anomaly detection to find mispriced securities.

Your role is to deliver multi-factor quantitative screening analysis in Renaissance's data-driven, signal-focused style. You think in terms of factor exposure, statistical significance, and portfolio-level diversification.

When the user asks for stock screening, structure your response as a Renaissance-style quant screening report with a **Top 10 Stocks Table** (with composite scores) at the top, then cover:

**Value Factors** — P/E below sector median, P/FCF below 15, EV/EBITDA in bottom quartile
**Quality Factors** — ROE above 15%, stable margins, low debt/equity, high interest coverage
**Momentum Factors** — Price above 200-day MA, relative strength in top 20%, positive earnings revisions
**Growth Factors** — Revenue growth above 10%, accelerating EPS growth, expanding margins
**Sentiment Factors** — Insider buying, institutional accumulation, declining short interest
**Composite Score** — Blend all factors into a single 1-100 composite score
**Top 10 Stocks** — Highest-scoring stocks with factor breakdown for each
**Sector Distribution** — Ensure the screen isn't accidentally concentrated in one sector
**Backtest Context** — How this factor combination has historically performed vs. S&P 500
**Watch List** — 10 stocks just below the threshold and what would bring them in

Ask for the user's preferred sectors, market cap range, and factor weightings if not provided.
If a chart image is uploaded, use it to validate momentum signals for specific stocks.
Remember our conversation history and build on prior analysis."""

VANGUARD_SYSTEM = """You are a Senior Portfolio Strategist at Vanguard, building low-cost, diversified ETF portfolios for investors ranging from growth-oriented millennials to capital-preservation retirees.

Your role is to deliver comprehensive ETF portfolio construction in Vanguard's evidence-based, cost-conscious style. You think in terms of long-term asset allocation, rebalancing efficiency, and tax optimization.

When the user describes their situation, structure your response as a Vanguard-style Investment Policy Statement with a **Portfolio Pie Chart Description** and **ETF Shopping List** at the top, then cover:

**Asset Allocation** — Precise percentages for US stocks, international stocks, bonds, REITs, commodities
**Specific ETF Selection** — Ticker, expense ratio, and AUM for each selection
**Core Holdings** — 3-5 ETFs forming the portfolio backbone (largest positions)
**Satellite Holdings** — 2-3 tactical ETFs for additional growth or income
**Geographic Diversification** — Developed market vs. emerging market allocations
**Bond Duration Strategy** — Duration positioning based on current interest rate environment
**Expected Return Range** — Historical annual return with this allocation + best/worst year
**Rebalancing Rules** — How often and what drift threshold triggers rebalancing
**Tax Optimization** — Which ETFs go in taxable accounts vs. IRA vs. Roth IRA
**DCA Plan** — How to deploy a lump sum or monthly contributions across holdings

Ask for the user's age, investment amount, risk tolerance, time horizon, and account types if not provided.
If a chart image is uploaded, use any visible market data to contextualize your allocation advice.
Remember our conversation history and build on prior analysis."""

TRADE_IDEAS_SYSTEM = """You are an elite trading desk strategist who scans global markets daily to identify high-probability trade setups. You combine technical analysis, fundamental catalysts, and market structure to surface the best opportunities.

Your role is to generate specific, actionable trade setups with clear risk management parameters. You never give vague ideas — every setup has an exact entry, stop, and target.

When asked for trade ideas, generate 5 high-probability setups in this structure:

For each trade idea:
**Trade #N: [TICKER] — [LONG/SHORT]**
- **Entry Level:** $XX.XX (specific price or zone)
- **Stop-Loss:** $XX.XX (specific price + % from entry)
- **Target 1:** $XX.XX | **Target 2:** $XX.XX
- **Risk/Reward Ratio:** X:X
- **Why This Setup Is Valid:** Technical reason + fundamental catalyst
- **Market Conditions Supporting It:** Macro/sector context

After all 5 ideas:
**Market Environment Summary** — Overall risk-on/risk-off reading and sector themes to watch

Be specific. Give real tickers and real price levels. If you don't know the current exact price, acknowledge that and frame levels as relative (e.g., "at or below the 20-day MA"). Ask what market or sector to focus on if the user hasn't specified.
If a chart image is uploaded, make one of the 5 setups based on that specific chart.
Remember our conversation history and build on prior analysis."""

CHART_ANALYSIS_SYSTEM = """You are an expert technical analyst specializing in multi-timeframe chart analysis. You read price structure the way a master reads a language — patterns, momentum, and context all at once.

Your role is to deliver complete, structured technical chart readings that lead to clear Buy / Hold / Sell decisions. Every conclusion you draw is supported by specific technical evidence from the chart.

When analyzing a stock or chart image, structure your response as a Technical Analysis Report:

**📈 TREND ANALYSIS**
- Daily trend direction, weekly trend, monthly trend
- Key trend lines and their current status

**🔲 SUPPORT & RESISTANCE**
- Exact price levels for major support and resistance
- How price has reacted at these levels historically

**〰️ MOVING AVERAGES**
- 20/50/100/200-day MA positions and what they signal
- Any crossovers (golden cross / death cross) and their implications

**⚡ MOMENTUM INDICATORS**
- RSI: current reading + interpretation
- MACD: signal crossovers, histogram direction, divergence

**📊 VOLUME**
- Whether volume confirms or contradicts the price move

**🔷 CHART PATTERNS**
- Any recognizable patterns forming or completed

**✅ DECISION**
- **BUY / HOLD / SELL** with specific price rationale
- Entry zone, stop-loss, and price target

Ask for the ticker if not provided. If a chart image is uploaded, perform the full analysis on that exact chart — prioritize what you can see visually.
Remember our conversation history and build on prior analysis."""

NEWS_SYSTEM = """You are a market intelligence analyst who specializes in translating financial news into actionable trading insights. You cut through noise to identify what actually matters for price.

Your role is to take news or events and convert them into clear trading implications. You think like a trader, not a journalist — you care about price impact, timing, and trade positioning.

When the user shares news or asks about a company/sector, structure your response as a Trading Intelligence Brief:

**📰 NEWS SUMMARY**
- What happened, in 2-3 bullet points (the facts only)

**📉📈 PRICE IMPACT ANALYSIS**
- Likely direction and magnitude of price movement
- What market participants are focusing on

**⏱️ SHORT-TERM IMPLICATIONS (Days/Weeks)**
- Immediate price reaction expected
- Key levels that confirm or invalidate the move

**📅 LONG-TERM IMPLICATIONS (Months/Years)**
- Structural impact on the business or sector
- Whether this changes the fundamental investment thesis

**📊 EXPECTED VOLATILITY RANGE**
- Estimated price move range based on the news magnitude

**🎯 TRADER'S INTERPRETATION**
- How a trader should read this: bullish / bearish / neutral
- Specific positioning suggestion (buy the dip / sell the rally / wait)

**⚠️ RISKS TO WATCH**
- What could make this news impact more or less severe than expected

Ask what company or sector to analyze if the user hasn't specified.
If a chart image is uploaded, combine the news context with the chart setup for a complete picture.
Remember our conversation history and build on prior analysis."""

BACKTEST_SYSTEM = """You are a quantitative trading strategist who designs and evaluates trading strategies through rigorous historical backtesting. You know the difference between a robust edge and curve-fitting.

Your role is to analyze trading strategies as if running a real backtest — examining statistical performance, identifying weaknesses, and suggesting improvements. You are honest about limitations and data biases.

When the user describes a strategy, structure your response as a Strategy Backtest Report:

**📋 STRATEGY DESCRIPTION**
- Strategy rules as you understand them (restate for clarity)

**📊 SIMULATED PERFORMANCE METRICS**
- Estimated win rate (% of trades profitable)
- Estimated total profit/loss over the period
- Maximum drawdown (worst peak-to-trough loss)
- Sharpe ratio estimate (risk-adjusted return)
- Average winner vs. average loser

**📅 PERFORMANCE BY MARKET CONDITION**
- How the strategy performs in trending vs. ranging markets
- Performance in bull vs. bear markets

**⚠️ KEY WEAKNESSES**
- Where this strategy typically fails
- Overfitting risks or data snooping concerns

**🔧 IMPROVEMENT SUGGESTIONS**
- 3 specific modifications to make it more robust
- Additional filters to reduce false signals
- Position sizing improvements

**✅ VERDICT**
- Is this strategy worth trading live? Under what conditions?

Be intellectually honest — acknowledge that you're simulating based on strategy logic, not running actual historical data. Ask for strategy details (exact rules, asset, timeframe) if not provided.
If a chart image is uploaded, use it to illustrate the strategy's signals on that specific price action.
Remember our conversation history and build on prior analysis."""

BIAS_SYSTEM = """You are a trading psychology coach and performance analyst who specializes in identifying cognitive biases and behavioral patterns that destroy trading profitability.

Your role is to examine trading history and behavior to expose the hidden mistakes that traders repeat without realizing it. You are direct, empathetic, and solutions-focused.

When the user shares their trading history or describes their patterns, structure your response as a Trading Psychology Analysis:

**🔍 BIAS IDENTIFICATION**
- Primary bias detected (e.g., confirmation bias, loss aversion, FOMO, revenge trading)
- Secondary biases present
- Evidence from the trades provided

**📊 PATTERN ANALYSIS**
- Repeating mistakes across trades
- Missed opportunities and why they were missed
- Signs of emotional or impulsive decisions

**🧠 ROOT CAUSE**
- What psychological mechanism is driving each bias
- When these biases are most likely to trigger

**💡 MISSED OPPORTUNITIES**
- Specific moments where a different decision would have been better
- What a disciplined trader would have done differently

**📏 3 PERSONALIZED TRADING RULES**
- Rule 1: [Specific rule targeting their primary bias]
- Rule 2: [Specific rule targeting their secondary bias]
- Rule 3: [Specific rule for risk/emotional management]

**✅ IMPLEMENTATION CHECKLIST**
- Daily pre-trade checklist to prevent these biases from triggering

Ask for specific trade history (entries, exits, results, emotions during the trade) if not provided. Be honest but constructive — your goal is improvement, not judgment.
If a chart image is uploaded, analyze whether the user's pattern can be spotted in that price action.
Remember our conversation history and build on prior analysis."""

DAILY_PLAN_SYSTEM = """You are an elite trading planner who builds complete, time-structured daily trading plans. You combine pre-market preparation, intraday execution frameworks, and end-of-day positioning into a single actionable blueprint.

Your role is to give traders a complete roadmap for the trading day — what to watch, when to act, and how to manage risk at every stage. You think in terms of preparation, execution, and review.

When asked to build a daily trading plan, structure your response as a Time-Stamped Trading Playbook:

**📋 PRE-MARKET CHECKLIST (Before Market Open)**
- Economic calendar events to watch today
- Overnight/pre-market price action notes
- Key levels identified before the open
- Mindset and risk parameters for today

**🔔 OPENING BELL STRATEGY (First 30-60 Minutes)**
- How to handle the open (trade it / watch it / fade it)
- Specific price levels to trigger a trade
- What to avoid in the first 15 minutes

**🕐 MID-DAY ADJUSTMENT POINTS (10:30 AM – 2:00 PM)**
- How to manage open positions
- New setups to look for in the lunch lull
- Criteria for adding to winners or cutting losses

**🕒 AFTERNOON SESSION (2:00 PM – Close)**
- Power hour setup identification
- End-of-day positioning rules
- When to be flat vs. hold overnight

**📊 END-OF-DAY REVIEW**
- Questions to answer before closing the trading platform
- What to note in the trading journal

**⚠️ TODAY'S RISK PARAMETERS**
- Max loss for the day (walk away rule)
- Max number of trades
- Position sizing guideline

Ask for the specific market or stock and today's key news events if the user hasn't provided them.
If a chart image is uploaded, build the daily plan around the levels visible in that chart.
Remember our conversation history and build on prior analysis."""

BEGINNER_SYSTEM = """You are a patient, knowledgeable investing teacher who specializes in making complex financial concepts simple and accessible. You never use jargon without immediately explaining it. You treat every question as a great question.

Your role is to explain stocks, companies, and investing concepts in plain language — the way you'd explain them to a smart friend who's just getting started. Your goal is education and confidence-building, not showing off knowledge.

When the user asks about a company or stock, cover these topics in simple language:

**🏢 WHAT IT DOES**
- What the company makes or does, in one sentence a 10-year-old could understand

**💰 HOW IT MAKES MONEY**
- Its business model in plain terms
- Main revenue streams

**📈 WHY INVESTORS CARE**
- What makes this company interesting or exciting to own
- The growth story or income story

**✅ WHAT COULD GO RIGHT**
- 2-3 reasons the stock could do well

**⚠️ WHAT COULD GO WRONG**
- 2-3 honest risks a beginner should know about

**📊 IS IT PROFITABLE?**
- Simply: is the company making money? Growing? How much?

**📉 IS IT GROWING?**
- Revenue and earnings trends in plain terms

**💳 DOES IT HAVE TOO MUCH DEBT?**
- Debt situation explained simply

**🏷️ IS THE PRICE FAIR?**
- Basic valuation (expensive/cheap/fair) with simple explanation

**🎯 TOP RISKS**
- The 1-2 biggest risks in simple terms

**✅ BEGINNER CHECKLIST**
- [ ] Easy to understand what they do
- [ ] Financially strong (profitable, low debt)
- [ ] Growing (revenues and earnings going up)
- [ ] Reasonably valued (not wildly overpriced)
- [ ] I understand the risks
- [ ] I need to research more before buying

Always end with honest, balanced advice. Encourage questions. Never make beginners feel stupid.
If a chart image is uploaded, describe what you see in the chart in simple terms the beginner can understand.
Remember our conversation history and build on prior analysis."""

# ── Gold Chart Analyzer system prompt (standalone /chart tool) ─────────────────
GOLD_CHART_SYSTEM = """You are an expert technical analyst specializing in Gold (XAU/USD) trading.
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

# ── Agent registry ─────────────────────────────────────────────────────────────
AGENTS = {
    "goldscalper":    {
        "name": "GoldScalperPro AI", "emoji": "🏆",
        "system": SYSTEM,
        "template_hint": "Analyze my XAUUSD setup and tell me if I should enter now.",
    },
    "goldman_sachs":  {
        "name": "Goldman Sachs Fundamental", "emoji": "🏦",
        "system": GOLDMAN_SYSTEM,
        "template_hint": "الرمز: [TICKER] — قدّم تحليلاً أساسياً كاملاً كتقرير أبحاث Goldman Sachs.",
    },
    "morgan_stanley": {
        "name": "Morgan Stanley Technical", "emoji": "📐",
        "system": MORGAN_SYSTEM,
        "template_hint": "الرمز: [TICKER] — وضعي: [LONG/SHORT/متابعة فقط] — حلّل الشارت فنياً.",
    },
    "bridgewater":    {
        "name": "Bridgewater Risk", "emoji": "🛡️",
        "system": BRIDGEWATER_SYSTEM,
        "template_hint": "ممتلكاتي: [TICKER مع نسبة التخصيص] — قيّم المخاطر كمحلل Bridgewater.",
    },
    "jpmorgan":       {
        "name": "JPMorgan Earnings", "emoji": "💼",
        "system": JPMORGAN_SYSTEM,
        "template_hint": "الرمز: [TICKER] — تاريخ الأرباح: [التاريخ] — حلّل الأرباح كـ JPMorgan.",
    },
    "citadel":        {
        "name": "Citadel Sector Rotation", "emoji": "🔄",
        "system": CITADEL_SYSTEM,
        "template_hint": "تركيز محفظتي: [وصف تحمّل المخاطر والقطاعات الحالية] — أي قطاعات أزود؟",
    },
    "renaissance":    {
        "name": "Renaissance Quant Filter", "emoji": "🔬",
        "system": RENAISSANCE_SYSTEM,
        "template_hint": "معاييري: [القطاعات المفضلة، نطاق القيمة السوقية، العوامل المهمة].",
    },
    "vanguard":       {
        "name": "Vanguard ETF Builder", "emoji": "📦",
        "system": VANGUARD_SYSTEM,
        "template_hint": "وضعي: [العمر، المبلغ، تحمّل المخاطر، المدة، نوع الحسابات] — ابنِ محفظة ETF.",
    },
    "trade_ideas":    {
        "name": "5 High-Probability Setups", "emoji": "💡",
        "system": TRADE_IDEAS_SYSTEM,
        "template_hint": "Scan today's market and give me 5 high-probability trade setups for [stock/sector].",
    },
    "chart_analysis": {
        "name": "AI Chart Analysis", "emoji": "📊",
        "system": CHART_ANALYSIS_SYSTEM,
        "template_hint": "Analyze [stock] on daily and weekly charts. Provide a Buy/Hold/Sell decision.",
    },
    "news_translator":{
        "name": "News → Trading Insight", "emoji": "📰",
        "system": NEWS_SYSTEM,
        "template_hint": "Summarize the latest news for [company/sector] and translate it into trade signals.",
    },
    "backtest":       {
        "name": "Strategy Backtester", "emoji": "⏮️",
        "system": BACKTEST_SYSTEM,
        "template_hint": "Backtest [strategy, e.g. MA crossover] on [stock/index] over the past [time period].",
    },
    "bias_exposer":   {
        "name": "Trading Bias Exposer", "emoji": "🧠",
        "system": BIAS_SYSTEM,
        "template_hint": "Review my last 20 trades: [paste entries/exits/results] and expose my biases.",
    },
    "daily_plan":     {
        "name": "Daily Trading Plan", "emoji": "📅",
        "system": DAILY_PLAN_SYSTEM,
        "template_hint": "Create a full-day trading plan for [market/stock] starting at market open.",
    },
    "beginner":       {
        "name": "Beginner Stock Checklist", "emoji": "🎓",
        "system": BEGINNER_SYSTEM,
        "template_hint": "Explain [COMPANY / TICKER] in simple language and give me a beginner checklist.",
    },
}

# ── Per-agent state ────────────────────────────────────────────────────────────
agent_conversations = {aid: [] for aid in AGENTS}
current_agent = "goldscalper"

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

# ── Capital.com live positions ─────────────────────────────────────────────────
def _capital_login():
    global _cap_cst, _cap_sec
    if not (CAPITAL_API_KEY and CAPITAL_PASSWORD and CAPITAL_EMAIL):
        return False
    try:
        r = _requests.post(
            f"{CAPITAL_BASE}/session",
            headers={"X-CAP-API-KEY": CAPITAL_API_KEY, "Content-Type": "application/json"},
            json={"identifier": CAPITAL_EMAIL, "password": CAPITAL_PASSWORD, "encryptedPassword": False},
            timeout=10,
        )
        if r.status_code == 200:
            _cap_cst = r.headers.get("CST")
            _cap_sec = r.headers.get("X-SECURITY-TOKEN")
            return True
        print(f"  Capital.com login failed: {r.status_code} {r.text[:120]}")
    except Exception as e:
        print(f"  Capital.com login error: {e}")
    return False

def _capital_fetch():
    global _cap_cst, _cap_sec
    if not _cap_cst and not _capital_login():
        return
    try:
        r = _requests.get(
            f"{CAPITAL_BASE}/positions",
            headers={"X-CAP-API-KEY": CAPITAL_API_KEY, "CST": _cap_cst, "X-SECURITY-TOKEN": _cap_sec},
            timeout=10,
        )
        if r.status_code == 401:
            _cap_cst = None
            if _capital_login():
                _capital_fetch()
            return
        if r.status_code == 200:
            with price_lock:
                capital_positions.clear()
                for pos in r.json().get("positions", []):
                    p = pos.get("position", {})
                    m = pos.get("market", {})
                    capital_positions.append({
                        "symbol":    m.get("instrumentName", m.get("epic", "?")),
                        "direction": p.get("direction", ""),
                        "size":      p.get("size", 0),
                        "open":      p.get("openLevel", 0),
                        "pnl":       round(p.get("profit", 0), 2),
                        "currency":  p.get("currency", ""),
                    })
    except Exception as e:
        print(f"  Capital.com positions error: {e}")

def capital_worker():
    while True:
        _capital_fetch()
        time.sleep(15)

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)

@app.route("/")
def index():
    return HTML

@app.route("/chart")
def chart_page():
    return CHART_HTML

@app.route("/price")
def get_price():
    with price_lock:
        return jsonify(live_price)

@app.route("/agents")
def get_agents():
    return jsonify({
        "agents": [
            {"id": k, "name": v["name"], "emoji": v["emoji"], "template_hint": v["template_hint"]}
            for k, v in AGENTS.items()
        ],
        "current": current_agent,
    })

@app.route("/agent", methods=["POST"])
def set_agent():
    global current_agent
    agent_id = (request.get_json(silent=True) or {}).get("agent_id", "")
    if agent_id not in AGENTS:
        return jsonify({"error": "Unknown agent"}), 400
    current_agent = agent_id
    return jsonify({
        "status":        "ok",
        "agent_id":      agent_id,
        "name":          AGENTS[agent_id]["name"],
        "emoji":         AGENTS[agent_id]["emoji"],
        "template_hint": AGENTS[agent_id]["template_hint"],
        "history_len":   len(agent_conversations[agent_id]),
    })

@app.route("/positions")
def positions_endpoint():
    return jsonify({"positions": capital_positions})

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    msg  = data.get("message") or data.get("text") or json.dumps(data)
    ts   = datetime.now().strftime("%H:%M:%S")
    tv_alerts.append({"time": ts, "message": msg})
    agent_conversations[current_agent].append({
        "role": "user",
        "content": f"[TradingView Alert {ts}]: {msg}",
    })
    return jsonify({"status": "ok"})

@app.route("/alerts")
def get_alerts():
    return jsonify({"alerts": tv_alerts[-20:]})

@app.route("/clear", methods=["POST"])
def clear():
    agent_id = (request.get_json(silent=True) or {}).get("agent_id", current_agent)
    if agent_id in agent_conversations:
        agent_conversations[agent_id].clear()
    return jsonify({"status": "cleared", "agent_id": agent_id})

# ── Gold Chart Analyzer endpoint ───────────────────────────────────────────────
@app.route("/analyze", methods=["POST"])
def analyze():
    if "chart" not in request.files:
        return jsonify({"error": "No chart image provided"}), 400

    chart_file = request.files["chart"]
    question   = request.form.get("question", "Analyze this chart and give me a trading recommendation.")

    image_bytes = chart_file.read()
    image_b64   = base64.standard_b64encode(image_bytes).decode("utf-8")

    fname = chart_file.filename.lower()
    if fname.endswith(".png"):
        media_type = "image/png"
    elif fname.endswith((".jpg", ".jpeg")):
        media_type = "image/jpeg"
    elif fname.endswith(".webp"):
        media_type = "image/webp"
    else:
        media_type = "image/png"

    try:
        client = anthropic.Anthropic(api_key=API_KEY)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=GOLD_CHART_SYSTEM,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                    {"type": "text",  "text": question},
                ],
            }],
        )
        return jsonify({"analysis": resp.content[0].text})
    except anthropic.APIError as e:
        return jsonify({"error": f"API error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500

@app.route("/chat", methods=["POST"])
def chat():
    text     = request.form.get("message", "").strip()
    chart    = request.files.get("chart")
    agent_id = request.form.get("agent_id", current_agent)
    if agent_id not in AGENTS:
        agent_id = current_agent

    conversation = agent_conversations[agent_id]
    system       = AGENTS[agent_id]["system"]

    ctx = []
    with price_lock:
        if live_price["price"]:
            ctx.append(f"Live Gold (XAU/USD): ${live_price['price']} ({live_price['change']:+.2f} / {live_price['pct']:+.3f}%)")
        if capital_positions:
            ctx.append("Open Capital.com positions:\n" + json.dumps(capital_positions, indent=2))

    full_text = ("\n".join(ctx) + "\n\n" + text).strip() if ctx else text

    content = []
    if chart:
        raw   = chart.read()
        b64   = base64.standard_b64encode(raw).decode()
        fname = chart.filename.lower()
        mime  = ("image/png"  if fname.endswith(".png")  else
                 "image/jpeg" if fname.endswith((".jpg", ".jpeg")) else
                 "image/webp" if fname.endswith(".webp")  else "image/png")
        content.append({"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}})

    fallback = f"Analyze this chart as a {AGENTS[agent_id]['name']} analyst."
    content.append({"type": "text", "text": full_text or fallback})
    conversation.append({"role": "user", "content": content})

    api_messages = _clean_history(conversation)

    try:
        client = anthropic.Anthropic(api_key=API_KEY)
        resp   = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=system,
            messages=api_messages,
        )
        reply = resp.content[0].text
        conversation.append({"role": "assistant", "content": reply})
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
            new_content = []
            for c in m["content"]:
                if c.get("type") == "image":
                    new_content.append({"type": "text", "text": "[chart image from earlier in conversation]"})
                else:
                    new_content.append(c)
            result.append({"role": m["role"], "content": new_content})
        else:
            result.append(m)
    return result

# ── Embedded HTML — main hub ─────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Trading AI Hub</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d0f14;color:#e0e0e0;font-family:'Segoe UI',system-ui,sans-serif;height:100vh;display:flex;flex-direction:column;overflow:hidden}

/* ── Header ── */
#header{background:#111318;border-bottom:1px solid #1f2230;padding:10px 16px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0;gap:10px}
#header-title{font-size:1rem;color:#f5c518;font-weight:700;letter-spacing:.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:220px}
#ticker{font-size:.9rem;font-weight:600;white-space:nowrap}
#ticker.up{color:#26a69a}#ticker.down{color:#ef5350}#ticker.flat{color:#888}
#header-right{display:flex;align-items:center;gap:8px;flex-shrink:0}
#chart-scan-btn{background:#1e2235;border:1px solid #2a2d35;color:#f5c518;border-radius:6px;padding:4px 10px;cursor:pointer;font-size:.75rem;text-decoration:none;white-space:nowrap;transition:border-color .2s}
#chart-scan-btn:hover{border-color:#f5c518}
#clear-btn{background:transparent;border:1px solid #2a2d35;color:#888;border-radius:6px;padding:4px 10px;cursor:pointer;font-size:.75rem;transition:border-color .2s,color .2s;white-space:nowrap}
#clear-btn:hover{border-color:#f5c518;color:#f5c518}

/* ── Mobile agent dropdown ── */
#agent-dropdown-wrap{display:none;background:#111318;border-bottom:1px solid #1f2230;padding:6px 10px;flex-shrink:0}
#agent-select{width:100%;background:#0d0f14;border:1px solid #2a2d35;color:#e0e0e0;border-radius:6px;padding:7px 10px;font-size:.85rem;outline:none;cursor:pointer}
#agent-select:focus{border-color:#f5c518}

/* ── 3-column body ── */
#body{display:flex;flex:1;overflow:hidden}

/* ── Agent sidebar (left) ── */
#agent-sidebar{width:220px;border-right:1px solid #1f2230;display:flex;flex-direction:column;overflow:hidden;flex-shrink:0;background:#0a0c10}
#agent-sidebar-header{padding:10px 12px;font-size:.7rem;text-transform:uppercase;letter-spacing:1px;color:#666;font-weight:600;background:#111318;border-bottom:1px solid #1f2230;flex-shrink:0}
#agent-list{overflow-y:auto;flex:1;padding:4px 0}
#agent-list::-webkit-scrollbar{width:3px}
#agent-list::-webkit-scrollbar-thumb{background:#2a2d35}
.agent-item{display:flex;align-items:center;gap:8px;padding:9px 12px;cursor:pointer;font-size:.8rem;color:#999;transition:background .12s,color .12s;border-left:2px solid transparent;line-height:1.3;user-select:none}
.agent-item:hover{background:#111318;color:#ddd}
.agent-item.active{background:#161920;color:#f5c518;border-left-color:#f5c518}
.agent-emoji{font-size:.95rem;flex-shrink:0;width:20px;text-align:center}
.agent-name{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

/* ── Chat panel ── */
#chat-panel{flex:1;display:flex;flex-direction:column;min-width:0}
#messages{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px}
#messages::-webkit-scrollbar{width:4px}
#messages::-webkit-scrollbar-thumb{background:#2a2d35;border-radius:4px}

.msg{max-width:84%;padding:10px 13px;border-radius:10px;font-size:.88rem;line-height:1.65;word-break:break-word}
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
#msg-input::placeholder{color:#444;font-size:.82rem}
#send-btn{background:#f5c518;color:#0d0f14;border:none;border-radius:8px;padding:9px 14px;cursor:pointer;font-weight:700;font-size:.9rem;flex-shrink:0;transition:opacity .2s}
#send-btn:disabled{opacity:.4;cursor:not-allowed}

/* ── Right sidebar ── */
#right-sidebar{width:260px;border-left:1px solid #1f2230;display:flex;flex-direction:column;overflow:hidden;flex-shrink:0}
.panel{border-bottom:1px solid #1f2230;display:flex;flex-direction:column}
.panel-header{padding:10px 12px;font-size:.7rem;text-transform:uppercase;letter-spacing:1px;color:#888;font-weight:600;background:#111318;flex-shrink:0}
.panel-body{padding:10px 12px;font-size:.8rem;overflow-y:auto;max-height:200px;flex:1}
.panel-body::-webkit-scrollbar{width:3px}
.panel-body::-webkit-scrollbar-thumb{background:#2a2d35}

.trade-card{background:#0d0f14;border:1px solid #1f2230;border-radius:6px;padding:8px;margin-bottom:7px}
.trade-card .symbol{font-weight:700;font-size:.82rem;color:#e0e0e0}
.trade-card .dir{display:inline-block;padding:1px 6px;border-radius:3px;font-size:.7rem;font-weight:700;margin-left:5px}
.dir.buy{background:#0d2b2b;color:#26a69a}.dir.sell{background:#2b0d0d;color:#ef5350}
.trade-card .detail{color:#888;font-size:.75rem;margin-top:3px}
.trade-card .pnl{font-weight:600;font-size:.82rem;margin-top:2px}
.pnl.pos{color:#26a69a}.pnl.neg{color:#ef5350}
.no-data{color:#444;font-style:italic;font-size:.78rem}

.alert-item{border-left:2px solid #f5c518;padding:4px 8px;margin-bottom:6px;font-size:.76rem;color:#bbb}
.alert-item .alert-time{color:#888;font-size:.7rem}
#tv-setup{padding:10px 12px;font-size:.75rem;color:#555;line-height:1.5;flex:1}

/* ── Welcome message ── */
.welcome{text-align:center;color:#444;font-size:.85rem;padding:30px 20px;line-height:1.8}
.welcome .welcome-icon{font-size:2rem;display:block;margin-bottom:8px}
.welcome .welcome-hint{font-size:.78rem;color:#333;margin-top:8px;font-style:italic;padding:0 10px}

/* ── Responsive ── */
@media(max-width:900px){
  #agent-sidebar{display:none}
  #agent-dropdown-wrap{display:block}
}
@media(max-width:640px){#right-sidebar{display:none}}
</style>
</head>
<body>

<div id="header">
  <h1 id="header-title">🏆 GoldScalperPro AI</h1>
  <div id="header-right">
    <span id="ticker" class="flat">XAUUSD —</span>
    <a id="chart-scan-btn" href="/chart" target="_blank">📈 Chart Scan</a>
    <button id="clear-btn" onclick="clearChat()">Clear chat</button>
  </div>
</div>

<div id="agent-dropdown-wrap">
  <select id="agent-select" onchange="switchAgent(this.value)"></select>
</div>

<div id="body">

  <!-- LEFT: Agent list -->
  <div id="agent-sidebar">
    <div id="agent-sidebar-header">🤖 AI Analysts</div>
    <div id="agent-list"></div>
  </div>

  <!-- CENTER: Chat -->
  <div id="chat-panel">
    <div id="messages">
      <div class="welcome" id="welcome-msg">
        <span class="welcome-icon">📈</span>
        <strong>Trading AI Hub</strong><br>
        Select an analyst from the left panel, then type your question.<br>
        <span class="welcome-hint">Attach a chart screenshot for visual analysis · or use <strong>📈 Chart Scan</strong> for a quick Gold read.</span>
      </div>
    </div>

    <div id="input-bar">
      <label id="attach-btn" for="file-input" title="Attach chart">📎</label>
      <input type="file" id="file-input" accept="image/*" onchange="onFileSelected(this)"/>
      <textarea id="msg-input" placeholder="Select an agent to get started…" onkeydown="onKey(event)" oninput="autoResize(this)"></textarea>
      <button id="send-btn" onclick="sendMessage()">▶</button>
    </div>
  </div>

  <!-- RIGHT: Capital.com + Alerts -->
  <div id="right-sidebar">

    <div class="panel" style="flex:0 0 auto">
      <div class="panel-header">📊 Capital.com Positions</div>
      <div class="panel-body" id="trades-panel">
        <div class="no-data" id="no-positions">Connecting to Capital.com…</div>
      </div>
    </div>

    <div class="panel" style="flex:1">
      <div class="panel-header">⚡ TradingView Alerts</div>
      <div class="panel-body" id="alerts-panel">
        <div class="no-data" id="no-alerts">No alerts yet.</div>
      </div>
    </div>

    <div id="tv-setup">
      <b style="color:#888">TradingView webhook:</b><br>
      Alert → Notifications → Webhook URL:<br>
      <code style="color:#f5c518">http://YOUR-IP:5000/webhook</code><br><br>
      <b style="color:#888">Capital.com:</b> Set<br>
      <code style="color:#f5c518">CAPITAL_EMAIL</code> in your .env
    </div>

  </div>
</div>

<script>
let selectedFile    = null;
let currentAgentId  = 'goldscalper';
let agentsData      = {};

async function loadAgents(){
  try{
    const d = await (await fetch('/agents')).json();
    currentAgentId = d.current;
    agentsData     = {};

    const listEl   = document.getElementById('agent-list');
    const selectEl = document.getElementById('agent-select');
    listEl.innerHTML   = '';
    selectEl.innerHTML = '';

    d.agents.forEach(a => {
      agentsData[a.id] = a;

      const item = document.createElement('div');
      item.className  = 'agent-item' + (a.id === d.current ? ' active' : '');
      item.dataset.id = a.id;
      item.innerHTML  = `<span class="agent-emoji">${a.emoji}</span><span class="agent-name">${a.name}</span>`;
      item.onclick    = () => switchAgent(a.id);
      listEl.appendChild(item);

      const opt = document.createElement('option');
      opt.value    = a.id;
      opt.text     = `${a.emoji} ${a.name}`;
      opt.selected = (a.id === d.current);
      selectEl.appendChild(opt);
    });

    updateHeaderAndHint(d.current);
  } catch(e){ console.error('loadAgents failed', e); }
}

async function switchAgent(agentId){
  if(agentId === currentAgentId) return;
  try{
    const res  = await fetch('/agent',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent_id:agentId})});
    const data = await res.json();
    if(data.error) return;

    currentAgentId = agentId;

    document.querySelectorAll('.agent-item').forEach(el =>
      el.classList.toggle('active', el.dataset.id === agentId)
    );
    document.getElementById('agent-select').value = agentId;

    const msgs = document.getElementById('messages');
    const a    = agentsData[agentId] || {};
    if(data.history_len > 0){
      msgs.innerHTML = `<div class="welcome">
        <span class="welcome-icon">${a.emoji||'🤖'}</span>
        <strong>${a.name}</strong><br>
        Resuming your previous conversation (${data.history_len} messages).<br>
        <span class="welcome-hint">Type a message to continue, or click <em>Clear chat</em> to start fresh.</span>
      </div>`;
    } else {
      msgs.innerHTML = `<div class="welcome">
        <span class="welcome-icon">${a.emoji||'🤖'}</span>
        Switched to <strong>${a.name}</strong>.<br>
        <span class="welcome-hint">Try: "${a.template_hint||\'\'}"</span>
      </div>`;
    }
    updateHeaderAndHint(agentId);
  } catch(e){ console.error('switchAgent error', e); }
}

function updateHeaderAndHint(agentId){
  const a = agentsData[agentId];
  if(!a) return;
  document.getElementById('header-title').textContent = `${a.emoji} ${a.name}`;
  document.getElementById('msg-input').placeholder    = a.template_hint || 'Type your message…';
}

function onFileSelected(input){
  selectedFile = input.files[0] || null;
  const btn = document.getElementById('attach-btn');
  btn.classList.toggle('has-file', !!selectedFile);
  btn.title = selectedFile ? selectedFile.name : 'Attach chart';
}

function autoResize(el){
  el.style.height='40px';
  el.style.height = Math.min(el.scrollHeight, 120)+'px';
}

function onKey(e){
  if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); sendMessage(); }
}

async function sendMessage(){
  const input   = document.getElementById('msg-input');
  const text    = input.value.trim();
  if(!text && !selectedFile) return;

  const sendBtn = document.getElementById('send-btn');
  sendBtn.disabled = true;

  const msgs    = document.getElementById('messages');
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

  const typing = document.createElement('div');
  typing.className  = 'msg bot typing';
  typing.textContent = 'Analyzing…';
  msgs.appendChild(typing);
  msgs.scrollTop = msgs.scrollHeight;

  input.value = '';
  input.style.height = '40px';

  const fd = new FormData();
  if(text) fd.append('message', text);
  if(selectedFile) fd.append('chart', selectedFile, selectedFile.name);
  fd.append('agent_id', currentAgentId);

  selectedFile = null;
  document.getElementById('file-input').value = '';
  document.getElementById('attach-btn').classList.remove('has-file');
  document.getElementById('attach-btn').title = 'Attach chart';

  try{
    const res  = await fetch('/chat',{method:'POST',body:fd});
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

function formatMsg(text){
  return text
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/\n/g,'<br>');
}

async function clearChat(){
  await fetch('/clear',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent_id:currentAgentId})});
  const msgs = document.getElementById('messages');
  const a    = agentsData[currentAgentId] || {};
  msgs.innerHTML = `<div class="welcome">
    <span class="welcome-icon">${a.emoji||'📈'}</span>
    Chat cleared. <strong>${a.name||'Agent'}</strong> is ready for a new session.
  </div>`;
}

async function updatePrice(){
  try{
    const d  = await (await fetch('/price')).json();
    const el = document.getElementById('ticker');
    if(d.price){
      const sign = d.change >= 0 ? '+' : '';
      el.textContent = `XAUUSD $${d.price}  ${sign}${d.change} (${sign}${d.pct}%)`;
      el.className   = d.change > 0 ? 'up' : d.change < 0 ? 'down' : 'flat';
    }
  } catch(e){}
}

async function updateTrades(){
  try{
    const d     = await (await fetch('/positions')).json();
    const panel = document.getElementById('trades-panel');
    if(!d.positions || !d.positions.length){
      panel.innerHTML = '<div class="no-data">No open positions.<br>Set CAPITAL_EMAIL in .env to connect.</div>';
      return;
    }
    panel.innerHTML = d.positions.map(t => {
      const pnlClass = t.pnl >= 0 ? 'pos' : 'neg';
      const sign     = t.pnl >= 0 ? '+' : '';
      const dirClass = t.direction === 'BUY' ? 'buy' : 'sell';
      return `<div class="trade-card">
        <div><span class="symbol">${t.symbol}</span><span class="dir ${dirClass}">${t.direction}</span></div>
        <div class="detail">Size: ${t.size} | Open: ${t.open}</div>
        <div class="pnl ${pnlClass}">${sign}${t.pnl} ${t.currency}</div>
      </div>`;
    }).join('');
  } catch(e){}
}

async function updateAlerts(){
  try{
    const d     = await (await fetch('/alerts')).json();
    const panel = document.getElementById('alerts-panel');
    if(!d.alerts || !d.alerts.length) return;
    document.getElementById('no-alerts')?.remove();
    panel.innerHTML = d.alerts.slice().reverse().map(a =>
      `<div class="alert-item"><div class="alert-time">${a.time}</div>${escHtml(a.message)}</div>`
    ).join('');
  } catch(e){}
}

function escHtml(s){ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') }

loadAgents();
updatePrice();  setInterval(updatePrice,  30000);
updateTrades(); setInterval(updateTrades, 10000);
updateAlerts(); setInterval(updateAlerts, 15000);
</script>
</body>
</html>"""

# ── Embedded HTML — Gold Chart Analyzer ───────────────────────────────────────────────
CHART_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Gold Chart Analyzer</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d0f14;color:#e0e0e0;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:32px 16px}
header{text-align:center;margin-bottom:32px}
header h1{font-size:1.6rem;color:#f5c518;letter-spacing:.5px}
header p{color:#888;font-size:.9rem;margin-top:6px}
.back-link{display:inline-block;margin-bottom:20px;color:#888;font-size:.8rem;text-decoration:none;border:1px solid #2a2d35;border-radius:6px;padding:4px 10px;transition:color .2s,border-color .2s}
.back-link:hover{color:#f5c518;border-color:#f5c518}
.card{background:#161920;border:1px solid #2a2d35;border-radius:12px;padding:24px;width:100%;max-width:780px;margin-bottom:20px}
.card h2{font-size:.85rem;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:14px}
#drop-zone{border:2px dashed #2e3340;border-radius:10px;padding:40px 20px;text-align:center;cursor:pointer;transition:border-color .2s,background .2s;position:relative}
#drop-zone:hover,#drop-zone.drag-over{border-color:#f5c518;background:#1a1d24}
#drop-zone input[type="file"]{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%}
#drop-zone .drop-icon{font-size:2.5rem;margin-bottom:10px}
#drop-zone p{color:#888;font-size:.9rem}
#drop-zone .drop-label{color:#e0e0e0;font-size:1rem;font-weight:500;margin-bottom:4px}
#preview-wrap{display:none;margin-top:16px;position:relative}
#preview-wrap img{width:100%;max-height:320px;object-fit:contain;border-radius:8px;border:1px solid #2a2d35;background:#0d0f14}
#remove-btn{position:absolute;top:8px;right:8px;background:rgba(0,0,0,.7);color:#f5c518;border:none;border-radius:6px;padding:4px 10px;cursor:pointer;font-size:.8rem}
#question{width:100%;background:#0d0f14;border:1px solid #2a2d35;border-radius:8px;color:#e0e0e0;font-size:.95rem;padding:12px 14px;resize:vertical;min-height:72px;font-family:inherit;outline:none;transition:border-color .2s}
#question:focus{border-color:#f5c518}
#analyze-btn{width:100%;max-width:780px;padding:14px;background:#f5c518;color:#0d0f14;font-weight:700;font-size:1rem;border:none;border-radius:10px;cursor:pointer;letter-spacing:.5px;transition:opacity .2s;margin-bottom:20px}
#analyze-btn:disabled{opacity:.45;cursor:not-allowed}
#result-card{display:none}
#result-body{background:#0d0f14;border:1px solid #2a2d35;border-radius:8px;padding:18px;font-size:.93rem;line-height:1.7;white-space:pre-wrap;color:#d4d4d4;max-height:520px;overflow-y:auto}
#result-body strong{color:#f5c518}
.result-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}
#reset-btn{background:transparent;border:1px solid #2a2d35;color:#888;border-radius:6px;padding:5px 12px;cursor:pointer;font-size:.8rem;transition:border-color .2s,color .2s}
#reset-btn:hover{border-color:#f5c518;color:#f5c518}
.spinner{display:inline-block;width:18px;height:18px;border:2px solid #0d0f14;border-top-color:transparent;border-radius:50%;animation:spin .7s linear infinite;vertical-align:middle;margin-right:8px}
@keyframes spin{to{transform:rotate(360deg)}}
#error-msg{display:none;color:#e05252;font-size:.88rem;margin-top:10px;text-align:center}
footer{color:#444;font-size:.78rem;margin-top:16px}
</style>
</head>
<body>

<a class="back-link" href="/">← Back to AI Hub</a>

<header>
  <h1>📈 Gold Chart Analyzer</h1>
  <p>Upload a chart screenshot — get an instant structured XAUUSD analysis</p>
</header>

<div class="card">
  <h2>Chart Screenshot</h2>
  <div id="drop-zone">
    <input type="file" id="file-input" accept="image/*"/>
    <div class="drop-icon">📊</div>
    <div class="drop-label">Drop your chart here</div>
    <p>or click to browse — PNG, JPG, WebP supported</p>
  </div>
  <div id="preview-wrap">
    <img id="preview-img" src="" alt="Chart preview"/>
    <button id="remove-btn">✕ Remove</button>
  </div>
</div>

<div class="card">
  <h2>Your Question</h2>
  <textarea id="question" placeholder="e.g. Should I enter a long position here? Where is the nearest support?">Analyze this chart and give me a trading recommendation.</textarea>
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

<footer>Powered by Claude Vision · For educational purposes only · Not financial advice</footer>

<script>
const dropZone    = document.getElementById('drop-zone');
const fileInput   = document.getElementById('file-input');
const previewWrap = document.getElementById('preview-wrap');
const previewImg  = document.getElementById('preview-img');
const removeBtn   = document.getElementById('remove-btn');
const questionEl  = document.getElementById('question');
const analyzeBtn  = document.getElementById('analyze-btn');
const resultCard  = document.getElementById('result-card');
const resultBody  = document.getElementById('result-body');
const errorMsg    = document.getElementById('error-msg');
const resetBtn    = document.getElementById('reset-btn');

let selectedFile = null;

dropZone.addEventListener('dragover', e=>{ e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', ()=> dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e=>{
  e.preventDefault(); dropZone.classList.remove('drag-over');
  if(e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', ()=>{ if(fileInput.files.length) handleFile(fileInput.files[0]); });

function handleFile(file){
  if(!file.type.startsWith('image/')){ showError('Please upload an image file.'); return; }
  selectedFile = file;
  const reader = new FileReader();
  reader.onload = e=>{
    previewImg.src = e.target.result;
    previewWrap.style.display = 'block';
    dropZone.querySelector('input').style.display = 'none';
    analyzeBtn.disabled = false;
    hideError();
  };
  reader.readAsDataURL(file);
}

removeBtn.addEventListener('click', resetUpload);
function resetUpload(){
  selectedFile = null;
  previewWrap.style.display = 'none';
  previewImg.src = '';
  fileInput.value = '';
  dropZone.querySelector('input').style.display = '';
  analyzeBtn.disabled = true;
}

analyzeBtn.addEventListener('click', async()=>{
  if(!selectedFile) return;
  analyzeBtn.disabled = true;
  analyzeBtn.innerHTML = '<span class="spinner"></span>Analyzing…';
  resultCard.style.display = 'none';
  hideError();

  const fd = new FormData();
  fd.append('chart', selectedFile, selectedFile.name);
  fd.append('question', questionEl.value.trim() || 'Analyze this chart and give me a trading recommendation.');

  try{
    const res  = await fetch('/analyze',{method:'POST',body:fd});
    const data = await res.json();
    if(data.error){ showError(data.error); }
    else { renderAnalysis(data.analysis); }
  } catch(e){
    showError('Could not reach the server.');
  } finally{
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = 'Analyze Chart';
  }
});

resetBtn.addEventListener('click', ()=>{
  resultCard.style.display = 'none';
  resetUpload();
  questionEl.value = 'Analyze this chart and give me a trading recommendation.';
});

function renderAnalysis(text){
  resultBody.innerHTML = text.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');
  resultCard.style.display = 'block';
  resultCard.scrollIntoView({behavior:'smooth',block:'start'});
}
function showError(msg){ errorMsg.textContent = '⚠ '+msg; errorMsg.style.display = 'block'; }
function hideError(){ errorMsg.style.display = 'none'; }
</script>
</body>
</html>"""

if __name__ == "__main__":
    if HAS_YFINANCE:
        threading.Thread(target=price_worker, daemon=True).start()
        print(" Live Gold price feed active (XAU/USD via yfinance)")
    else:
        print(" TIP: pip install yfinance for live Gold price feed")

    if HAS_REQUESTS and CAPITAL_API_KEY and CAPITAL_EMAIL:
        threading.Thread(target=capital_worker, daemon=True).start()
        print(" Capital.com positions feed active")
    elif not CAPITAL_EMAIL:
        print(" TIP: Set CAPITAL_EMAIL in .env to enable Capital.com positions")

    print(f"\n Trading AI Hub — {len(AGENTS)} AI Analysts + Gold Chart Analyzer")
    print(" Chat hub    : http://localhost:5000")
    print(" Chart Scan  : http://localhost:5000/chart")
    print(" Alerts      : POST http://localhost:5000/webhook (from TradingView)\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
