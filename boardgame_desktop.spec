# PyInstaller spec for Board Generator Studio — Desktop (CustomTkinter) app.
# Run from project root: pyinstaller boardgame_desktop.spec
# Optional: --windowed to hide console; add --onefile for a single exe.

from PyInstaller.utils.hooks import collect_all

# CustomTkinter needs its themes and assets at runtime.
ctk_datas, ctk_binaries, ctk_hiddenimports = collect_all("customtkinter")

a = Analysis(
    ["board_generator.py"],
    pathex=[],
    binaries=ctk_binaries,
    datas=ctk_datas,
    hiddenimports=ctk_hiddenimports,
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
    name="BoardGeneratorStudio-Desktop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Set to False for --windowed (no console)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="BoardGeneratorStudio-Desktop",
)
