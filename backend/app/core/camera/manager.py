"""相机管理器"""
import asyncio
import logging
from typing import Dict, Optional, Type
import numpy as np

from app.core.camera.base import CameraBase
from app.core.camera.usb import USBCamera
from app.core.camera.rtsp import RTSPCamera
from app.core.camera.daheng import DahengCamera
from app.core.camera.hikvision import HikvisionCamera

logger = logging.getLogger("vmodule.camera.manager")


class CameraManager:
    """相机管理器，统一管理所有相机实例"""

    # 相机类型注册表
    CAMERA_TYPES: Dict[str, Type[CameraBase]] = {
        "usb": USBCamera,
        "rtsp": RTSPCamera,
        "daheng": DahengCamera,
        "hikvision": HikvisionCamera,
    }

    def __init__(self):
        self._cameras: Dict[str, CameraBase] = {}
        self._lock = asyncio.Lock()

    def register_type(self, type_name: str, camera_class: Type[CameraBase]):
        """注册新的相机类型"""
        self.CAMERA_TYPES[type_name] = camera_class
        logger.info(f"注册相机类型: {type_name}")

    async def add_camera(self, camera_id: str, camera_type: str, config: dict) -> bool:
        """添加相机"""
        async with self._lock:
            if camera_id in self._cameras:
                logger.warning(f"相机已存在: {camera_id}")
                return False

            if camera_type not in self.CAMERA_TYPES:
                logger.error(f"未知相机类型: {camera_type}")
                return False

            camera_class = self.CAMERA_TYPES[camera_type]
            camera = camera_class(camera_id, config)
            self._cameras[camera_id] = camera
            logger.info(f"添加相机: {camera_id}, 类型: {camera_type}")
            return True

    async def remove_camera(self, camera_id: str) -> bool:
        """移除相机"""
        async with self._lock:
            if camera_id not in self._cameras:
                return False

            camera = self._cameras[camera_id]
            if camera.is_open:
                await camera.close()

            del self._cameras[camera_id]
            logger.info(f"移除相机: {camera_id}")
            return True

    async def open_camera(self, camera_id: str) -> bool:
        """打开相机"""
        camera = self._cameras.get(camera_id)
        if not camera:
            logger.error(f"相机不存在: {camera_id}")
            return False
        return await camera.open()

    async def close_camera(self, camera_id: str) -> bool:
        """关闭相机"""
        camera = self._cameras.get(camera_id)
        if not camera:
            return False
        await camera.close()
        return True

    async def capture(self, camera_id: str) -> Optional[np.ndarray]:
        """从指定相机采集图像"""
        camera = self._cameras.get(camera_id)
        if not camera or not camera.is_open:
            return None
        return await camera.capture()

    async def capture_with_exposures(self, camera_id: str, exposures: list) -> list:
        """使用多个曝光值采集多张图像"""
        camera = self._cameras.get(camera_id)
        if not camera or not camera.is_open:
            return []

        images = []
        for exp in exposures:
            await camera.set_exposure(exp)
            await asyncio.sleep(0.05)  # 等待曝光生效
            img = await camera.capture()
            if img is not None:
                images.append({"exposure": exp, "image": img})
        return images

    def get_camera(self, camera_id: str) -> Optional[CameraBase]:
        """获取相机实例"""
        return self._cameras.get(camera_id)

    def get_all_cameras(self) -> Dict[str, CameraBase]:
        """获取所有相机"""
        return self._cameras.copy()

    def get_camera_info(self, camera_id: str) -> Optional[dict]:
        """获取相机信息"""
        camera = self._cameras.get(camera_id)
        if not camera:
            return None
        return camera.get_info()

    def get_all_info(self) -> list:
        """获取所有相机信息"""
        return [cam.get_info() for cam in self._cameras.values()]

    async def close_all(self):
        """关闭所有相机"""
        # 先调各相机的关闭钩子（如海康 SDK 全局清理）
        for camera in list(self._cameras.values()):
            camera.on_shutdown()
        # 再关闭并移除所有相机
        for camera_id in list(self._cameras.keys()):
            await self.close_camera(camera_id)
        logger.info("所有相机已关闭")


# 全局单例
camera_manager = CameraManager()
