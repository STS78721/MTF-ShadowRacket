# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

ctk_datas, ctk_binaries, ctk_hiddenimports = collect_all('customtkinter')
dd_datas, dd_binaries, dd_hiddenimports = collect_all('darkdetect')

datas = [('C:/DK-Bananza-Instalador/payload', 'payload')] + ctk_datas + dd_datas
binaries = ctk_binaries + dd_binaries
hiddenimports = ['zstandard', 'installer.extract_nup', 'customtkinter', 'darkdetect', 'tkinter', 'PIL', 'PIL.Image'] + ctk_hiddenimports + dd_hiddenimports

a = Analysis(
    ['installer/modern_gui.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Donkey-Kong-Bananza-Setup',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['runtime/dkb.ico'],
)
