@echo off
chcp 65001 >nul
title HD SAISON RPA - Dev Launcher
color 0A

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║       HD SAISON RPA Tool - Dev Launcher          ║
echo  ║       Backend: http://localhost:8000              ║
echo  ║       Frontend: http://localhost:5173             ║
echo  ╚══════════════════════════════════════════════════╝
echo.

set ROOT=%~dp0
set BACKEND_DIR=%ROOT%backend
set FRONTEND_DIR=%ROOT%frontend
set VENV_DIR=%ROOT%.venv

REM ── Kiểm tra Python ──────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Chưa cài Python hoặc Python chưa có trong PATH.
    pause & exit /b 1
)

REM ── Kiểm tra Node.js ─────────────────────────────────────────
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Chưa cài Node.js hoặc Node chưa có trong PATH.
    pause & exit /b 1
)

REM ── Tạo virtual env nếu chưa có ─────────────────────────────
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [SETUP] Tạo Python virtual environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Không thể tạo venv.
        pause & exit /b 1
    )
    echo [SETUP] Cài đặt Python dependencies...
    call "%VENV_DIR%\Scripts\activate.bat"
    pip install -r "%BACKEND_DIR%\requirements.txt" --quiet
    echo [SETUP] Cài đặt Playwright browsers...
    playwright install chromium --quiet
    echo [OK] Python environment sẵn sàng.
) else (
    echo [OK] Đã có Python virtual environment.
)

REM ── Cài npm packages nếu chưa có ────────────────────────────
if not exist "%FRONTEND_DIR%\node_modules" (
    echo [SETUP] Cài đặt Node.js packages (lần đầu)...
    pushd "%FRONTEND_DIR%"
    npm install --silent
    popd
    echo [OK] Node packages sẵn sàng.
) else (
    echo [OK] Đã có node_modules.
)

REM ── Khởi động Backend ────────────────────────────────────────
echo.
echo [START] Khởi động Backend server...
start "RPA_Backend" cmd /k "title RPA Backend ^& cd /d %BACKEND_DIR% ^& call %VENV_DIR%\Scripts\activate ^& python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

REM ── Chờ backend sẵn sàng (tối đa 20 giây) ──────────────────
echo [WAIT] Đang chờ Backend khởi động...
set /a count=0
:wait_backend
timeout /t 1 /nobreak >nul
curl -s http://localhost:8000/api/health >nul 2>&1
if not errorlevel 1 goto backend_ready
set /a count+=1
if %count% lss 20 goto wait_backend
echo [WARN] Backend chưa phản hồi sau 20s, vẫn tiếp tục...
:backend_ready
echo [OK] Backend đã sẵn sàng!

REM ── Khởi động Frontend ───────────────────────────────────────
echo [START] Khởi động Frontend (Vite)...
start "RPA_Frontend" cmd /k "title RPA Frontend ^& cd /d %FRONTEND_DIR% ^& npm run dev"

REM ── Chờ Frontend sẵn sàng rồi mở trình duyệt ───────────────
echo [WAIT] Đang chờ Frontend khởi động...
timeout /t 4 /nobreak >nul
set /a fcount=0
:wait_frontend
timeout /t 1 /nobreak >nul
curl -s http://localhost:5173 >nul 2>&1
if not errorlevel 1 goto frontend_ready
set /a fcount+=1
if %fcount% lss 15 goto wait_frontend
:frontend_ready
echo [OK] Frontend đã sẵn sàng!

REM ── Mở trình duyệt ───────────────────────────────────────────
echo [OPEN] Mở trình duyệt...
start http://localhost:5173

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║  ✓ Ứng dụng đang chạy!                          ║
echo  ║    Frontend : http://localhost:5173               ║
echo  ║    Backend  : http://localhost:8000               ║
echo  ║    API Docs : http://localhost:8000/docs          ║
echo  ║                                                   ║
echo  ║  Nhấn phím bất kỳ để DỪNG tất cả servers...     ║
echo  ╚══════════════════════════════════════════════════╝
echo.
pause >nul

REM ── Dừng tất cả servers ──────────────────────────────────────
echo [STOP] Đang dừng servers...
taskkill /FI "WINDOWTITLE eq RPA Backend*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq RPA Frontend*" /T /F >nul 2>&1
echo [DONE] Đã dừng tất cả.
timeout /t 2 /nobreak >nul
