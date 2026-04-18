"""海康工业相机驱动"""
import asyncio
import ctypes
import logging
import threading
import time
from typing import Optional, Dict, Any
import numpy as np

from app.core.camera.base import CameraBase

logger = logging.getLogger("vmodule.camera.hikvision")

# 海康 SDK 超时专用错误码（只是超时，不是真错误）
MV_E_TIMEOUT = -2147483638  # 0x8000000A

# 全局 SDK 初始化标志（确保只初始化一次）
_sdk_initialized = False
_sdk_init_lock = threading.Lock()


def _init_sdk():
    """全局初始化海康 SDK（多相机共用，只初始化一次）"""
    global _sdk_initialized
    with _sdk_init_lock:
        if not _sdk_initialized:
            try:
                from MvImport import MvCamera
                ret = MvCamera.MV_CC_Initialize()
                if ret != 0:
                    logger.error(f"海康 SDK 初始化失败, 错误码: 0x{ret:08X}")
                    return False
                logger.info("海康 SDK 全局初始化成功")
                _sdk_initialized = True
                return True
            except Exception as e:
                logger.error(f"海康 SDK 初始化异常: {e}")
                return False
        return True


def _finalize_sdk():
    """全局清理海康 SDK"""
    global _sdk_initialized
    with _sdk_init_lock:
        if _sdk_initialized:
            try:
                from MvImport import MvCamera
                MvCamera.MV_CC_Finalize()
                logger.info("海康 SDK 已全局清理")
            except Exception:
                pass
            _sdk_initialized = False


