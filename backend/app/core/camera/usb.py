"""USB 相机驱动 (基于 OpenCV)"""
import asyncio
import logging
from typing import Optional, Dict, Any
import numpy as np
import cv2

from app.core.camera.base import CameraBase

logger = logging.getLogger("vmodule.camera.usb")


class USBCamera(CameraBase):
    """USB 相机驱动，使用 OpenCV 实现"""

    # 按优先级尝试的后端列表
    _BACKENDS = [
        (cv2.CAP_DSHOW, "DSHOW"),
        (cv2.CAP_MSMF, "MSMF"),
        (cv2.CAP_ANY, "AUTO"),
    ]

    def __init__(self, camera_id: str, config: Dict[str, Any]):
        super().__init__(camera_id, config)
        self._cap: Optional[cv2.VideoCapture] = None
        self._device_index = config.get("connection", {}).get("index", 0)
        self._width = config.get("connection", {}).get("width", 1920)
        self._height = config.get("connection", {}).get("height", 1080)
        self._backend_name = ""

    async def open(self) -> bool:
        """打开相机，自动尝试多种后端"""
        for backend, name in self._BACKENDS:
            try:
                cap = cv2.VideoCapture(self._device_index, backend)
                if cap.isOpened():
                    # 验证能否实际读帧
                    ret, _ = cap.read()
                    if ret:
                        self._cap = cap
                        self._backend_name = name
                        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
                        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
                        self._is_open = True
                        logger.info(f"USB 相机已打开: {self.camera_id} (索引={self._device_index}, 后端={name})")
                        return True
                    else:
                        cap.release()
                        logger.debug(f"USB 相机 {self.camera_id}: {name} 后端打开成功但无法读帧，尝试下一个")
                else:
                    cap.release()
                    logger.debug(f"USB 相机 {self.camera_id}: {name} 后端无法打开索引 {self._device_index}")
            except Exception as e:
                logger.debug(f"USB 相机 {self.camera_id}: {name} 后端异常: {e}")

        logger.error(f"无法打开 USB 相机: {self.camera_id} (索引={self._device_index}, 所有后端均失败)")
        return False

    async def close(self) -> None:
        """关闭相机"""
        if self._cap:
            self._cap.release()
            self._cap = None
        self._is_open = False
        logger.info(f"USB 相机已关闭: {self.camera_id}")

    async def capture(self) -> Optional[np.ndarray]:
        """采集一帧图像"""
        if not self._is_open or not self._cap:
            return None

        try:
            ret, frame = self._cap.read()
            if ret:
                return frame
            else:
                logger.warning(f"USB 相机采集失败: {self.camera_id}")
                return None
        except Exception as e:
            logger.error(f"USB 相机采集异常: {e}")
            return None

    async def set_exposure(self, value: int) -> bool:
        """设置曝光时间"""
        if not self._cap:
            return False
        try:
            self._cap.set(cv2.CAP_PROP_EXPOSURE, value / 1000)  # 转换为毫秒
            self._exposure = value
            return True
        except Exception as e:
            logger.error(f"设置曝光失败: {e}")
            return False

    async def set_gain(self, value: float) -> bool:
        """设置增益"""
        if not self._cap:
            return False
        try:
            self._cap.set(cv2.CAP_PROP_GAIN, value)
            self._gain = value
            return True
        except Exception as e:
            logger.error(f"设置增益失败: {e}")
            return False

    def get_info(self) -> Dict[str, Any]:
        """获取相机信息"""
        info = {
            "camera_id": self.camera_id,
            "name": self.config.get("name", ""),
            "type": "usb",
            "device_index": self._device_index,
            "backend": self._backend_name,
            "is_open": self._is_open,
            "enabled": self.config.get("enabled", True),
            "exposure": self._exposure,
            "exposures": self.config.get("exposures") or [],
            "gain": self._gain,
        }
        if self._cap and self._is_open:
            info["width"] = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            info["height"] = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            info["fps"] = self._cap.get(cv2.CAP_PROP_FPS)
        return info
