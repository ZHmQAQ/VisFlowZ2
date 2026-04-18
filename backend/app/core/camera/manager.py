"""相机管理器 — 虚拟相机 + 物理设备池"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, Type, Any
import numpy as np

from app.core.camera.base import CameraBase
from app.core.camera.usb import USBCamera
from app.core.camera.rtsp import RTSPCamera
from app.core.camera.daheng import DahengCamera
from app.core.camera.hikvision import HikvisionCamera

logger = logging.getLogger("vmodule.camera.manager")


@dataclass
class VirtualCamera:
    """虚拟相机：引用物理设备 + 独立拍照参数"""
    camera_id: str
    camera_type: str
    physical_key: str
    config: Dict[str, Any]
    exposure: int = 10000
    gain: float = 1.0


def _make_physical_key(camera_type: str, config: dict) -> str:
    """根据相机类型和配置生成物理设备唯一标识"""
    conn = config.get("connection", config)
    if camera_type == "daheng":
        sn = conn.get("serial_number", "")
        return f"daheng:{sn}" if sn else "daheng:auto"
    elif camera_type == "hikvision":
        sn = conn.get("serial_number", "")
        return f"hikvision:{sn}" if sn else "hikvision:auto"
    elif camera_type == "usb":
        idx = conn.get("index", conn.get("device_index", 0))
        return f"usb:{idx}"
    elif camera_type == "rtsp":
        url = conn.get("url", "")
        return f"rtsp:{url}"
    else:
        return f"{camera_type}:{id(config)}"


class CameraManager:
    """相机管理器，支持多个虚拟相机共享同一物理设备"""

    CAMERA_TYPES: Dict[str, Type[CameraBase]] = {
        "usb": USBCamera,
        "rtsp": RTSPCamera,
        "daheng": DahengCamera,
        "hikvision": HikvisionCamera,
    }

    def __init__(self):
        self._vcams: Dict[str, VirtualCamera] = {}           # 虚拟相机
        self._physical_devices: Dict[str, CameraBase] = {}   # 物理设备池
        self._physical_locks: Dict[str, asyncio.Lock] = {}   # 每物理设备一把锁
        self._physical_ref_count: Dict[str, int] = {}        # 引用计数
        self._lock = asyncio.Lock()

    def register_type(self, type_name: str, camera_class: Type[CameraBase]):
        """注册新的相机类型"""
        self.CAMERA_TYPES[type_name] = camera_class
        logger.info(f"注册相机类型: {type_name}")

    async def add_camera(self, camera_id: str, camera_type: str, config: dict) -> bool:
        """添加虚拟相机"""
        async with self._lock:
            if camera_id in self._vcams:
                logger.warning(f"相机已存在: {camera_id}")
                return False

            if camera_type not in self.CAMERA_TYPES:
                logger.error(f"未知相机类型: {camera_type}")
                return False

            physical_key = _make_physical_key(camera_type, config)

            # 物理设备不存在则创建
            if physical_key not in self._physical_devices:
                camera_class = self.CAMERA_TYPES[camera_type]
                device = camera_class(camera_id, config)
                self._physical_devices[physical_key] = device
                self._physical_locks[physical_key] = asyncio.Lock()
                self._physical_ref_count[physical_key] = 0

            self._physical_ref_count[physical_key] += 1

            vcam = VirtualCamera(
                camera_id=camera_id,
                camera_type=camera_type,
                physical_key=physical_key,
                config=config,
                exposure=config.get("exposure", 10000),
                gain=config.get("gain", 1.0),
            )
            self._vcams[camera_id] = vcam
            logger.info(f"添加虚拟相机: {camera_id}, 物理设备: {physical_key}")
            return True

    async def remove_camera(self, camera_id: str) -> bool:
        """移除虚拟相机"""
        async with self._lock:
            vcam = self._vcams.pop(camera_id, None)
            if not vcam:
                return False

            pk = vcam.physical_key
            self._physical_ref_count[pk] -= 1

            # 引用计数归零，关闭并移除物理设备
            if self._physical_ref_count[pk] <= 0:
                device = self._physical_devices.pop(pk, None)
                if device and device.is_open:
                    await device.close()
                self._physical_locks.pop(pk, None)
                self._physical_ref_count.pop(pk, None)
                logger.info(f"物理设备已关闭: {pk}")

            logger.info(f"移除虚拟相机: {camera_id}")
            return True

    async def open_camera(self, camera_id: str) -> bool:
        """打开虚拟相机（实际打开其物理设备）"""
        vcam = self._vcams.get(camera_id)
        if not vcam:
            logger.error(f"相机不存在: {camera_id}")
            return False

        device = self._physical_devices.get(vcam.physical_key)
        if not device:
            logger.error(f"物理设备不存在: {vcam.physical_key}")
            return False

        if device.is_open:
            return True
        return await device.open()

    async def close_camera(self, camera_id: str) -> bool:
        """关闭虚拟相机（仅当没有其他虚拟相机引用同一物理设备时才真正关闭）"""
        vcam = self._vcams.get(camera_id)
        if not vcam:
            return False

        pk = vcam.physical_key
        device = self._physical_devices.get(pk)
        if not device:
            return False

        # 检查是否还有其他虚拟相机在使用同一物理设备
        other_users = [v for v in self._vcams.values()
                       if v.physical_key == pk and v.camera_id != camera_id]
        if other_users:
            logger.info(f"物理设备 {pk} 仍有 {len(other_users)} 个虚拟相机在使用，不关闭")
            return True

        await device.close()
        return True

    async def capture(self, camera_id: str) -> Optional[np.ndarray]:
        """从虚拟相机采集图像（加锁 → 切参数 → 拍照）"""
        vcam = self._vcams.get(camera_id)
        if not vcam:
            return None

        device = self._physical_devices.get(vcam.physical_key)
        if not device or not device.is_open:
            return None

        lock = self._physical_locks.get(vcam.physical_key)
        if not lock:
            return None

        async with lock:
            # 切换到虚拟相机的参数
            await device.set_exposure(vcam.exposure)
            await device.set_gain(vcam.gain)
            await asyncio.sleep(0.02)  # 等待参数生效
            return await device.capture()

    async def capture_with_exposures(self, camera_id: str, exposures: list) -> list:
        """使用多个曝光值采集多张图像"""
        vcam = self._vcams.get(camera_id)
        if not vcam:
            return []

        device = self._physical_devices.get(vcam.physical_key)
        if not device or not device.is_open:
            return []

        lock = self._physical_locks.get(vcam.physical_key)
        if not lock:
            return []

        images = []
        async with lock:
            for exp in exposures:
                await device.set_exposure(exp)
                await asyncio.sleep(0.05)
                img = await device.capture()
                if img is not None:
                    images.append({"exposure": exp, "image": img})
        return images

    def get_camera(self, camera_id: str) -> Optional[CameraBase]:
        """获取物理设备实例（兼容旧调用）"""
        vcam = self._vcams.get(camera_id)
        if not vcam:
            return None
        return self._physical_devices.get(vcam.physical_key)

    def get_virtual_camera(self, camera_id: str) -> Optional[VirtualCamera]:
        """获取虚拟相机"""
        return self._vcams.get(camera_id)

    def get_all_cameras(self) -> Dict[str, VirtualCamera]:
        """获取所有虚拟相机"""
        return self._vcams.copy()

    def get_camera_info(self, camera_id: str) -> Optional[dict]:
        """获取虚拟相机信息"""
        vcam = self._vcams.get(camera_id)
        if not vcam:
            return None

        device = self._physical_devices.get(vcam.physical_key)
        info = {
            "camera_id": vcam.camera_id,
            "camera_type": vcam.camera_type,
            "physical_key": vcam.physical_key,
            "exposure": vcam.exposure,
            "gain": vcam.gain,
            "is_open": device.is_open if device else False,
            "config": vcam.config,
        }
        # 补充物理设备的额外信息
        if device:
            dev_info = device.get_info()
            for key in ("width", "height", "fps", "serial_number",
                        "device_index", "backend", "trigger_mode"):
                if key in dev_info:
                    info[key] = dev_info[key]
        return info

    def get_all_info(self) -> list:
        """获取所有虚拟相机信息"""
        return [self.get_camera_info(cid) for cid in self._vcams]

    async def close_all(self):
        """关闭所有物理设备"""
        for device in list(self._physical_devices.values()):
            device.on_shutdown()
        for device in list(self._physical_devices.values()):
            if device.is_open:
                await device.close()
        self._physical_devices.clear()
        self._physical_locks.clear()
        self._physical_ref_count.clear()
        self._vcams.clear()
        logger.info("所有相机已关闭")


# 全局单例
camera_manager = CameraManager()
