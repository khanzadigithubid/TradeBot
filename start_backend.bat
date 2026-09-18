@echo off
title AI TradeBot - Backend Server
color 0A
echo.
echo  ===================================
echo   AI TradeBot - Backend Starting...
echo  ===================================
echo.

cd /d "%~dp0backend"

:: Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo [*] Creating Python virtual environment...
    python -m venv venv
    echo [OK] Virtual environment created
)

:: Activate venv
call venv\Scripts\activate.bat

:: Install dependencies
echo [*] Installing dependencies...
pip install -r requirements.txt --quiet

echo.
echo [OK] Starting FastAPI server on http://localhost:8000
echo [OK] API Docs: http://localhost:8000/docs
echo [OK] WebSocket: ws://localhost:8000/ws
echo.
python main.py

pause
