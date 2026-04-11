# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


PROJECT_ROOT = Path(SPECPATH)
FRONTEND_DIST = PROJECT_ROOT / 'frontend' / 'dist'


def build_frontend_datas(frontend_dist: Path):
    if not frontend_dist.exists():
        return []

    datas = []
    for asset in frontend_dist.rglob('*'):
        if asset.is_file():
            target_dir = Path('frontend') / 'dist' / asset.relative_to(frontend_dist).parent
            datas.append((str(asset), target_dir.as_posix()))
    return datas


a = Analysis(
    ['run.py'],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=build_frontend_datas(FRONTEND_DIST),
    hiddenimports=[],
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
    name='dividend-cli',
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
