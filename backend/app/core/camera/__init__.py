"""相机模块"""
from app.core.camera.base import CameraBase
from app.core.camera.usb import USBCamera
from app.core.camera.rtsp import RTSPCamera
from app.core.camera.daheng import DahengCamera
from app.core.camera.hikvision import HikvisionCamera
from app.core.camera.manager import CameraManager, camera_manager

__all__ = [
    "CameraBase",
    "USBCamera",
    "RTSPCamera",
    "DahengCamera",
    "HikvisionCamera",
    "CameraManager",
    "camera_manager",
]
