# PyInstaller spec for VModule backend.
# Build from repository root with: build_backend_exe.bat

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"

datas = []
hiddenimports = [
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "aiosqlite",
    "pydantic",
    "pydantic_settings",
    "loguru",
    "cv2",
    "numpy",
    "PIL",
    "PIL.Image",
    "torch",
    "ultralytics",
    "aiofiles",
    "fitz",
]

for package in ("app", "ultralytics"):
    try:
        hiddenimports.extend(collect_submodules(package))
    except Exception:
        pass

for package in ("ultralytics", "cv2"):
    try:
        datas.extend(collect_data_files(package))
    except Exception:
        pass

if FRONTEND_DIST.exists():
    for path in FRONTEND_DIST.rglob("*"):
        if path.is_file():
            target_dir = Path("frontend_dist") / path.relative_to(FRONTEND_DIST).parent
            datas.append((str(path), str(target_dir)))


a = Analysis(
    ["run.py"],
    pathex=[str(BASE_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "setuptools", "distutils"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="VModule-Backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
