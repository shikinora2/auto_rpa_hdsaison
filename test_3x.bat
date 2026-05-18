@echo off
chcp 65001 >nul
setlocal

title automation marketing - Test x3

set ROOT=%~dp0
set LOOP=1

:run_loop
if %LOOP% GTR 3 goto done

echo.
echo ============================================================
echo   TEST RUN %LOOP% / 3
echo ============================================================
echo.

call "%ROOT%test.bat"
if errorlevel 1 (
    echo.
    echo [FAIL] Test run %LOOP% failed.
    exit /b 1
)

set /a LOOP=%LOOP%+1
goto run_loop

:done

echo.
echo ============================================================
echo   [PASS] All 3 test runs passed.
echo ============================================================
exit /b 0
