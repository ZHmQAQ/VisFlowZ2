import logging
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
from app.core.camera.manager import camera_manager
from app.core.inference.manager import inference_manager

logger = logging.getLogger("vmodule")

# -- Global instances (populated during lifespan) --
scan_engine: ScanEngine | None = None
memory: SoftDeviceMemory | None = None
detection_block: DetectionProgramBlock | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scan_engine, memory, detection_block

    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Ensure data directories exist
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize soft-device memory and scan engine
    memory = SoftDeviceMemory()
    scan_engine = ScanEngine(
        memory=memory,
        config=ScannerConfig(target_cycle_ms=settings.DEFAULT_SCAN_CYCLE_MS),
    )

    # Initialize detection program block
    detection_block = DetectionProgramBlock(camera_manager, inference_manager)
    scan_engine.add_program(detection_block)

    # Register detection block with API
    from app.api.detection import set_detection_block
    set_detection_block(detection_block)

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
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
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

api_router.include_router(plc_router)
api_router.include_router(detection_router)

app.include_router(api_router)

# -- Static files from DATA_DIR --
app.mount("/data", StaticFiles(directory=str(settings.DATA_DIR)), name="data")

# -- SPA frontend serving --
_FRONTEND_DIR = Path(__file__).parent.parent.parent.parent / "frontend" / "dist"
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
