"""
扫描引擎 — VModule 的心脏

仿照 PLC 的扫描周期模型:
  ┌──────────────────────────────────────────────────┐
  │ 一个扫描周期                                      │
  │                                                  │
  │  ① 输入刷新  从 PLC 读取 EX/ED                   │
  │       ↓                                          │
  │  ② 逻辑执行  处理所有程序块（触发→拍照→推理→判定）│
  │       ↓                                          │
  │  ③ 输出刷新  向 PLC 写出 EY/EW                   │
  │       ↓                                          │
  │  ④ 内务处理  更新 VT/VC/SM/SD，边沿快照          │
  │       ↓                                          │
  │  → 回到 ①                                        │
  └──────────────────────────────────────────────────┘

关键设计:
  - 扫描周期目标: 10~50ms（可配置）
  - 输入/输出通过 Modbus TCP 批量读写（减少通信���数）
  - 逻辑执行是异步的（相机采集、推理可能跨多个扫描周期）
  - 系统软元件 SM/SD 在每个周期末尾更新
"""

from __future__ import annotations
import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable, Awaitable

from app.core.softdevice.memory import (
    SoftDeviceMemory, SoftDeviceAddress, DevicePrefix,
)
from app.core.softdevice.xinje import (
    XinjeAddress, IOMapping, COIL_TYPES, REGISTER_TYPES,
)
from app.core.plc.modbus_client import ModbusTCPClient, PLCConnection

logger = logging.getLogger("vmodule.scanner")


@dataclass
class ScannerConfig:
    """扫描引擎配置"""
    target_cycle_ms: int = 20      # 目标扫描周期 (ms)
    io_batch_size: int = 64        # 单次 Modbus 批量读写最大数量
    max_consecutive_errors: int = 10  # 连续错误阈值（超过后暂停通信）


class IOBatch:
    """I/O 批量操作 — 将多个离散地址合并为连续的 Modbus 读写

    PLC 通信优化的关键: 尽量用一次 Modbus 请求读/写连续地址范围，
    而不是每个地址单独请求。
    """

    @staticmethod
    def group_mappings(
        mappings: List[IOMapping],
        is_input: bool,
    ) -> Dict[str, Dict[str, List[IOMapping]]]:
        """将映射按 PLC 名称和类型（线圈/寄存器）分组

        Returns:
            { plc_name: { "coil": [...], "register": [...] } }
        """
        groups: Dict[str, Dict[str, List[IOMapping]]] = {}
        for m in mappings:
            xaddr = m.get_xinje_address()
            # 过滤方向
            vaddr = SoftDeviceAddress.parse(m.vmodule_addr)
            if is_input and not vaddr.is_input:
                continue
            if not is_input and not vaddr.is_output:
                continue

            plc = m.plc_name
            if plc not in groups:
                groups[plc] = {"coil": [], "register": []}
            key = "coil" if xaddr.is_coil else "register"
            groups[plc][key].append(m)

        return groups

    @staticmethod
    def optimize_ranges(
        mappings: List[IOMapping],
    ) -> List[Tuple]:
        """将离散地址优化为连续范围

        Returns:
            [(start_modbus_addr, count, [(mapping, offset), ...]), ...]
        """
        if not mappings:
            return []

        # 按 Modbus 地址排序
        sorted_maps = sorted(mappings, key=lambda m: m.get_modbus_address())

        ranges = []
        range_start = sorted_maps[0].get_modbus_address()
        range_items = [(sorted_maps[0], 0)]

        for m in sorted_maps[1:]:
            addr = m.get_modbus_address()
            offset = addr - range_start
            if offset < 64:  # 间距小于 64，合并
                range_items.append((m, offset))
            else:
                # 新范围
                count = range_items[-1][1] + 1
                ranges.append((range_start, count, range_items))
                range_start = addr
                range_items = [(m, 0)]

        count = range_items[-1][1] + 1
        ranges.append((range_start, count, range_items))
        return ranges


# 类型别名: 程序块回调
ProgramBlock = Callable[[SoftDeviceMemory], Awaitable[None]]


