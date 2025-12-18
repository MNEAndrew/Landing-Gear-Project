# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for building the gearrec CLI as a single-folder (onedir) app.
Outputs to dist/gearrec-<os>-<arch>/gearrec[.exe]
"""

import platform
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

_spec_file = Path(globals().get("__file__", Path.cwd() / "packaging/pyinstaller/gearrec.spec"))
project_root = _spec_file.resolve().parents[2] if _spec_file.exists() else Path.cwd()

datas = collect_data_files("gearrec", includes=["data/*.json"])
hiddenimports = collect_submodules("gearrec")

a = Analysis(
    [str(project_root / "gearrec" / "cli" / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="gearrec",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="gearrec",
)
