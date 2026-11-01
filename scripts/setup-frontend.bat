@echo off
chcp 65001 >nul
cd /d "%~dp0..\prototype-frontend"
echo.
echo   ZhiQingYu prototype frontend - dependency setup
echo.
node --version
if errorlevel 1 (
    echo   ERROR: Node.js not found. Install Node.js 24+ first.
    pause
    exit /b 1
)
call pnpm --version
if errorlevel 1 (
    echo   Installing pnpm...
    call npm install -g pnpm
)
echo   Installing frontend dependencies...
call pnpm install --frozen-lockfile
if errorlevel 1 exit /b 1
if "%1"=="build" (
    echo   Building production bundle...
    call pnpm run build
    if errorlevel 1 exit /b 1
    echo   Build finished.
) else (
    echo.
    echo   Done. Start dev server with: scripts\start-frontend.bat
)
pause
