# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['launcher\\MTFLauncher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('launcher\\assets\\mtf.ico', 'assets'),
        ('runtime\\mtf.png', 'assets'),
        ('runtime\\mtf_ball.png', 'assets'),
        ('VERSION', '.'),
        ('launcher\\mtf_version.txt', '.'),
        ('tools\\data\\expected-mtf111.json', 'tools\\data'),
    ],
    hiddenimports=['PIL._tkinter_finder'],
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
    name='MTFLauncher',
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
    icon=['launcher\\assets\\mtf.ico'],
)
