@echo off
chcp 65001 >nul
cd /d "%~dp0..\prototype-frontend"
echo.
echo   ZhiQingYu prototype frontend - http://127.0.0.1:5525
echo   Stop: Ctrl+C
echo.
if not exist "node_modules" (
    echo   WARNING: node_modules missing. Run scripts\setup-frontend.bat first.
    pause
    exit /b 1
)
call pnpm run dev
pause
