"""Uvicorn entry point for VModule backend."""

import sys
import uvicorn
from app.config import settings

if __name__ == "__main__":
    # In frozen (PyInstaller) mode: disable reload, use direct app object
    if getattr(sys, 'frozen', False):
        from app.main import app
        uvicorn.run(
            app,
            host=settings.HOST,
            port=settings.PORT,
            reload=False,
        )
    else:
        uvicorn.run(
            "app.main:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=settings.DEBUG,
            reload_dirs=["app"] if settings.DEBUG else None,
        )
