"""Serial communication device."""
from __future__ import annotations
from typing import Optional

from app.core.device.base import DeviceBase
from app.utils.logger import logger


class SerialDevice(DeviceBase):
    def __init__(self, device_id: str, config: dict):
        super().__init__(device_id, config)
        conn = config.get("connection", {})
        self._port = conn.get("port", "COM1")
        self._baudrate = int(conn.get("baudrate", 9600))
        self._bytesize = int(conn.get("bytesize", 8))
        self._parity = conn.get("parity", "N")
        self._stopbits = int(conn.get("stopbits", 1))
        self._serial = None

    async def connect(self) -> bool:
        try:
            import serial
            self._serial = serial.Serial(
                port=self._port,
                baudrate=self._baudrate,
                bytesize=self._bytesize,
                parity=self._parity,
                stopbits=self._stopbits,
                timeout=1,
            )
            self._is_connected = True
            return True
        except ImportError:
            logger.error("pyserial is not installed")
            return False
        except Exception as e:
            logger.error(f"Serial connect failed [{self.device_id}]: {e}")
            self._is_connected = False
            return False

    async def disconnect(self) -> None:
        if self._serial:
            self._serial.close()
            self._serial = None
        self._is_connected = False

    async def send(self, data: bytes) -> bool:
        if not self._is_connected or not self._serial:
            return False
        try:
            self._serial.write(data)
            return True
        except Exception as e:
            logger.error(f"Serial send failed [{self.device_id}]: {e}")
            return False

    async def receive(self, timeout: float = 1.0) -> Optional[bytes]:
        if not self._is_connected or not self._serial:
            return None
        try:
            self._serial.timeout = timeout
            data = self._serial.read(1024)
            return data or None
        except Exception as e:
            logger.error(f"Serial receive failed [{self.device_id}]: {e}")
            return None

    def get_info(self) -> dict:
        info = super().get_info()
        info.update({"type": "serial", "port": self._port, "baudrate": self._baudrate})
        return info