class ScanEngine:
    """扫描引擎

    VModule 的主循环，负责:
      1. 管理 PLC 连接
      2. 周期性 I/O 刷新
      3. 执行用户程序块
      4. 更新系统状态
    """

    def __init__(
        self,
        memory: SoftDeviceMemory,
        config: ScannerConfig = None,
    ):
        self.memory = memory
        self.config = config or ScannerConfig()
        self._plc_clients: Dict[str, ModbusTCPClient] = {}
        self._io_mappings: List[IOMapping] = []
        self._program_blocks: List[ProgramBlock] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._scan_count: int = 0
        self._last_scan_ms: float = 0
        self._consecutive_errors: int = 0

    # ==================== 配置 ====================

    def add_plc(self, config: PLCConnection):
        """添加 PLC 连接"""
        client = ModbusTCPClient(config)
        self._plc_clients[config.name] = client
        logger.info(f"添加 PLC: {config.name} ({config.host}:{config.port})")

    def add_mapping(self, mapping: IOMapping):
        """添加 I/O 映射"""
        self._io_mappings.append(mapping)

    def add_mappings(self, mappings: List[IOMapping]):
        """批量添加 I/O 映射"""
        self._io_mappings.extend(mappings)

    def add_program(self, block: ProgramBlock):
        """添加程序块（按添加顺序执行）"""
        self._program_blocks.append(block)

    # ==================== 生命周期 ====================

    async def start(self):
        """启动扫描引擎"""
        if self._running:
            return

        # 连接所有 PLC
        for name, client in self._plc_clients.items():
            try:
                await client.connect()
            except Exception as e:
                logger.error(f"PLC [{name}] 连接失败: {e}")

        self._running = True
        self._task = asyncio.create_task(self._scan_loop())
        logger.info(
            f"扫描引擎启动 | "
            f"目标周期={self.config.target_cycle_ms}ms | "
            f"PLC={len(self._plc_clients)} | "
            f"映射={len(self._io_mappings)} | "
            f"程序块={len(self._program_blocks)}"
        )

    async def stop(self):
        """停止扫描引擎"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # 断开所有 PLC
        for client in self._plc_clients.values():
            await client.disconnect()

        logger.info(f"扫描引擎停止 | 总扫描次数={self._scan_count}")

    # ==================== 扫描主循环 ====================

    async def _scan_loop(self):
        """扫描主循环"""
        while self._running:
            cycle_start = time.perf_counter()

            try:
                # ① 输入刷新
                await self._refresh_inputs()

                # ② 逻辑执行
                for block in self._program_blocks:
                    try:
                        await block(self.memory)
                    except Exception as e:
                        logger.error(f"程序块执行异常: {e}")

                # ③ 输出刷新
                await self._refresh_outputs()

                # ④ 内务处理
                cycle_end = time.perf_counter()
                self._last_scan_ms = (cycle_end - cycle_start) * 1000
                self._scan_count += 1

                self.memory.update_timers(self._last_scan_ms)
                self.memory.update_counters()
                self.memory.snapshot_for_edge_detection()
                self.memory._update_system(
                    scan_cycle_ms=self._last_scan_ms,
                    plc_count=sum(1 for c in self._plc_clients.values() if c.connected),
                    model_count=self._get_model_count(),
                    camera_count=self._get_camera_count(),
                )

                self._consecutive_errors = 0

            except Exception as e:
                self._consecutive_errors += 1
                logger.error(f"扫描周期异常 ({self._consecutive_errors}): {e}")
                if self._consecutive_errors >= self.config.max_consecutive_errors:
                    logger.critical("连续错误过多，暂停扫描 5 秒")
                    # Use internal write to bypass readonly check for SM11
                    self.memory._bits[DevicePrefix.SM].set(11, True)
                    await asyncio.sleep(5)
                    self.memory._bits[DevicePrefix.SM].set(11, False)
                    self._consecutive_errors = 0

            # 等待到目标周期
            elapsed = (time.perf_counter() - cycle_start) * 1000
            sleep_ms = self.config.target_cycle_ms - elapsed
            if sleep_ms > 0:
                await asyncio.sleep(sleep_ms / 1000)

    # ==================== I/O 刷新 ====================

    async def _refresh_inputs(self):
        """从 PLC 读取输入软元件到 EX/ED"""
        groups = IOBatch.group_mappings(self._io_mappings, is_input=True)

        for plc_name, type_groups in groups.items():
            client = self._plc_clients.get(plc_name)
            if not client or not client.connected:
                continue

            # 读线圈 → EX
            for m in type_groups.get("coil", []):
                try:
                    modbus_addr = m.get_modbus_address()
                    values = await client.read_coils(modbus_addr, 1)
                    self.memory.write(m.vmodule_addr, values[0])
                except Exception as e:
                    logger.debug(f"读线圈失败 {m.plc_addr}: {e}")

            # 读寄存器 → ED
            for m in type_groups.get("register", []):
                try:
                    modbus_addr = m.get_modbus_address()
                    values = await client.read_registers(modbus_addr, 1)
                    self.memory.write(m.vmodule_addr, values[0])
                except Exception as e:
                    logger.debug(f"读寄存器失败 {m.plc_addr}: {e}")

    async def _refresh_outputs(self):
        """将 EY/EW 写出到 PLC"""
        groups = IOBatch.group_mappings(self._io_mappings, is_input=False)

        for plc_name, type_groups in groups.items():
            client = self._plc_clients.get(plc_name)
            if not client or not client.connected:
                continue

            # EY → 写线圈
            for m in type_groups.get("coil", []):
                try:
                    modbus_addr = m.get_modbus_address()
                    value = self.memory.read(m.vmodule_addr)
                    await client.write_coil(modbus_addr, bool(value))
                except Exception as e:
                    logger.debug(f"写线圈失败 {m.plc_addr}: {e}")

            # EW → 写寄存器
            for m in type_groups.get("register", []):
                try:
                    modbus_addr = m.get_modbus_address()
                    value = self.memory.read(m.vmodule_addr)
                    await client.write_register(modbus_addr, int(value))
                except Exception as e:
                    logger.debug(f"写寄存器失败 {m.plc_addr}: {e}")

    # ==================== 状态查询 ====================

    @property
    def running(self) -> bool:
        return self._running

    @property
    def scan_count(self) -> int:
        return self._scan_count

    @property
    def last_scan_ms(self) -> float:
        return self._last_scan_ms

    def get_status(self) -> dict:
        """获取引擎状态"""
        return {
            "running": self._running,
            "scan_count": self._scan_count,
            "last_scan_ms": round(self._last_scan_ms, 2),
            "target_cycle_ms": self.config.target_cycle_ms,
            "plc_connections": {
                name: client.connected
                for name, client in self._plc_clients.items()
            },
            "io_mappings": len(self._io_mappings),
            "program_blocks": len(self._program_blocks),
        }

    def _get_model_count(self) -> int:
        """Get loaded model count from inference manager."""
        try:
            from app.core.inference.manager import inference_manager
            return inference_manager.get_loaded_count()
        except Exception:
            return 0

    def _get_camera_count(self) -> int:
        """Get connected camera count from camera manager."""
        try:
            from app.core.camera.manager import camera_manager
            return len([info for info in camera_manager.get_all_info()
                        if info and info.get('is_open')])
        except Exception:
            return 0
