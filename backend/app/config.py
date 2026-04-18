import sys
from pathlib import Path
from pydantic_settings import BaseSettings


def _get_base_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


class Settings(BaseSettings):
    APP_NAME: str = "VModule"
    APP_VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8100  # Different from VisFlowZ's 8000
    DEBUG: bool = True
    BASE_DIR: Path = _get_base_dir()
    DATA_DIR: Path = BASE_DIR / "data"
    WEIGHTS_DIR: Path = DATA_DIR / "weights"
    DATABASE_URL: str = "sqlite+aiosqlite:///./vmodule.db"
    # PLC defaults
    DEFAULT_SCAN_CYCLE_MS: int = 20
    DEFAULT_MODBUS_TIMEOUT: float = 1.0

    class Config:
        env_prefix = "VMODULE_"


settings = Settings()
