import logging
import re
import sys
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.core.scanner.engine import ScanEngine, ScannerConfig
from app.core.softdevice.memory import SoftDeviceMemory
from app.core.detection.program_block import DetectionProgramBlock
from app.core.detection.multiframe import MultiFrameProgramBlock
from app.core.camera.manager import camera_manager
from app.core.inference.manager import inference_manager
from app.utils.logger import setup_logger, logger

settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)


# Keep the console focused on operator-relevant backend messages.
class _QuietAccessFilter(logging.Filter):
    """Suppress routine successful access logs and keep console output readable."""

    _STATUS_RE = re.compile(r'HTTP/\\d(?:\\.\\d)?\" (\\d{3})')

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        match = self._STATUS_RE.search(msg)
        if match and int(match.group(1)) < 400:
            return False
        return True


logging.getLogger("uvicorn.access").addFilter(_QuietAccessFilter())

# -- Global instances (populated during lifespan) --
scan_engine: ScanEngine | None = None
memory: SoftDeviceMemory | None = None
detection_block: DetectionProgramBlock | None = None
multiframe_block: MultiFrameProgramBlock | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scan_engine, memory, detection_block, multiframe_block

    # Setup logging
    settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    setup_logger()

    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Ensure data directories exist
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize database
    from app.db.database import init_db
    await init_db()

    # Initialize soft-device memory and scan engine
    memory = SoftDeviceMemory()
    scan_engine = ScanEngine(
        memory=memory,
        config=ScannerConfig(target_cycle_ms=settings.DEFAULT_SCAN_CYCLE_MS),
    )

    # Initialize detection program blocks
    detection_block = DetectionProgramBlock(camera_manager, inference_manager)
    scan_engine.add_program(detection_block)

    multiframe_block = MultiFrameProgramBlock(camera_manager, inference_manager)
    from app.api.model import get_strategy_map
    multiframe_block.set_strategy_getter(get_strategy_map)
    scan_engine.add_program(multiframe_block)

    # Register blocks with API
    from app.api.detection import set_detection_block, set_multiframe_block
    set_detection_block(detection_block)
    set_multiframe_block(multiframe_block)

    # Restore config from database
    from app.core.persistence import (
        restore_config, restore_runtime_settings, set_config_collector,
    )
    await restore_runtime_settings()
    saved = await restore_config()
    if saved:
        try:
            from app.api.plc import _do_load_preset
            await _do_load_preset(saved, scan_engine, detection_block, multiframe_block)
            logger.info("配置自动恢复完成")
        except Exception as e:
            logger.error(f"配置恢复失败: {e}")

    # Setup auto-save config collector
    async def _collect_config():
        from app.api.plc import _collect_current_preset
        return await _collect_current_preset(scan_engine, detection_block, multiframe_block)
    set_config_collector(_collect_config)

    await scan_engine.start()

    yield

    # Shutdown
    if scan_engine:
        await scan_engine.stop()
    await camera_manager.close_all()
    logger.info("VModule shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# -- CORS (allow all for development) --
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -- Health check --
@app.get("/health")
async def health():
    import platform
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "python": platform.python_version(),
        "scan_engine": scan_engine.get_status() if scan_engine else None,
    }


# -- API router placeholder --
from fastapi import APIRouter

api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def api_root():
    return {"message": f"{settings.APP_NAME} API"}


# -- Register sub-routers --
from app.api.plc import router as plc_router
from app.api.detection import router as detection_router
from app.api.camera import router as camera_router
from app.api.model import router as model_router
from app.api.system import router as system_router
from app.api.gpu import router as gpu_router
from app.api.config import router as config_router
from app.api.device import router as device_router
from app.api.event_action import router as event_action_router
from app.api.rule import router as rule_router

api_router.include_router(plc_router)
api_router.include_router(detection_router)
api_router.include_router(camera_router)
api_router.include_router(model_router)
api_router.include_router(system_router)
api_router.include_router(gpu_router)
api_router.include_router(config_router)
api_router.include_router(device_router)
api_router.include_router(event_action_router)
api_router.include_router(rule_router)

app.include_router(api_router)

# -- Static files from DATA_DIR --
app.mount("/data", StaticFiles(directory=str(settings.DATA_DIR)), name="data")

# -- SPA frontend serving --
# In frozen (PyInstaller) mode, frontend dist is bundled as 'frontend_dist'
if getattr(sys, 'frozen', False):
    _FRONTEND_DIR = Path(sys._MEIPASS) / "frontend_dist"
else:
    _FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
logger.info(f"Frontend dist path: {_FRONTEND_DIR} (exists={_FRONTEND_DIR.is_dir()})")
if _FRONTEND_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIR / "assets")), name="frontend-assets")

    @app.get("/")
    async def serve_index():
        return FileResponse(_FRONTEND_DIR / "index.html")

    @app.get("/{path:path}")
    async def spa_fallback(request: Request, path: str):
        file = _FRONTEND_DIR / path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(_FRONTEND_DIR / "index.html")
