@echo off
REM ====================================================
REM  GoldScalperPro AI Agent v3 - One-Click Launcher
REM ====================================================

echo.
echo  ===============================================
echo    GoldScalperPro AI Agent - Starting...
echo  ===============================================
echo.

REM --- SETTINGS (edit these) ---
set ANTHROPIC_API_KEY=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
set ACCESS_PASSWORD=gold2024

REM Install dependencies
echo  Checking dependencies...
pip install --quiet anthropic flask yfinance >nul 2>&1

REM Open browser
start "" "http://localhost:5000"

echo.
echo  Agent running at: http://localhost:5000
echo  Login password  : %ACCESS_PASSWORD%
echo  Close this window to stop.
echo.
python gold_agent.py

pause
