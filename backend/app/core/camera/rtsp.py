"""RTSP/网络相机驱动"""
import asyncio
import logging
from typing import Optional, Dict, Any
import numpy as np
import cv2

from app.core.camera.base import CameraBase

logger = logging.getLogger("vmodule.camera.rtsp")


class RTSPCamera(CameraBase):
    """RTSP 网络相机驱动"""

    def __init__(self, camera_id: str, config: Dict[str, Any]):
        super().__init__(camera_id, config)
        self._cap: Optional[cv2.VideoCapture] = None
        self._url = config.get("connection", {}).get("url", "")

    async def open(self) -> bool:
        """打开相机"""
        try:
            if not self._url:
                logger.error(f"RTSP URL 未配置: {self.camera_id}")
                return False

            self._cap = cv2.VideoCapture(self._url)
            if not self._cap.isOpened():
                logger.error(f"无法连接 RTSP 相机: {self.camera_id}")
                return False

            self._is_open = True
            logger.info(f"RTSP 相机已连接: {self.camera_id}")
            return True
        except Exception as e:
            logger.error(f"打开 RTSP 相机失败: {e}")
            return False

    async def close(self) -> None:
        """关闭相机"""
        if self._cap:
            self._cap.release()
            self._cap = None
        self._is_open = False
        logger.info(f"RTSP 相机已关闭: {self.camera_id}")

    async def capture(self) -> Optional[np.ndarray]:
        """采集一帧图像"""
        if not self._is_open or not self._cap:
            return None

        try:
            ret, frame = self._cap.read()
            if ret:
                return frame
            else:
                logger.warning(f"RTSP 相机采集失败: {self.camera_id}")
                return None
        except Exception as e:
            logger.error(f"RTSP 相机采集异常: {e}")
            return None

    async def set_exposure(self, value: int) -> bool:
        """RTSP 相机通常不支持远程设置曝光"""
        self._exposure = value
        logger.warning(f"RTSP 相机不支持设置曝光: {self.camera_id}")
        return False

    async def set_gain(self, value: float) -> bool:
        """RTSP 相机通常不支持远程设置增益"""
        self._gain = value
        logger.warning(f"RTSP 相机不支持设置增益: {self.camera_id}")
        return False

    def get_info(self) -> Dict[str, Any]:
        """获取相机信息"""
        info = {
            "camera_id": self.camera_id,
            "name": self.config.get("name", ""),
            "type": "rtsp",
            "url": self._url,
            "is_open": self._is_open,
            "enabled": self.config.get("enabled", True),
        }
        if self._cap and self._is_open:
            info["width"] = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            info["height"] = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            info["fps"] = self._cap.get(cv2.CAP_PROP_FPS)
        return info
