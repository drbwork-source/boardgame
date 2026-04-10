# PyInstaller spec for Board Generator Studio — Web (API + built frontend) app.
# Build the frontend first: cd web && npm run build
# Then run from project root: pyinstaller boardgame_web.spec
# The exe starts the server and serves the SPA at http://localhost:8000

import os

# Include the built React app so the frozen exe can serve it (api/main.py uses sys._MEIPASS).
# If web/dist is missing, run: cd web && npm run build
web_dist = "web/dist"
if not os.path.isdir(web_dist):
    raise SystemExit(
        "web/dist not found. Build the frontend first: cd web && npm run build"
    )

added_datas = [(web_dist, "web/dist")]

a = Analysis(
    ["web_launcher.py"],
    pathex=[],
    binaries=[],
    datas=added_datas,
    hiddenimports=[
        "api.main",
        "api.routes.board",
        "api.routes.config",
        "api.schemas",
        "board_core",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BoardGeneratorStudio-Web",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="BoardGeneratorStudio-Web",
)
