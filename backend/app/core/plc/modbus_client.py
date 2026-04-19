"""
PLC 通信层 — Modbus TCP 主站

VModule 作为 Modbus TCP 主站，主动轮询 PLC（从站）。
这是 PLC 工程师最熟悉的模式——与 HMI/触摸屏访问 PLC 完全一致。

核心职责:
  1. 维护与一个或多个 PLC 的 TCP 连接
  2. 根据 I/O 映射表，周期性读取输入软元件 (EX/ED ← PLC)
  3. 根据 I/O 映射表，周期性写出输出软元件 (EY/EW → PLC)
  4. 将 Modbus 协议细节完全封装，上层只看到软元件读写

Modbus TCP 帧格式（参考 VisFlowZ 已验证的实现）:
  [TID 2B][PID 2B=0x0000][Len 2B][UID 1B][FC 1B][Data...]

支持的功能码:
  FC 0x01  读线圈          (EX ← PLC M/X/S...)
  FC 0x03  读保持寄存器     (ED ← PLC D/HD/TD...)
  FC 0x05  写单个线圈       (EY → PLC M/Y/S...)
  FC 0x06  写单个寄存器     (EW → PLC D/HD...)
  FC 0x0F  写多个线圈
  FC 0x10  写多个寄存器
"""

from __future__ import annotations
import asyncio
import struct
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import IntEnum

logger = logging.getLogger("vmodule.plc")


class ModbusFC(IntEnum):
    """Modbus 功能码"""
    READ_COILS = 0x01
    READ_DISCRETE_INPUTS = 0x02
    READ_HOLDING_REGISTERS = 0x03
    READ_INPUT_REGISTERS = 0x04
    WRITE_SINGLE_COIL = 0x05
    WRITE_SINGLE_REGISTER = 0x06
    WRITE_MULTIPLE_COILS = 0x0F
    WRITE_MULTIPLE_REGISTERS = 0x10


@dataclass
class PLCConnection:
    """PLC 连接配置"""
    name: str                # 连接名称 (如 "1号机PLC")
    host: str                # IP 地址
    port: int = 502          # Modbus TCP 端口
    unit_id: int = 1         # 从站地址
    timeout: float = 2.0     # 超时 (秒)
    retry_count: int = 3     # 重试次数
    retry_delay: float = 0.1 # 重试间隔 (秒)


