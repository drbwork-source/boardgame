@echo off
cd /d "%~dp0"
title Board Generator Studio - Web API
echo Checking dependencies (fastapi, uvicorn)...
py -m pip install -q -r requirements.txt 2>nul
if errorlevel 1 python -m pip install -q -r requirements.txt 2>nul
echo Starting Web API server...
echo.
py run_web.py 2>nul
if errorlevel 1 python run_web.py
echo.
echo Server stopped. Press any key to close.
pause >nul
