# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['dividend_calculator/cli.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('dividend_calculator/*.py', 'dividend_calculator'),
    ],
    hiddenimports=[
        'click',
        'pandas',
        'tabulate',
        'tqdm',
        'requests',
        'sqlite3',
        'datetime',
        'bisect',
    ],
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
    [],
    exclude_binaries=True,
    name='dividend-cli',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='dividend-cli',
)
