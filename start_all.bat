@echo off
title AI TradeBot - Launcher
echo.
echo  ========================================
echo   AI TradeBot - Starting All Services
echo  ========================================
echo.
echo [1] Starting Backend (Python)...
start "Backend" cmd /k "cd /d "%~dp0backend" && (if not exist venv python -m venv venv) && call venv\Scripts\activate && pip install -r requirements.txt --quiet && python main.py"

timeout /t 3 /nobreak >nul

echo [2] Starting Frontend (React)...
start "Frontend" cmd /k "cd /d "%~dp0frontend" && (if not exist node_modules npm install) && npm run dev"

timeout /t 4 /nobreak >nul

echo [3] Opening Dashboard...
start http://localhost:3000

echo.
echo  ========================================
echo   Both services started!
echo   Dashboard: http://localhost:3000
echo   API:       http://localhost:8000
echo  ========================================
pause
