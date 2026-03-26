@echo off
cd /d "%~dp0"

REM Desktop app (CustomTkinter) — use this for the original desktop UI
py board_generator.py
if %errorlevel% neq 0 (
    python board_generator.py
)
if errorlevel 1 (
    echo.
    echo Python was not found. Install Python from https://www.python.org/downloads/
    echo and during setup check "Add Python to PATH", or install the Python Launcher for Windows.
    pause
)
