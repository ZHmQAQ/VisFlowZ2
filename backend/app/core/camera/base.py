"""相机抽象基类"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import numpy as np


class CameraBase(ABC):
    """相机抽象基类，所有相机驱动必须继承此类"""

    def __init__(self, camera_id: str, config: Dict[str, Any]):
        self.camera_id = camera_id
        self.config = config
        self._is_open = False
        self._exposure = config.get("exposure", 10000)
        self._gain = config.get("gain", 1.0)

    @property
    def is_open(self) -> bool:
        return self._is_open

    @abstractmethod
    async def open(self) -> bool:
        """打开相机"""
        pass

    @abstractmethod
    async def close(self) -> None:
        """关闭相机"""
        pass

    @abstractmethod
    async def capture(self) -> Optional[np.ndarray]:
        """采集一帧图像"""
        pass

    @abstractmethod
    async def set_exposure(self, value: int) -> bool:
        """设置曝光时间(微秒)"""
        pass

    @abstractmethod
    async def set_gain(self, value: float) -> bool:
        """设置增益"""
        pass

    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """获取相机信息"""
        pass

    def get_status(self) -> str:
        """获取相机状态"""
        return "online" if self._is_open else "offline"

    def on_shutdown(self) -> None:
        """程序关闭时的清理钩子，可被子类重写（如海康 SDK 全局清理）"""
        pass
