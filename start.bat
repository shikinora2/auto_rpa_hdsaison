@echo off
title automation marketing - Launcher
echo ============================================================
echo    automation marketing v2.0.0 - Web Edition
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if Node.js is installed
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is not installed or not in PATH
    pause
    exit /b 1
)

echo [INFO] Starting Backend server...
start "Backend Server" cmd /k "cd /d %~dp0 && call .venv\Scripts\activate && cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

echo [INFO] Waiting for Backend to start...
timeout /t 3 /nobreak >nul

echo [INFO] Starting Frontend server...
start "Frontend Server" cmd /k "cd /d %~dp0frontend && npm run dev"

echo [INFO] Waiting for Frontend to start...
timeout /t 5 /nobreak >nul

echo [INFO] Opening browser...
start http://localhost:5173

echo.
echo ============================================================
echo    Application is running!
echo    Backend:  http://localhost:8000
echo    Frontend: http://localhost:5173
echo    API Docs: http://localhost:8000/docs
echo ============================================================
echo.
echo Press any key to stop all servers...
pause >nul

echo [INFO] Stopping servers...
taskkill /FI "WINDOWTITLE eq Backend Server*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Frontend Server*" /T /F >nul 2>&1

echo [INFO] Done!
