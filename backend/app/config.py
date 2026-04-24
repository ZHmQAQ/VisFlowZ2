import os
import sys
from pathlib import Path
from pydantic_settings import BaseSettings


def _get_base_dir() -> Path:
    """Return base directory: exe parent when frozen, else backend/ root."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _is_frozen() -> bool:
    return getattr(sys, 'frozen', False)


class Settings(BaseSettings):
    APP_NAME: str = "VModule"
    APP_VERSION: str = "3.1.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8100
    DEBUG: bool = not _is_frozen()
    BASE_DIR: Path = _get_base_dir()
    DATA_DIR: Path = Path(os.environ.get("VMODULE_DATA_DIR", str(BASE_DIR / "data")))
    WEIGHTS_DIR: Path = DATA_DIR / "weights"
    DATABASE_URL: str = f"sqlite+aiosqlite:///{DATA_DIR / 'vmodule.db'}"
    # Logging
    LOGS_DIR: Path = DATA_DIR / "logs"
    LOG_LEVEL: str = "INFO"
    LOG_RETENTION: str = "30 days"
    # Image storage
    SAVE_OK_IMAGES: bool = False
    SAVE_NG_IMAGES: bool = True
    # PLC defaults
    DEFAULT_SCAN_CYCLE_MS: int = 20
    DEFAULT_MODBUS_TIMEOUT: float = 1.0

    class Config:
        env_prefix = "VMODULE_"


settings = Settings()
