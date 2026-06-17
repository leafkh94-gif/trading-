"""
quick_swing.py
==============
Quick Swing Signal Detector — 15-30 min timeframe
Instruments: Gold (XAU/USD), US500, US100, US30
Sends alerts to Telegram + powers the web dashboard

Add this file to your trading- repo root.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
from datetime import datetime, timezone

# ─────────────────────────────────────────────
# CONFIG — set these in your .env or Render env vars
# ─────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

INSTRUMENTS = {
    "GOLD":  "GC=F",
    "US500": "ES=F",
    "US100": "NQ=F",
    "US30":  "YM=F",
}

# Signal config
EMA_FAST        = 9
EMA_SLOW        = 21
RSI_PERIOD      = 14
ATR_PERIOD      = 14
MIN_RR          = 1.5       # Minimum Risk:Reward ratio
ATR_SL_MULT     = 1.2       # Stop loss = 1.2x ATR below/above entry
ATR_TP_MULT     = 1.8       # Take profit = 1.8x ATR (gives R:R > 1.5)
CANDLE_STRENGTH = 0.6       # Body must be 60% of full candle range

# Session windows (UTC)
SESSIONS = {
    "London Open":    (7,  9),   # 07:00–09:00 UTC
    "New York Open":  (13, 15),  # 13:00–15:00 UTC
    "London-NY Overlap": (13, 17),
}


# ─────────────────────────────────────────────
# INDICATORS
# ─────────────────────────────────────────────

def calc_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    hl  = df["High"] - df["Low"]
    hpc = (df["High"] - df["Close"].shift()).abs()
    lpc = (df["Low"]  - df["Close"].shift()).abs()
    tr  = pd.concat([hl, hpc, lpc], axis=1).max(axis=1)
    return tr.rolling(period).mean()


# ─────────────────────────────────────────────
# SESSION CHECK
# ─────────────────────────────────────────────

def get_active_session() -> str:
    hour = datetime.now(timezone.utc).hour
    for name, (start, end) in SESSIONS.items():
        if start <= hour < end:
            return name
    return "Off-session"


# ─────────────────────────────────────────────
# SIGNAL LOGIC
# ─────────────────────────────────────────────

def detect_signal(df: pd.DataFrame) -> dict | None:
    """
    Returns a signal dict or None.
    Conditions (ALL must be met):
      1. EMA 9 crosses above/below EMA 21 in last 2 candles
      2. RSI confirms direction (>52 for BUY, <48 for SELL)
      3. Strong candle: body >= 60% of range
      4. R:R >= 1.5
    """
    if len(df) < EMA_SLOW + 5:
        return None

    df = df.copy()
    df["ema_fast"] = calc_ema(df["Close"], EMA_FAST)
    df["ema_slow"] = calc_ema(df["Close"], EMA_SLOW)
    df["rsi"]      = calc_rsi(df["Close"], RSI_PERIOD)
    df["atr"]      = calc_atr(df, ATR_PERIOD)

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    # ── Candle strength check
    candle_range = curr["High"] - curr["Low"]
    candle_body  = abs(curr["Close"] - curr["Open"])
    if candle_range == 0:
        return None
    strength = candle_body / candle_range

    if strength < CANDLE_STRENGTH:
        return None  # Weak/indecisive candle — skip

    # ── EMA crossover detection
    ema_crossed_up   = (prev["ema_fast"] <= prev["ema_slow"]) and (curr["ema_fast"] > curr["ema_slow"])
    ema_crossed_down = (prev["ema_fast"] >= prev["ema_slow"]) and (curr["ema_fast"] < curr["ema_slow"])

    if not ema_crossed_up and not ema_crossed_down:
        return None  # No crossover — no trade

    direction = "BUY" if ema_crossed_up else "SELL"

    # ── RSI confirmation
    rsi_val = curr["rsi"]
    if direction == "BUY"  and rsi_val < 52:
        return None
    if direction == "SELL" and rsi_val > 48:
        return None

    # ── Price levels
    atr       = curr["atr"]
    entry     = curr["Close"]

    if direction == "BUY":
        sl = entry - (atr * ATR_SL_MULT)
        tp = entry + (atr * ATR_TP_MULT)
    else:
        sl = entry + (atr * ATR_SL_MULT)
        tp = entry - (atr * ATR_TP_MULT)

    risk   = abs(entry - sl)
    reward = abs(tp - entry)
    rr     = round(reward / risk, 2) if risk > 0 else 0

    if rr < MIN_RR:
        return None  # Bad R:R — skip

    return {
        "direction": direction,
        "entry":     round(entry, 4),
        "sl":        round(sl, 4),
        "tp":        round(tp, 4),
        "rr":        rr,
        "rsi":       round(rsi_val, 1),
        "candle_strength": round(strength * 100, 1),
        "atr":       round(atr, 4),
    }


# ─────────────────────────────────────────────
# DATA FETCH
# ─────────────────────────────────────────────

def fetch_data(symbol: str, interval: str = "15m") -> pd.DataFrame | None:
    try:
        df = yf.download(symbol, period="2d", interval=interval,
                         auto_adjust=True, progress=False)
        if df.empty or len(df) < 30:
            return None
        # Flatten multi-level columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        print(f"  ⚠️  Failed to fetch {symbol}: {e}")
        return None


# ─────────────────────────────────────────────
# TELEGRAM ALERT
# ─────────────────────────────────────────────

def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("  ⚠️  Telegram not configured — skipping alert")
        return
    url  = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        r = requests.post(url, data=data, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"  ⚠️  Telegram send failed: {e}")


def format_alert(name: str, signal: dict, session: str) -> str:
    emoji = "🟢" if signal["direction"] == "BUY" else "🔴"
    arrow = "⬆️" if signal["direction"] == "BUY" else "⬇️"
    return (
        f"{emoji} <b>QUICK SWING — {name}</b> {arrow}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📍 Direction : <b>{signal['direction']}</b>\n"
        f"💵 Entry     : <b>{signal['entry']}</b>\n"
        f"🛑 Stop Loss : <b>{signal['sl']}</b>\n"
        f"🎯 Take Profit: <b>{signal['tp']}</b>\n"
        f"⚖️  R:R       : <b>1 : {signal['rr']}</b>\n"
        f"📊 RSI       : {signal['rsi']}\n"
        f"💪 Candle    : {signal['candle_strength']}% body\n"
        f"🕐 Session   : {session}\n"
        f"⏱️  Timeframe : 15m Quick Swing\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ <i>Not financial advice. Manage your risk.</i>"
    )


# ─────────────────────────────────────────────
# MAIN SCAN
# ─────────────────────────────────────────────

# Global store so the dashboard can read latest signals
latest_signals: dict = {}


def run_scan() -> list[dict]:
    """Scan all instruments and return list of active signals."""
    session  = get_active_session()
    found    = []
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    print(f"\n{'='*50}")
    print(f"  Quick Swing Scan — {timestamp}")
    print(f"  Session: {session}")
    print(f"{'='*50}")

    for name, symbol in INSTRUMENTS.items():
        print(f"\n  Scanning {name} ({symbol})...")
        df = fetch_data(symbol, interval="15m")
        if df is None:
            print(f"  ❌ No data for {name}")
            continue

        signal = detect_signal(df)

        if signal:
            signal["instrument"] = name
            signal["symbol"]     = symbol
            signal["session"]    = session
            signal["timestamp"]  = timestamp

            print(f"  ✅ SIGNAL: {signal['direction']} | Entry={signal['entry']} | R:R={signal['rr']}")

            alert_text = format_alert(name, signal, session)
            send_telegram(alert_text)
            found.append(signal)
            latest_signals[name] = signal
        else:
            print(f"  ⏭️  No signal for {name}")
            latest_signals[name] = None

    if not found:
        print("\n  📭 No signals this scan.")

    return found


# ─────────────────────────────────────────────
# STANDALONE RUN (for testing)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    results = run_scan()
    print(f"\n  Total signals found: {len(results)}")