class HikvisionCamera(CameraBase):
    """海康工业相机驱动，使用 MVS SDK，按需触发采集"""

    def __init__(self, camera_id: str, config: Dict[str, Any]):
        super().__init__(camera_id, config)
        self._cam = None
        self._device_info = None
        self._ip_address = config.get("connection", {}).get("ip_address", "")
        self._serial_number = config.get("connection", {}).get("serial_number", "")
        self._trigger_mode = config.get("connection", {}).get("trigger_mode", "software")
        self._payload_size = 0
        self._width = 0
        self._height = 0
        self._pixel_type = None  # 当前像素格式

    async def open(self) -> bool:
        """打开相机"""
        # 全局初始化 SDK（多相机共用，只初始化一次）
        if not _init_sdk():
            return False

        try:
            from MvImport import MvCamera
            from MvImport import (
                MV_CC_DEVICE_INFO,
                MV_CC_DEVICE_INFO_LIST,
                MVCC_INTVALUE,
                MV_GIGE_DEVICE,
                MV_USB_DEVICE,
                MV_ACCESS_Exclusive,
                MV_ACCESS_ControlWithSwitch,
            )
            # 尝试导入排序枚举（部分 SDK 版本支持）
            try:
                from MvImport import SortMethod_SerialNumber
                _use_sorted_enum = True
            except ImportError:
                _use_sorted_enum = False
        except ImportError:
            logger.error(
                "未安装海康 MVS SDK Python 封装，无法使用海康相机。"
                "请确认: 1) 已安装 MVS 客户端 "
                "2) MvCameraControl_class.py 在 Python 路径中"
            )
            return False

        try:
            # 枚举设备（GigE + USB3），按序列号排序确保多相机时顺序固定
            device_list = MV_CC_DEVICE_INFO_LIST()
            if _use_sorted_enum:
                ret = MvCamera.MV_CC_EnumDevicesEx2(
                    MV_GIGE_DEVICE | MV_USB_DEVICE,
                    device_list,
                    "",
                    SortMethod_SerialNumber,
                )
            else:
                ret = MvCamera.MV_CC_EnumDevices(
                    MV_GIGE_DEVICE | MV_USB_DEVICE, device_list
                )
            if ret != 0:
                logger.error(f"海康相机枚举设备失败, 错误码: 0x{ret:08X}")
                return False

            if device_list.nDeviceNum == 0:
                logger.error(
                    "未找到海康相机设备，请检查: "
                    "1)相机是否通电连接 2)MVS SDK是否安装 3)网络/USB连接是否正常"
                )
                return False

            # 遍历设备列表，匹配目标
            target_index = None
            for i in range(device_list.nDeviceNum):
                dev_info = ctypes.cast(
                    device_list.pDeviceInfo[i],
                    ctypes.POINTER(MV_CC_DEVICE_INFO),
                ).contents
                dev_ip, dev_sn = self._extract_device_id(dev_info)
                logger.info(
                    f"发现海康相机 [{i + 1}/{device_list.nDeviceNum}]: "
                    f"IP={dev_ip}, SN={dev_sn}"
                )
                if self._ip_address and dev_ip == self._ip_address:
                    target_index = i
                    self._device_info = dev_info
                elif self._serial_number and dev_sn == self._serial_number:
                    target_index = i
                    self._device_info = dev_info

            if target_index is None:
                logger.error(
                    f"未在网络上找到匹配的相机，请检查配置: "
                    f"camera_id={self.camera_id}, "
                    f"IP={self._ip_address}, SN={self._serial_number}"
                )
                return False

            # 创建句柄并打开设备
            self._cam = MvCamera()
            ret = self._cam.MV_CC_CreateHandle(self._device_info)
            if ret != 0:
                logger.error(f"海康相机创建句柄失败, 错误码: 0x{ret:08X}")
                return False

            ret = self._cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
            if ret != 0:
                logger.warning(
                    f"独占模式打开失败, 错误码: 0x{ret:08X}, 尝试控制切换模式..."
                )
                ret = self._cam.MV_CC_OpenDevice(MV_ACCESS_ControlWithSwitch, 0)
                if ret != 0:
                    logger.error(
                        f"海康相机打开设备失败, 错误码: 0x{ret:08X}，"
                        f"可能正被其他程序占用，请关闭 MVS 客户端等程序后重试"
                    )
                    self._cam.MV_CC_DestroyHandle()
                    return False
                else:
                    logger.info("以控制切换模式打开设备（其他程序可能正在预览）")

            # GigE 相机：设置最佳包大小
            if self._device_info.nTLayerType == MV_GIGE_DEVICE:
                packet_size = self._cam.MV_CC_GetOptimalPacketSize()
                if packet_size > 0:
                    self._cam.MV_CC_SetIntValue("GevSCPSPacketSize", packet_size)

            # 设置触发模式（参考代码：AcquisitionMode=2 + TriggerMode=0 连续采集）
            self._cam.MV_CC_SetEnumValue("AcquisitionMode", 2)
            if self._trigger_mode == "software":
                self._cam.MV_CC_SetEnumValue("TriggerMode", 1)
                self._cam.MV_CC_SetEnumValue("TriggerSource", 7)
            else:
                self._cam.MV_CC_SetEnumValue("TriggerMode", 0)

            # 设置曝光和增益
            await self.set_exposure(self._exposure)
            await self.set_gain(self._gain)

            # 获取图像参数
            stParam = MVCC_INTVALUE()
            if self._cam.MV_CC_GetIntValue("PayloadSize", stParam) == 0:
                self._payload_size = stParam.nCurValue
            if self._cam.MV_CC_GetIntValue("Width", stParam) == 0:
                self._width = stParam.nCurValue
            if self._cam.MV_CC_GetIntValue("Height", stParam) == 0:
                self._height = stParam.nCurValue

            # 记录像素格式
            stPixelType = MVCC_INTVALUE()
            if self._cam.MV_CC_GetIntValue("PixelFormat", stPixelType) == 0:
                self._pixel_type = int(stPixelType.nCurValue)
                logger.info(f"像素格式: 0x{self._pixel_type:08X}")

            logger.info(
                f"相机已就绪: PayloadSize={self._payload_size}, "
                f"分辨率={self._width}x{self._height}, "
                f"触发模式={self._trigger_mode}"
            )
            self._is_open = True
            return True

        except Exception as e:
            logger.error(f"打开海康相机失败: {e}")
            return False

    async def close(self) -> None:
        """关闭相机"""
        try:
            if self._cam:
                self._cam.MV_CC_CloseDevice()
                self._cam.MV_CC_DestroyHandle()
                self._cam = None
            self._is_open = False
            self._device_info = None
            logger.info(f"海康相机已关闭: {self.camera_id}")
        except Exception as e:
            logger.error(f"关闭海康相机失败: {e}")

    def _raw_to_image(
        self, buf: ctypes.Array, width: int, height: int, pixel_type: int
    ) -> Optional[np.ndarray]:
        """将原始缓冲区数据转换为 numpy 图像（参考代码的 buffer_to_numpy 逻辑）"""
        try:
            import cv2

            # Mono8 (0x01080001)
            if pixel_type == 0x01080001:
                arr = np.frombuffer(buf, dtype=np.uint8, count=width * height)
                return arr.reshape((height, width))

            # RGB8 Packed (0x02180014)
            elif pixel_type == 0x02180014:
                arr = np.frombuffer(buf, dtype=np.uint8, count=width * height * 3)
                return arr.reshape((height, width, 3))

            # BayerRG8 (0x01080007) - 工业相机最常见格式
            elif pixel_type == 0x01080007:
                arr = np.frombuffer(buf, dtype=np.uint8, count=width * height)
                bayer = arr.reshape((height, width))
                return cv2.cvtColor(bayer, cv2.COLOR_BAYER_RG2BGR)

            # BayerGB8 (0x01080008)
            elif pixel_type == 0x01080008:
                arr = np.frombuffer(buf, dtype=np.uint8, count=width * height)
                bayer = arr.reshape((height, width))
                return cv2.cvtColor(bayer, cv2.COLOR_BAYER_GB2BGR)

            # BayerGR8 (0x01080009)
            elif pixel_type == 0x01080009:
                arr = np.frombuffer(buf, dtype=np.uint8, count=width * height)
                bayer = arr.reshape((height, width))
                return cv2.cvtColor(bayer, cv2.COLOR_BAYER_GR2BGR)

            # BayerBG8 (0x01080006)
            elif pixel_type == 0x01080006:
                arr = np.frombuffer(buf, dtype=np.uint8, count=width * height)
                bayer = arr.reshape((height, width))
                return cv2.cvtColor(bayer, cv2.COLOR_BAYER_BG2BGR)

            # 未知格式，尝试用 SDK 像素转换
            else:
                logger.warning(
                    f"未知像素格式: 0x{pixel_type:08X}，尝试 SDK 转换"
                )
                return self._convert_unknown(buf, width, height, pixel_type)

        except Exception as e:
            logger.error(f"图像转换失败: {e}")
            return None

    def _convert_unknown(
        self, buf, width: int, height: int, pixel_type: int
    ) -> Optional[np.ndarray]:
        """用 SDK 转换未知像素格式（备用）"""
        try:
            from MvImport import MV_CC_PIXEL_CONVERT_PARAM

            rgb_buf = (ctypes.c_ubyte * (width * height * 3))()
            param = MV_CC_PIXEL_CONVERT_PARAM()
            ctypes.memset(ctypes.byref(param), 0, ctypes.sizeof(param))
            param.nWidth = width
            param.nHeight = height
            param.pSrcData = ctypes.cast(buf, ctypes.c_void_p)
            param.nSrcDataLen = self._payload_size
            param.enSrcPixelType = pixel_type
            param.enDstPixelType = 0x02180014  # RGB8
            param.pDstBuffer = ctypes.cast(
                ctypes.addressof(rgb_buf), ctypes.c_void_p
            )
            param.nDstBufferSize = width * height * 3

            ret = self._cam.MV_CC_ConvertPixelType(param)
            if ret != 0:
                logger.error(f"像素格式转换失败: 0x{ret:08X}")
                return None

            return np.frombuffer(rgb_buf, dtype=np.uint8).reshape(
                (height, width, 3)
            )
        except Exception as e:
            logger.error(f"SDK 像素转换异常: {e}")
            return None

    async def capture(self) -> Optional[np.ndarray]:
        """采集一帧图像：发送触发 → 获取帧 → 返回图像"""
        if not self._is_open or not self._cam:
            return None

        try:
            from MvImport import MV_FRAME_OUT

            # 开始取流（相机可能已处于取流状态，重启无副作用）
            self._cam.MV_CC_StartGrabbing()

            # 软触发：发送触发命令
            if self._trigger_mode == "software":
                ret = self._cam.MV_CC_SetCommandValue("TriggerSoftware")
                if ret != 0:
                    logger.warning(f"软触发失败, 错误码: 0x{ret:08X}")

            # 获取图像
            stFrameInfo = MV_FRAME_OUT()
            ctypes.memset(ctypes.byref(stFrameInfo), 0, ctypes.sizeof(stFrameInfo))
            ret = self._cam.MV_CC_GetImageBuffer(stFrameInfo, 3000)
            if ret != 0:
                if ret != MV_E_TIMEOUT:
                    logger.warning(f"采集失败: 0x{ret:08X}")
                return None

            try:
                frame_info = stFrameInfo.stFrameInfo
                width = frame_info.nWidth
                height = frame_info.nHeight

                # enPixelType 可能是 ctypes 枚举、int 或 bytes，安全转换
                raw_pixel = frame_info.enPixelType
                if hasattr(raw_pixel, 'value'):
                    pixel_type = int(raw_pixel.value)
                elif isinstance(raw_pixel, bytes):
                    pixel_type = int.from_bytes(raw_pixel, byteorder='little')
                else:
                    pixel_type = int(raw_pixel)

                # pBufAddr 可能是 c_void_p(int)、c_char_p(bytes) 等，安全取地址
                raw_addr = stFrameInfo.pBufAddr
                if isinstance(raw_addr, bytes):
                    addr_int = int.from_bytes(raw_addr, byteorder='little')
                elif isinstance(raw_addr, int):
                    addr_int = raw_addr
                elif hasattr(raw_addr, 'value'):
                    addr_int = int(raw_addr.value) if raw_addr.value is not None else 0
                else:
                    addr_int = ctypes.cast(raw_addr, ctypes.c_void_p).value or 0

                # 安全检查
                if width <= 0 or height <= 0 or addr_int == 0:
                    logger.warning(f"帧尺寸无效 w={width} h={height} addr=0x{addr_int:X}")
                    return None

                buf = (ctypes.c_ubyte * self._payload_size).from_address(addr_int)
                img = self._raw_to_image(buf, width, height, pixel_type)
                return img

            finally:
                self._cam.MV_CC_FreeImageBuffer(stFrameInfo)

        except Exception as e:
            logger.error(f"采集异常: {e}")
            return None

    async def set_exposure(self, value: int) -> bool:
        """设置曝光时间(微秒)"""
        if not self._cam:
            return False
        try:
            ret = self._cam.MV_CC_SetFloatValue("ExposureTime", float(value))
            if ret != 0:
                logger.error(
                    f"海康相机设置曝光失败, 错误码: 0x{ret:08X}, 值: {value}"
                )
                return False
            self._exposure = value
            return True
        except Exception as e:
            logger.error(f"海康相机设置曝光异常: {e}")
            return False

    async def set_gain(self, value: float) -> bool:
        """设置增益"""
        if not self._cam:
            return False
        try:
            ret = self._cam.MV_CC_SetFloatValue("Gain", value)
            if ret != 0:
                logger.error(
                    f"海康相机设置增益失败, 错误码: 0x{ret:08X}, 值: {value}"
                )
                return False
            self._gain = value
            return True
        except Exception as e:
            logger.error(f"海康相机设置增益异常: {e}")
            return False

    def get_info(self) -> Dict[str, Any]:
        """获取相机信息"""
        info = {
            "camera_id": self.camera_id,
            "name": self.config.get("name", ""),
            "type": "hikvision",
            "ip_address": self._ip_address,
            "serial_number": self._serial_number,
            "is_open": self._is_open,
            "enabled": self.config.get("enabled", True),
            "exposure": self._exposure,
            "exposures": self.config.get("exposures") or [],
            "gain": self._gain,
            "trigger_mode": self._trigger_mode,
        }
        if self._is_open and self._width > 0:
            info["width"] = self._width
            info["height"] = self._height
        return info

    def on_shutdown(self) -> None:
        """程序结束时调用，全局清理海康 SDK"""
        _finalize_sdk()

    @staticmethod
    def _extract_device_id(dev_info) -> tuple:
        """从设备信息结构中提取 IP 和序列号"""
        dev_ip = ""
        dev_sn = ""
        try:
            # GigE 设备
            if dev_info.nTLayerType == 1:
                gige_info = dev_info.SpecialInfo.stGigEInfo
                ip_int = gige_info.nCurrentIp
                dev_ip = (
                    f"{(ip_int >> 24) & 0xFF}."
                    f"{(ip_int >> 16) & 0xFF}."
                    f"{(ip_int >> 8) & 0xFF}."
                    f"{ip_int & 0xFF}"
                )
                # 参考代码：直接用 bytes() 解析序列号，更可靠
                sn_bytes = bytes(gige_info.chSerialNumber)
                dev_sn = sn_bytes.split(b"\x00", 1)[0].decode("ascii", errors="ignore")
            # USB3 设备
            elif dev_info.nTLayerType == 4:
                usb_info = dev_info.SpecialInfo.stUsb3VInfo
                sn_bytes = bytes(usb_info.chSerialNumber)
                dev_sn = sn_bytes.split(b"\x00", 1)[0].decode("ascii", errors="ignore")
        except Exception:
            pass
        return dev_ip, dev_sn
