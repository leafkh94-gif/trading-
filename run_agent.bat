@echo off
cd /d "%~dp0"
python gold_agent.py
if errorlevel 1 (
    echo.
    echo Agent failed. Press any key to exit.
    pause
) else (
    echo.
    echo Agent completed. Press any key to exit.
    pause
)
