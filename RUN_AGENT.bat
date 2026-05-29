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

REM ── Start agent, then open browser after it's ready ───
echo  Starting agent...
start /b "" python gold_agent.py

echo  Waiting for server to start...
timeout /t 10 /nobreak >nul

echo  Opening browser...
start "" "http://localhost:5000"

REM If browser shows error, wait 5 more seconds and try again
timeout /t 5 /nobreak >nul
start "" "http://localhost:5000"

REM ── Find this PC's WiFi address for phone access ───
set PHONE_IP=
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    set IPLINE=%%a
    call :trim
)
goto :showinfo

:trim
set IPLINE=%IPLINE: =%
echo %IPLINE% | findstr /b "192.168 10. 172." >nul && set PHONE_IP=%IPLINE%
goto :eof

:showinfo
echo.
echo  ==============================================
echo    AGENT IS RUNNING
echo  ==============================================
echo.
echo   On THIS computer:  http://localhost:5000
if defined PHONE_IP (
echo.
echo   On your PHONE ^(same WiFi^), open this in the browser:
echo.
echo        http://%PHONE_IP%:5000
echo.
)
echo  ----------------------------------------------
echo  DO NOT close this window while using the agent.
echo  To stop: close this window.
echo  ==============================================
echo.

REM Keep window open
:loop
timeout /t 60 /nobreak >nul
goto loop
