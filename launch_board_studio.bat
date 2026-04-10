@echo off
cd /d "%~dp0"
echo Launching Board Generator Studio Web UI...

REM Web UI: start API server, then open browser

REM Build frontend if dist doesn't exist
if not exist "web\dist\index.html" (
    if exist "web\package.json" (
        echo Building web frontend...
        cd web
        call npm run build 2>nul
        cd ..
    )
)

REM Start server in its own window (no nested quotes)
start "Board Generator Studio - Web API" "%~dp0run_web_server.bat"

REM Wait for server to start
timeout /t 4 /nobreak >nul

REM Open browser
start "" "http://localhost:8000"

echo.
echo If the Web UI did not open, go to: http://localhost:8000
echo Close the server window to stop the API.
echo.
pause
