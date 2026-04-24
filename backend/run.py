"""Uvicorn entry point for VModule backend."""

import sys
import uvicorn
from app.config import settings

_ACCESS_FMT = '%(asctime)s | %(message)s'

if __name__ == "__main__":
    # In frozen (PyInstaller) mode: disable reload, use direct app object
    if getattr(sys, 'frozen', False):
        from app.main import app
        uvicorn.run(
            app,
            host=settings.HOST,
            port=settings.PORT,
            reload=False,
            access_log=True,
            log_config={
                "version": 1,
                "formatters": {"access": {"format": _ACCESS_FMT, "datefmt": "%Y-%m-%d %H:%M:%S"}},
                "handlers": {"access": {"class": "logging.StreamHandler", "formatter": "access", "stream": "ext://sys.stdout"}},
                "loggers": {"uvicorn.access": {"handlers": ["access"], "level": "INFO"}},
            },
        )
    else:
        uvicorn.run(
            "app.main:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=settings.DEBUG,
            reload_dirs=["app"] if settings.DEBUG else None,
            access_log=True,
            log_config={
                "version": 1,
                "formatters": {"access": {"format": _ACCESS_FMT, "datefmt": "%Y-%m-%d %H:%M:%S"}},
                "handlers": {"access": {"class": "logging.StreamHandler", "formatter": "access", "stream": "ext://sys.stdout"}},
                "loggers": {"uvicorn.access": {"handlers": ["access"], "level": "INFO"}},
            },
        )
