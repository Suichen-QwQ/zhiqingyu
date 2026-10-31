@echo off
chcp 65001 >nul
cd /d "%~dp0..\prototype-backend"
echo.
echo   ZhiQingYu prototype backend - environment setup
echo.
python --version
if errorlevel 1 (
    echo   ERROR: Python not found. Install Python 3.11+ first.
    pause
    exit /b 1
)
if not exist "venv" (
    echo   Creating virtualenv...
    python -m venv venv
)
call venv\Scripts\activate.bat
echo   Upgrading pip...
python -m pip install --upgrade pip
echo   Installing requirements...
pip install -r requirements.txt
echo.
echo   Done. Start it with: scripts\start-backend.bat
pause
