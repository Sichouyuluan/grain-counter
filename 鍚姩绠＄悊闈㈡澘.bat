@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
echo.
echo ============================================
echo   Grain Counter - Server Management Panel
echo ============================================
echo.
python server_panel.py
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start. Make sure dependencies are installed:
    echo pip install -r requirements.txt
    pause
)