class ModbusTCPClient:
    """Modbus TCP 客户端 — 异步实现

    封装 Modbus TCP 帧的构建、发送、解析。
    每个 PLCConnection 对应一个 client 实例。
    """

    def __init__(self, config: PLCConnection):
        self.config = config
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._tid: int = 0
        self._lock = asyncio.Lock()
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def _next_tid(self) -> int:
        self._tid = (self._tid + 1) & 0xFFFF
        return self._tid

    async def connect(self):
        """建立 TCP 连接并验证 Modbus 通信"""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.config.host, self.config.port),
                timeout=self.config.timeout,
            )
            self._connected = True
            # 发送一个测试读取来验证对端是合法的 Modbus 从站
            # 读保持寄存器 D0 (FC03, addr=0, count=1)
            test_pdu = struct.pack(">BHH", 0x03, 0x0000, 0x0001)
            try:
                await self._transact(test_pdu)
            except Exception as verify_err:
                self._connected = False
                if self._writer:
                    try:
                        self._writer.close()
                        await self._writer.wait_closed()
                    except Exception:
                        pass
                self._reader = None
                self._writer = None
                raise ConnectionError(
                    f"TCP 连接成功但 Modbus 验证失败 "
                    f"({self.config.host}:{self.config.port}): {verify_err}"
                )
            logger.info(
                f"[{self.config.name}] 已连接 "
                f"{self.config.host}:{self.config.port} "
                f"(站号={self.config.unit_id})"
            )
        except Exception as e:
            self._connected = False
            logger.error(f"[{self.config.name}] 连接失败: {e}")
            raise

    async def disconnect(self):
        """断开 TCP 连接"""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        self._connected = False
        self._reader = None
        self._writer = None
        logger.info(f"[{self.config.name}] 已断开")

    def _build_mbap(self, tid: int, pdu: bytes) -> bytes:
        """构建 MBAP 头 + PDU"""
        return struct.pack(
            ">HHHB",
            tid,                    # Transaction ID
            0x0000,                 # Protocol ID (Modbus)
            len(pdu) + 1,           # Length (UID + PDU)
            self.config.unit_id,    # Unit ID
        ) + pdu

    async def _transact(self, pdu: bytes) -> bytes:
        """发送请求并等待响应，返回响应 PDU（不含 MBAP 头）"""
        if not self._connected:
            raise ConnectionError(f"[{self.config.name}] 未连接")

        async with self._lock:
            tid = self._next_tid()
            frame = self._build_mbap(tid, pdu)

            for attempt in range(self.config.retry_count):
                try:
                    self._writer.write(frame)
                    await self._writer.drain()

                    # 读 MBAP 头 (7 bytes)
                    header = await asyncio.wait_for(
                        self._reader.readexactly(7),
                        timeout=self.config.timeout,
                    )
                    resp_tid, proto, length, unit = struct.unpack(">HHHB", header)

                    # 读 PDU
                    pdu_data = await asyncio.wait_for(
                        self._reader.readexactly(length - 1),
                        timeout=self.config.timeout,
                    )

                    # 检查错误响应
                    if pdu_data[0] & 0x80:
                        error_code = pdu_data[1] if len(pdu_data) > 1 else 0
                        raise ModbusError(pdu_data[0] & 0x7F, error_code)

                    return pdu_data

                except (asyncio.TimeoutError, ConnectionError, OSError) as e:
                    if attempt < self.config.retry_count - 1:
                        logger.warning(
                            f"[{self.config.name}] 通信重试 "
                            f"({attempt + 1}/{self.config.retry_count}): {e}"
                        )
                        await asyncio.sleep(self.config.retry_delay)
                    else:
                        self._connected = False
                        raise

    # ==================== 读操作 ====================

    async def read_coils(self, address: int, count: int) -> List[bool]:
        """FC 0x01 读线圈"""
        pdu = struct.pack(">BHH", ModbusFC.READ_COILS, address, count)
        resp = await self._transact(pdu)
        # resp: [FC][byte_count][data...]
        byte_count = resp[1]
        data_bytes = resp[2:2 + byte_count]
        bits = []
        for i in range(count):
            byte_idx, bit_idx = divmod(i, 8)
            bits.append(bool(data_bytes[byte_idx] & (1 << bit_idx)))
        return bits

    async def read_registers(self, address: int, count: int) -> List[int]:
        """FC 0x03 读保持寄存器"""
        pdu = struct.pack(">BHH", ModbusFC.READ_HOLDING_REGISTERS, address, count)
        resp = await self._transact(pdu)
        # resp: [FC][byte_count][data...]
        byte_count = resp[1]
        values = []
        for i in range(count):
            hi = resp[2 + i * 2]
            lo = resp[3 + i * 2]
            val = (hi << 8) | lo
            # 转有符号
            if val > 0x7FFF:
                val -= 0x10000
            values.append(val)
        return values

    # ==================== 写操作 ====================

    async def write_coil(self, address: int, value: bool):
        """FC 0x05 写单个线圈"""
        coil_value = 0xFF00 if value else 0x0000
        pdu = struct.pack(">BHH", ModbusFC.WRITE_SINGLE_COIL, address, coil_value)
        await self._transact(pdu)

    async def write_register(self, address: int, value: int):
        """FC 0x06 写单个寄存器"""
        value = int(value) & 0xFFFF
        pdu = struct.pack(">BHH", ModbusFC.WRITE_SINGLE_REGISTER, address, value)
        await self._transact(pdu)

    async def write_coils(self, address: int, values: List[bool]):
        """FC 0x0F 写多个线圈"""
        count = len(values)
        byte_count = (count + 7) // 8
        data = bytearray(byte_count)
        for i, v in enumerate(values):
            if v:
                byte_idx, bit_idx = divmod(i, 8)
                data[byte_idx] |= (1 << bit_idx)
        pdu = struct.pack(">BHHB", ModbusFC.WRITE_MULTIPLE_COILS,
                          address, count, byte_count) + bytes(data)
        await self._transact(pdu)

    async def write_registers(self, address: int, values: List[int]):
        """FC 0x10 写多个寄存器"""
        count = len(values)
        byte_count = count * 2
        data = b""
        for v in values:
            data += struct.pack(">H", int(v) & 0xFFFF)
        pdu = struct.pack(">BHHB", ModbusFC.WRITE_MULTIPLE_REGISTERS,
                          address, count, byte_count) + data
        await self._transact(pdu)


class ModbusError(Exception):
    """Modbus 异常响应"""
    ERROR_NAMES = {
        1: "非法功能码",
        2: "非法数据地址",
        3: "非法数据值",
        4: "从站设备故障",
    }

    def __init__(self, function_code: int, error_code: int):
        self.function_code = function_code
        self.error_code = error_code
        name = self.ERROR_NAMES.get(error_code, f"未知错误({error_code})")
        super().__init__(f"Modbus 异常 FC=0x{function_code:02X}: {name}")
