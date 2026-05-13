"""Generic communication device manager."""
from __future__ import annotations
import asyncio
from typing import Optional, Type

from app.core.device.base import DeviceBase
from app.core.device.tcp import TCPDevice, TCPServer
from app.core.device.serial import SerialDevice
from app.utils.logger import logger


class DeviceManager:
    DEVICE_TYPES: dict[str, Type[DeviceBase]] = {
        "tcp": TCPDevice,
        "tcp_server": TCPServer,
        "serial": SerialDevice,
    }

    def __init__(self):
        self._devices: dict[str, DeviceBase] = {}
        self._lock = asyncio.Lock()

    async def add_device(self, device_id: str, device_type: str, config: dict) -> bool:
        async with self._lock:
            if device_id in self._devices:
                return False
            device_class = self.DEVICE_TYPES.get(device_type)
            if not device_class:
                logger.error(f"Unknown device type: {device_type}")
                return False
            full_config = {**config, "type": device_type}
            self._devices[device_id] = device_class(device_id, full_config)
            return True

    async def remove_device(self, device_id: str) -> bool:
        async with self._lock:
            device = self._devices.pop(device_id, None)
            if not device:
                return False
            if device.is_connected:
                await device.disconnect()
            return True

    async def update_device(self, device_id: str, device_type: str, config: dict) -> bool:
        await self.remove_device(device_id)
        return await self.add_device(device_id, device_type, config)

    async def connect_device(self, device_id: str) -> bool:
        device = self._devices.get(device_id)
        return await device.connect() if device else False

    async def disconnect_device(self, device_id: str) -> bool:
        device = self._devices.get(device_id)
        if not device:
            return False
        await device.disconnect()
        return True

    async def send(self, device_id: str, data: bytes) -> bool:
        device = self._devices.get(device_id)
        if not device:
            return False
        return await device.send(data)

    async def send_hex(self, device_id: str, hex_str: str) -> bool:
        try:
            data = bytes.fromhex(hex_str.replace(" ", ""))
        except ValueError:
            return False
        return await self.send(device_id, data)

    async def receive(self, device_id: str, timeout: float = 1.0) -> Optional[bytes]:
        device = self._devices.get(device_id)
        return await device.receive(timeout) if device else None

    def get_device(self, device_id: str) -> Optional[DeviceBase]:
        return self._devices.get(device_id)

    def get_all_devices(self) -> dict[str, DeviceBase]:
        return self._devices.copy()

    def get_device_info(self, device_id: str) -> Optional[dict]:
        device = self._devices.get(device_id)
        return device.get_info() if device else None

    def get_all_info(self) -> list:
        return [device.get_info() for device in self._devices.values()]

    async def disconnect_all(self):
        for device_id in list(self._devices):
            await self.disconnect_device(device_id)


device_manager = DeviceManager()
