@echo off
chcp 65001 >nul
cd /d "%~dp0..\prototype-backend"
echo.
echo   ZhiQingYu prototype backend - http://127.0.0.1:8000
echo   Stop: Ctrl+C
echo.
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo   WARNING: no venv found. Run scripts\setup-backend.bat first.
    pause
    exit /b 1
)
python -m app.main
pause
