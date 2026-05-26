@echo off
REM ====================================================
REM  Gold Chart Analysis Agent - One-Click Launcher
REM  Just double-click this file to run the agent.
REM ====================================================

echo.
echo  ===============================================
echo    Gold Chart Analysis Agent - Starting...
echo  ===============================================
echo.

REM Set the API key
set ANTHROPIC_API_KEY=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

REM Install dependencies (silent if already installed)
echo  Checking dependencies...
pip install --quiet anthropic flask >nul 2>&1

REM Open the browser to the local URL
echo  Opening browser...
start "" "http://localhost:5000"

REM Run the agent
echo.
echo  Agent is running at: http://localhost:5000
echo  Close this window to stop the agent.
echo.
python gold_agent.py

pause
