@echo off
title GoldScalperPro AI Agent
color 0A

echo.
echo  ==============================================
echo    GoldScalperPro AI Agent - Starting...
echo  ==============================================
echo.

REM ── Check Python is installed ──────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  !! Python is not installed on this computer.
    echo.
    echo  Please do the following:
    echo   1. A browser will open to the Python download page
    echo   2. Click the big yellow Download button
    echo   3. Run the installer
    echo   4. IMPORTANT: tick "Add Python to PATH" on the first screen
    echo   5. After installing, double-click this file again
    echo.
    pause
    start "" "https://www.python.org/downloads/"
    exit /b
)

echo  Python found. Good.
echo.

REM ── Settings ───────────────────────────────────
set ANTHROPIC_API_KEY=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
set ACCESS_PASSWORD=gold2024

REM ── Install required packages ───────────────────
echo  Installing packages (first run only, takes ~1 minute)...
pip install --quiet --upgrade anthropic flask yfinance requests
echo  Done.
echo.

REM ── Open browser and start ──────────────────────
echo  Opening browser...
start "" "http://localhost:5000"

echo  Agent is running at: http://localhost:5000
echo  Login password     : %ACCESS_PASSWORD%
echo.
echo  DO NOT close this window while using the agent.
echo  To stop: close this window.
echo.
python gold_agent.py

pause
