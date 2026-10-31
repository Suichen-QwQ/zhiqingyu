@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo.
echo   ZhiQingYu local preview (real model)
echo.
echo   First run creates backend-live\.env.local - put your DEEPSEEK_API_KEY there.
echo   Stop: Ctrl+C
echo.
python local-run.py %*
if errorlevel 1 pause
