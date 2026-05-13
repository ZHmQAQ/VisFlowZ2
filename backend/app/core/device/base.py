"""Generic communication device abstraction."""
from abc import ABC, abstractmethod
from typing import Any, Optional


class DeviceBase(ABC):
    def __init__(self, device_id: str, config: dict[str, Any]):
        self.device_id = device_id
        self.config = config
        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @abstractmethod
    async def connect(self) -> bool:
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        pass

    @abstractmethod
    async def send(self, data: bytes) -> bool:
        pass

    @abstractmethod
    async def receive(self, timeout: float = 1.0) -> Optional[bytes]:
        pass

    def get_info(self) -> dict:
        connection = self.config.get("connection", {})
        return {
            "device_id": self.device_id,
            "name": self.config.get("name", ""),
            "type": self.config.get("type", "unknown"),
            "protocol": self.config.get("protocol", "raw"),
            "enabled": self.config.get("enabled", True),
            "timeout": self.config.get("timeout", 5.0),
            "connection": connection,
            "host": connection.get("host", ""),
            "port": connection.get("port", ""),
            "baudrate": connection.get("baudrate", ""),
            "is_connected": self._is_connected,
        }
