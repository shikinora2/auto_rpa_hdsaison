@echo off
chcp 65001 >nul
setlocal

title automation marketing - All-in-One Test

set ROOT=%~dp0
set PYTHON_EXE=%ROOT%.venv\Scripts\python.exe
set BACKEND_DIR=%ROOT%backend
set FRONTEND_DIR=%ROOT%frontend

echo.
echo ============================================================
echo   AUTOMATION MARKETING - ALL-IN-ONE TEST
echo ============================================================
echo.

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Không tìm thấy Python virtual environment tại:
    echo         %PYTHON_EXE%
    echo [HINT]  Hãy chạy dev.bat trước để tạo .venv hoặc tự tạo bằng:
    echo         python -m venv .venv
    exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Không tìm thấy Node.js trong PATH.
    exit /b 1
)

echo [1/3] Backend tests (pytest)...
pushd "%BACKEND_DIR%"
"%PYTHON_EXE%" -m pytest
if errorlevel 1 (
    popd
    echo [FAIL] Backend pytest thất bại.
    exit /b 1
)
popd

echo.
echo [2/3] Frontend lint...
pushd "%FRONTEND_DIR%"
call npm run lint
if errorlevel 1 (
    popd
    echo [FAIL] Frontend lint thất bại.
    exit /b 1
)

echo.
echo [3/3] Frontend build...
call npm run build
if errorlevel 1 (
    popd
    echo [FAIL] Frontend build thất bại.
    exit /b 1
)
popd

echo.
echo ============================================================
echo   [PASS] Tất cả kiểm tra đã thành công!
echo ============================================================
exit /b 0
