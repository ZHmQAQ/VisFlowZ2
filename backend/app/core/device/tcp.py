"""TCP client/server devices."""
from __future__ import annotations
import asyncio
from typing import Optional

from app.core.device.base import DeviceBase
from app.utils.logger import logger


class TCPDevice(DeviceBase):
    def __init__(self, device_id: str, config: dict):
        super().__init__(device_id, config)
        conn = config.get("connection", {})
        self._host = conn.get("host", "127.0.0.1")
        self._port = int(conn.get("port", 502))
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

    async def connect(self) -> bool:
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=float(self.config.get("timeout", 5.0)),
            )
            self._is_connected = True
            return True
        except Exception as e:
            logger.error(f"TCP device connect failed [{self.device_id}]: {e}")
            self._is_connected = False
            return False

    async def disconnect(self) -> None:
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
        self._reader = None
        self._writer = None
        self._is_connected = False

    async def send(self, data: bytes) -> bool:
        if not self._is_connected or not self._writer:
            return False
        try:
            self._writer.write(data)
            await self._writer.drain()
            return True
        except Exception as e:
            logger.error(f"TCP device send failed [{self.device_id}]: {e}")
            self._is_connected = False
            return False

    async def receive(self, timeout: float = 1.0) -> Optional[bytes]:
        if not self._is_connected or not self._reader:
            return None
        try:
            data = await asyncio.wait_for(self._reader.read(1024), timeout=timeout)
            return data or None
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"TCP device receive failed [{self.device_id}]: {e}")
            return None

    def get_info(self) -> dict:
        info = super().get_info()
        info.update({"type": "tcp", "host": self._host, "port": self._port})
        return info


class TCPServer(DeviceBase):
    def __init__(self, device_id: str, config: dict):
        super().__init__(device_id, config)
        conn = config.get("connection", {})
        self._host = conn.get("host", "0.0.0.0")
        self._port = int(conn.get("port", 502))
        self._server: Optional[asyncio.Server] = None
        self._clients: dict[str, tuple[asyncio.StreamReader, asyncio.StreamWriter]] = {}

    async def connect(self) -> bool:
        try:
            self._server = await asyncio.start_server(self._handle_client, self._host, self._port)
            self._is_connected = True
            return True
        except Exception as e:
            logger.error(f"TCP server start failed [{self.device_id}]: {e}")
            self._is_connected = False
            return False

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer = writer.get_extra_info("peername")
        client_id = f"{peer[0]}:{peer[1]}" if peer else str(id(writer))
        self._clients[client_id] = (reader, writer)
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                logger.debug(f"TCP server received [{self.device_id}] {client_id}: {data.hex()}")
        finally:
            self._clients.pop(client_id, None)
            writer.close()

    async def disconnect(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        for _, writer in list(self._clients.values()):
            writer.close()
        self._clients.clear()
        self._is_connected = False

    async def send(self, data: bytes) -> bool:
        ok = True
        for _, writer in list(self._clients.values()):
            try:
                writer.write(data)
                await writer.drain()
            except Exception:
                ok = False
        return ok

    async def receive(self, timeout: float = 1.0) -> Optional[bytes]:
        return None

    def get_info(self) -> dict:
        info = super().get_info()
        info.update({
            "type": "tcp_server",
            "host": self._host,
            "port": self._port,
            "clients": list(self._clients.keys()),
        })
        return info
