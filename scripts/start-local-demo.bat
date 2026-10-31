@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo.
echo   ZhiQingYu local preview (fake model: offline, free, no API key)
echo.
echo   Open in browser:  http://127.0.0.1:8092/
echo   Stop:             Ctrl+C
echo.
python local-run.py --demo %*
if errorlevel 1 pause
