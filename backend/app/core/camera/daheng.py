"""大恒工业相机驱动"""
import asyncio
import logging
from typing import Optional, Dict, Any
import numpy as np

from app.core.camera.base import CameraBase

logger = logging.getLogger("vmodule.camera.daheng")


class DahengCamera(CameraBase):
    """大恒工业相机驱动，使用 Galaxy SDK"""

    def __init__(self, camera_id: str, config: Dict[str, Any]):
        super().__init__(camera_id, config)
        self._device = None
        self._device_manager = None
        self._serial_number = config.get("connection", {}).get("serial_number", "")
        self._trigger_mode = config.get("connection", {}).get("trigger_mode", "software")

    async def open(self) -> bool:
        """打开相机"""
        try:
            import gxipy as gx

            self._device_manager = gx.DeviceManager()
            dev_num, dev_info_list = self._device_manager.update_device_list()

            if dev_num == 0:
                logger.error("未找到大恒相机设备，请检查: 1)相机是否通电连接 2)SDK是否安装 3)驱动是否正常")
                return False

            # 列出所有可用相机
            available_sns = []
            for i, info in enumerate(dev_info_list):
                sn = info.get("sn", "未知")
                model = info.get("model_name", "未知")
                available_sns.append(sn)
                logger.info(f"发现大恒相机 [{i+1}/{dev_num}]: SN={sn}, 型号={model}")

            # 按序列号查找相机
            if self._serial_number:
                if self._serial_number not in available_sns:
                    logger.error(
                        f"未找到 SN={self._serial_number} 的大恒相机。"
                        f"可用设备: {available_sns}"
                    )
                    return False
                self._device = self._device_manager.open_device_by_sn(self._serial_number)
            else:
                logger.info(f"未指定序列号，按索引打开第1台相机 (SN={available_sns[0]})")
                self._device = self._device_manager.open_device_by_index(1)

            if not self._device:
                logger.error(f"无法打开大恒相机: {self.camera_id}")
                return False

            # 配置触发模式
            if self._trigger_mode == "software":
                self._device.TriggerMode.set(gx.GxSwitchEntry.ON)
                self._device.TriggerSource.set(gx.GxTriggerSourceEntry.SOFTWARE)
            else:
                self._device.TriggerMode.set(gx.GxSwitchEntry.OFF)

            # 设置曝光和增益
            await self.set_exposure(self._exposure)
            await self.set_gain(self._gain)

            # 开始采集
            self._device.stream_on()

            # 清空数据流缓冲区中的残留帧，避免首次采集拿到旧帧
            self._device.data_stream[0].flush_queue()

            self._is_open = True
            logger.info(f"大恒相机已打开: {self.camera_id}, SN: {self._serial_number}")
            return True

        except ImportError:
            logger.error("未安装 gxipy 库，无法使用大恒相机")
            return False
        except Exception as e:
            logger.error(f"打开大恒相机失败: {e}")
            return False

    async def close(self) -> None:
        """关闭相机"""
        try:
            if self._device:
                self._device.stream_off()
                self._device.close_device()
                self._device = None
            self._is_open = False
            logger.info(f"大恒相机已关闭: {self.camera_id}")
        except Exception as e:
            logger.error(f"关闭大恒相机失败: {e}")

    async def capture(self) -> Optional[np.ndarray]:
        """采集一帧图像"""
        if not self._is_open or not self._device:
            return None

        try:
            import gxipy as gx

            # 软触发: 先清空缓冲区，再发命令，确保 get_image 拿到的是本次触发的帧
            if self._trigger_mode == "software":
                self._device.data_stream[0].flush_queue()
                self._device.TriggerSoftware.send_command()

            # 获取图像
            raw_image = self._device.data_stream[0].get_image(timeout=1000)
            if raw_image is None:
                logger.warning(f"大恒相机采集超时: {self.camera_id}")
                return None

            # 转换为 numpy 数组
            if raw_image.get_status() == gx.GxFrameStatusList.INCOMPLETE:
                logger.warning(f"大恒相机图像不完整: {self.camera_id}")
                return None

            numpy_image = raw_image.get_numpy_array()
            if numpy_image is None:
                return None

            # 如果是彩色相机，进行颜色转换
            if len(numpy_image.shape) == 2:
                # Bayer 转 RGB
                rgb_image = raw_image.convert("RGB")
                if rgb_image:
                    numpy_image = rgb_image.get_numpy_array()

            return numpy_image

        except Exception as e:
            logger.error(f"大恒相机采集异常: {e}")
            return None

    async def set_exposure(self, value: int) -> bool:
        """设置曝光时间(微秒)"""
        if not self._device:
            return False
        try:
            self._device.ExposureTime.set(float(value))
            self._exposure = value
            # 曝光变更后清空缓冲区，避免下次采集拿到旧曝光的帧
            if self._is_open:
                self._device.data_stream[0].flush_queue()
            return True
        except Exception as e:
            logger.error(f"设置曝光失败: {e}")
            return False

    async def set_gain(self, value: float) -> bool:
        """设置增益"""
        if not self._device:
            return False
        try:
            self._device.Gain.set(value)
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
            "type": "daheng",
            "serial_number": self._serial_number,
            "is_open": self._is_open,
            "enabled": self.config.get("enabled", True),
            "exposure": self._exposure,
            "exposures": self.config.get("exposures") or [],
            "gain": self._gain,
            "trigger_mode": self._trigger_mode,
        }
        if self._device and self._is_open:
            try:
                info["width"] = self._device.Width.get()
                info["height"] = self._device.Height.get()
            except Exception as e:
                logger.warning(f"获取大恒相机分辨率失败: {e}")
        return info
