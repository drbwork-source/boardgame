@echo off
setlocal
cd /d "%~dp0"

REM Optional version for output zip names (default 1.0.0)
set VERSION=%~1
if "%VERSION%"=="" set VERSION=1.0.0

echo Building Board Generator Studio release: %VERSION%
echo.

REM 1. Build web frontend (required for web executable)
echo [1/4] Building web frontend...
if not exist "web\package.json" (
    echo Error: web\package.json not found.
    exit /b 1
)
cd web
call npm run build 2>nul
if errorlevel 1 (
    echo Error: npm run build failed. Ensure Node.js and npm are installed.
    cd ..
    exit /b 1
)
cd ..
echo Done.
echo.

REM 2. Build desktop executable
echo [2/4] Building desktop executable...
py -m PyInstaller --noconfirm --clean boardgame_desktop.spec 2>nul
if errorlevel 1 python -m PyInstaller --noconfirm --clean boardgame_desktop.spec
if errorlevel 1 (
    echo Error: PyInstaller failed. Install with: pip install -r requirements-build.txt
    exit /b 1
)
echo Done.
echo.

REM 3. Build web executable
echo [3/4] Building web executable...
py -m PyInstaller --noconfirm --clean boardgame_web.spec 2>nul
if errorlevel 1 python -m PyInstaller --noconfirm --clean boardgame_web.spec
if errorlevel 1 (
    echo Error: PyInstaller failed for web build.
    exit /b 1
)
echo Done.
echo.

REM 4. Create versioned zip archives
echo [4/4] Creating zip archives...
set DESKTOP_DIR=dist\BoardGeneratorStudio-Desktop
set WEB_DIR=dist\BoardGeneratorStudio-Web
set DESKTOP_ZIP=dist\BoardGeneratorStudio-Desktop-%VERSION%.zip
set WEB_ZIP=dist\BoardGeneratorStudio-Web-%VERSION%.zip

if exist "%DESKTOP_DIR%" (
    powershell -NoProfile -Command "Compress-Archive -Path '%DESKTOP_DIR%' -DestinationPath '%DESKTOP_ZIP%' -Force"
    echo Created %DESKTOP_ZIP%
)
if exist "%WEB_DIR%" (
    powershell -NoProfile -Command "Compress-Archive -Path '%WEB_DIR%' -DestinationPath '%WEB_ZIP%' -Force"
    echo Created %WEB_ZIP%
)

echo.
echo Build complete. Output:
echo   - %DESKTOP_DIR%  (run BoardGeneratorStudio-Desktop.exe)
echo   - %WEB_DIR%  (run BoardGeneratorStudio-Web.exe, then open http://localhost:8000)
echo   - %DESKTOP_ZIP%
echo   - %WEB_ZIP%
echo.
echo Transfer a folder or zip to another device; no Python or Node.js required.
endlocal
