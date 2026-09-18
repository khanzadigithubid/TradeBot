@echo off
title AI TradeBot - Dashboard
color 0B
echo.
echo  ===================================
echo   AI TradeBot - Dashboard Starting...
echo  ===================================
echo.

cd /d "%~dp0frontend"

:: Check if node_modules exists
if not exist "node_modules" (
    echo [*] Installing npm packages...
    npm install
    echo [OK] Packages installed
)

echo.
echo [OK] Starting React dashboard on http://localhost:3000
echo.
npm run dev

pause
