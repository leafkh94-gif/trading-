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

REM ── Install required packages ───────────────────
echo  Installing packages (first run only, takes ~1 minute)...
pip install --quiet --upgrade anthropic flask yfinance requests
echo  Done.
echo.

REM ── Download the phone-link tool (first run only) ───
if not exist cloudflared.exe (
    echo  Downloading the phone-link tool (first run only)...
    powershell -Command "try { Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile 'cloudflared.exe' } catch { exit 1 }"
    if errorlevel 1 (
        echo  Could not download the phone-link tool. You can still use it on this PC.
    ) else (
        echo  Done.
    )
)
echo.

REM ── Start the agent in the background ───────────
echo  Starting agent...
start /b "" python gold_agent.py

echo  Waiting for server to start...
timeout /t 8 /nobreak >nul

REM ── Open it on this computer ────────────────────
start "" "http://localhost:5000"

echo.
echo  ==============================================
echo    AGENT IS RUNNING
echo  ==============================================
echo.
echo   On THIS computer:  http://localhost:5000
echo.

REM ── Create the public phone link ────────────────
if exist cloudflared.exe (
    echo   Creating your PHONE link... watch for the address below.
    echo   It looks like:  https://something.trycloudflare.com
    echo   Open THAT address on your phone (works anywhere, even mobile data).
    echo.
    echo  ==============================================
    echo.
    cloudflared.exe tunnel --url http://localhost:5000
) else (
    echo   DO NOT close this window while using the agent.
    echo   To stop: close this window.
    echo  ==============================================
    :loop
    timeout /t 60 /nobreak >nul
    goto loop
)
