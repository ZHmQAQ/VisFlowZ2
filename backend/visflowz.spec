# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for VModule/VisFlowZ Backend
Build: pyinstaller visflowz.spec
Output: dist/VisFlowZ-Backend/VisFlowZ-Backend.exe  (folder mode)
"""

import sys
from pathlib import Path

block_cipher = None
HERE = Path(SPECPATH)

a = Analysis(
    [str(HERE / 'run.py')],
    pathex=[str(HERE)],
    binaries=[],
    datas=[
        # Include frontend dist if present (for SPA serving)
        (str(HERE.parent / 'frontend' / 'dist'), 'frontend_dist'),
    ],
    hiddenimports=[
        # FastAPI / Uvicorn
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        # Pydantic
        'pydantic',
        'pydantic_settings',
        # SQLAlchemy
        'sqlalchemy',
        'sqlalchemy.ext.asyncio',
        'aiosqlite',
        # OpenCV
        'cv2',
        # NumPy
        'numpy',
        # PIL
        'PIL',
        # Torch & Ultralytics
        'torch',
        'torchvision',
        'ultralytics',
        # App modules
        'app',
        'app.main',
        'app.config',
        'app.api.plc',
        'app.api.detection',
        'app.api.camera',
        'app.api.model',
        'app.core.scanner.engine',
        'app.core.softdevice.memory',
        'app.core.softdevice.xinje',
        'app.core.softdevice.knowledge',
        'app.core.plc.modbus_client',
        'app.core.camera.base',
        'app.core.camera.manager',
        'app.core.camera.usb',
        'app.core.camera.rtsp',
        'app.core.camera.daheng',
        'app.core.camera.hikvision',
        'app.core.inference.base',
        'app.core.inference.manager',
        'app.core.inference.yolo',
        'app.core.detection.program_block',
        'app.core.detection.multiframe',
        # Misc
        'aiofiles',
        'multipart',
        'python_multipart',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'IPython',
        'jupyter',
        'notebook',
    ],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VisFlowZ-Backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=str(HERE.parent / 'frontend' / 'build' / 'icon.ico')
    if (HERE.parent / 'frontend' / 'build' / 'icon.ico').exists()
    else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VisFlowZ-Backend',
)
