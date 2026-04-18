"""
虚拟软元件系统 — VModule 核心抽象

仿照信捷 XG 系列 PLC 的软元件体系，定义 VModule 内部的数据空间。

信捷 PLC 软元件参考:
  X/Y   输入/输出继电器    1bit
  M/HM  辅助继电器         1bit
  D/HD  数据寄存器         16bit
  T     定时器             16bit + 线圈
  C     计数器             16bit + 线圈
  S     状态继电器         1bit
  SM/SD 特殊辅助/数据      只读系统状态

VModule 软元件定义:
  ┌──────────┬────────┬──────┬──────────────────────────────────┐
  │ 前缀     │ 类型   │ 宽度 │ 说明                             │
  ├──────────┼────────┼──────┼──────────────────────────────────┤
  │ EX       │ 外部输入│ 1bit │ PLC → VModule (线圈/触发信号)    │
  │ EY       │ 外部输出│ 1bit │ VModule → PLC (完成/NG 标志)     │
  │ ED       │ 外部输入│ 16bit│ PLC → VModule (参数/模式)        │
  │ EW       │ 外部输出│ 16bit│ VModule → PLC (结果/数值)        │
  │ VM       │ 内部位  │ 1bit │ 内部逻辑标志                     │
  │ VD       │ 内部字  │ 16bit│ 内部数据（图像ID/结果/置信度）   │
  │ VT       │ 定时器  │ 16bit│ 内部定时器（带线圈+当前值）      │
  │ VC       │ 计数器  │ 16bit│ 内部计数器（带线圈+当前值）      │
  │ SM       │ 系统位  │ 1bit │ 只读系统状态标志                 │
  │ SD       │ 系统字  │ 16bit│ 只读系统诊断数据                 │
  └──────────┴────────┴──────┴──────────────────────────────────┘

地址空间:
  EX0~EX255     外部输入位       (256 点)
  EY0~EY255     外部输出位       (256 点)
  ED0~ED255     外部输入字       (256 字)
  EW0~EW255     外部输出字       (256 字)
  VM0~VM4095    内部虚拟继电器   (4096 点)
  VD0~VD4095    内部虚拟寄存器   (4096 字)
  VT0~VT255    虚拟定时器        (256 个)
  VC0~VC255    虚拟计数器        (256 个)
  SM0~SM255     系统状态位       (256 点, 只读)
  SD0~SD255     系统数据字       (256 字, 只读)
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Optional, Callable, List
import threading
import time
import logging

logger = logging.getLogger("vmodule.softdevice")


class DevicePrefix(str, Enum):
    """软元件前缀 — 决定了数据类型和读写方向"""
    # 外部 I/O（与 PLC 通信）
    EX = "EX"   # External Input  (bit)  PLC → VModule
    EY = "EY"   # External Output (bit)  VModule → PLC
    ED = "ED"   # External Input  (word) PLC → VModule
    EW = "EW"   # External Output (word) VModule → PLC

    # 内部逻辑
    VM = "VM"   # Virtual Memory  (bit)  内部辅助继电器
    VD = "VD"   # Virtual Data    (word) 内部数据寄存器
    VT = "VT"   # Virtual Timer          内部定时器
    VC = "VC"   # Virtual Counter        内部计数器

    # 系统保留（只读）
    SM = "SM"   # System Memory   (bit)  系统状态
    SD = "SD"   # System Data     (word) 系统诊断


# 每种软元件的容量
DEVICE_CAPACITY = {
    DevicePrefix.EX: 256,
    DevicePrefix.EY: 256,
    DevicePrefix.ED: 256,
    DevicePrefix.EW: 256,
    DevicePrefix.VM: 4096,
    DevicePrefix.VD: 4096,
    DevicePrefix.VT: 256,
    DevicePrefix.VC: 256,
    DevicePrefix.SM: 256,
    DevicePrefix.SD: 256,
}


@dataclass
class SoftDeviceAddress:
    """软元件地址 — 如 EX0, VD100, SM10 等

    解析规则（与信捷 PLC 一致）:
      "EX0"   → prefix=EX, index=0
      "VD100" → prefix=VD, index=100
      "SM10"  → prefix=SM, index=10
    """
    prefix: DevicePrefix
    index: int

    def __post_init__(self):
        cap = DEVICE_CAPACITY.get(self.prefix, 0)
        if not (0 <= self.index < cap):
            raise ValueError(
                f"地址越界: {self.prefix.value}{self.index}, "
                f"有效范围: {self.prefix.value}0~{self.prefix.value}{cap - 1}"
            )

    def __str__(self) -> str:
        return f"{self.prefix.value}{self.index}"

    def __hash__(self) -> int:
        return hash((self.prefix, self.index))

    def __eq__(self, other) -> bool:
        if isinstance(other, SoftDeviceAddress):
            return self.prefix == other.prefix and self.index == other.index
        return False

    @classmethod
    def parse(cls, addr_str: str) -> "SoftDeviceAddress":
        """从字符串解析软元件地址

        支持格式: "EX0", "VD100", "SM10", "eX0"（大小写不敏感）
        """
        addr_str = addr_str.strip().upper()

        # 尝试匹配所有已知前缀（按长度降序，确保 SM 优先于 S）
        for prefix in sorted(DevicePrefix, key=lambda p: -len(p.value)):
            if addr_str.startswith(prefix.value):
                idx_str = addr_str[len(prefix.value):]
                if idx_str.isdigit():
                    return cls(prefix=prefix, index=int(idx_str))

        raise ValueError(f"无法解析软元件地址: '{addr_str}'")

    @property
    def is_bit(self) -> bool:
        """是否为位软元件"""
        return self.prefix in (
            DevicePrefix.EX, DevicePrefix.EY,
            DevicePrefix.VM, DevicePrefix.SM,
        )

    @property
    def is_word(self) -> bool:
        """是否为字软元件"""
        return self.prefix in (
            DevicePrefix.ED, DevicePrefix.EW,
            DevicePrefix.VD, DevicePrefix.SD,
        )

    @property
    def is_timer_counter(self) -> bool:
        """是否为定时器/计数器"""
        return self.prefix in (DevicePrefix.VT, DevicePrefix.VC)

    @property
    def is_external(self) -> bool:
        """是否为外部 I/O（与 PLC 映射）"""
        return self.prefix in (
            DevicePrefix.EX, DevicePrefix.EY,
            DevicePrefix.ED, DevicePrefix.EW,
        )

    @property
    def is_input(self) -> bool:
        """是否为输入方向（PLC → VModule）"""
        return self.prefix in (DevicePrefix.EX, DevicePrefix.ED)

    @property
    def is_output(self) -> bool:
        """是否为输出方向（VModule → PLC）"""
        return self.prefix in (DevicePrefix.EY, DevicePrefix.EW)

    @property
    def is_readonly(self) -> bool:
        """是否只读（系统软元件）"""
        return self.prefix in (DevicePrefix.SM, DevicePrefix.SD)


class BitArray:
    """位数组 — 用于存储位软元件（线圈/继电器）"""

    def __init__(self, size: int):
        self._size = size
        self._data = bytearray((size + 7) // 8)

    def get(self, index: int) -> bool:
        if not (0 <= index < self._size):
            raise IndexError(f"位地址越界: {index}, 范围: 0~{self._size - 1}")
        byte_idx, bit_idx = divmod(index, 8)
        return bool(self._data[byte_idx] & (1 << bit_idx))

    def set(self, index: int, value: bool):
        if not (0 <= index < self._size):
            raise IndexError(f"位地址越界: {index}, 范围: 0~{self._size - 1}")
        byte_idx, bit_idx = divmod(index, 8)
        if value:
            self._data[byte_idx] |= (1 << bit_idx)
        else:
            self._data[byte_idx] &= ~(1 << bit_idx)

    def get_range(self, start: int, count: int) -> List[bool]:
        return [self.get(start + i) for i in range(count)]

    def set_range(self, start: int, values: List[bool]):
        for i, v in enumerate(values):
            self.set(start + i, v)

    def clear_all(self):
        self._data = bytearray(len(self._data))

    @property
    def size(self) -> int:
        return self._size


class WordArray:
    """字数组 — 用于存储字软元件（寄存器），16bit 有符号"""

    def __init__(self, size: int):
        self._size = size
        self._data = [0] * size

    def get(self, index: int) -> int:
        if not (0 <= index < self._size):
            raise IndexError(f"字地址越界: {index}, 范围: 0~{self._size - 1}")
        return self._data[index]

    def set(self, index: int, value: int):
        if not (0 <= index < self._size):
            raise IndexError(f"字地址越界: {index}, 范围: 0~{self._size - 1}")
        # 16bit 有符号范围: -32768 ~ 32767
        value = int(value) & 0xFFFF
        if value > 0x7FFF:
            value -= 0x10000
        self._data[index] = value

    def get_unsigned(self, index: int) -> int:
        """读取无符号值 (0~65535)"""
        v = self.get(index)
        return v if v >= 0 else v + 0x10000

    def get_range(self, start: int, count: int) -> List[int]:
        return [self.get(start + i) for i in range(count)]

    def set_range(self, start: int, values: List[int]):
        for i, v in enumerate(values):
            self.set(start + i, v)

    def get_dword(self, index: int) -> int:
        """读取 32bit 双字（两个连续寄存器组合，低位在前）"""
        lo = self.get_unsigned(index)
        hi = self.get_unsigned(index + 1)
        val = (hi << 16) | lo
        if val > 0x7FFFFFFF:
            val -= 0x100000000
        return val

    def set_dword(self, index: int, value: int):
        """写入 32bit 双字"""
        value = int(value) & 0xFFFFFFFF
        self.set(index, value & 0xFFFF)
        self.set(index + 1, (value >> 16) & 0xFFFF)

    def clear_all(self):
        self._data = [0] * self._size

    @property
    def size(self) -> int:
        return self._size


@dataclass
class TimerDevice:
    """虚拟定时器 — 仿照信捷 PLC T 软元件

    使用方式:
      VT0 预设值 100 (×10ms = 1秒)
      当 VT0 线圈被驱动时，当前值每 10ms +1
      当前值 >= 预设值时，VT0 触点 ON
    """
    preset: int = 0          # 预设值
    current: int = 0         # 当前值
    coil: bool = False       # 线圈（驱动输入）
    contact: bool = False    # 触点（输出）
    accumulative: bool = False  # 累计模式

    def reset(self):
        self.current = 0
        self.contact = False
        if not self.accumulative:
            self.coil = False


@dataclass
class CounterDevice:
    """虚拟计数器 — 仿照信捷 PLC C 软元件"""
    preset: int = 0
    current: int = 0
    coil: bool = False       # 计数输入（上升沿+1）
    contact: bool = False    # 到达预设值时 ON
    _prev_coil: bool = False

    def reset(self):
        self.current = 0
        self.contact = False


class SoftDeviceMemory:
    """软元件内存空间 — VModule 的完整数据空间

    这是整个系统的核心数据结构。
    所有模块（扫描引擎、PLC 通信、相机控制、推理引擎）
    都通过读写这个内存空间来交互。

    类比 PLC: 这就是 PLC 的内部存储器。

    线程安全: 所有读写操作通过锁保护。
    """

    def __init__(self):
        self._lock = threading.RLock()

        # 位软元件
        self._bits: Dict[DevicePrefix, BitArray] = {
            DevicePrefix.EX: BitArray(DEVICE_CAPACITY[DevicePrefix.EX]),
            DevicePrefix.EY: BitArray(DEVICE_CAPACITY[DevicePrefix.EY]),
            DevicePrefix.VM: BitArray(DEVICE_CAPACITY[DevicePrefix.VM]),
            DevicePrefix.SM: BitArray(DEVICE_CAPACITY[DevicePrefix.SM]),
        }

        # 字软元件
        self._words: Dict[DevicePrefix, WordArray] = {
            DevicePrefix.ED: WordArray(DEVICE_CAPACITY[DevicePrefix.ED]),
            DevicePrefix.EW: WordArray(DEVICE_CAPACITY[DevicePrefix.EW]),
            DevicePrefix.VD: WordArray(DEVICE_CAPACITY[DevicePrefix.VD]),
            DevicePrefix.SD: WordArray(DEVICE_CAPACITY[DevicePrefix.SD]),
        }

        # 定时器/计数器
        self._timers: List[TimerDevice] = [
            TimerDevice() for _ in range(DEVICE_CAPACITY[DevicePrefix.VT])
        ]
        self._counters: List[CounterDevice] = [
            CounterDevice() for _ in range(DEVICE_CAPACITY[DevicePrefix.VC])
        ]

        # 上一扫描周期的位状态快照（用于边沿检测）
        self._prev_bits: Dict[DevicePrefix, BitArray] = {
            prefix: BitArray(arr.size)
            for prefix, arr in self._bits.items()
        }

        # 初始化系统软元件
        self._init_system_devices()

    def _init_system_devices(self):
        """初始化系统软元件默认值"""
        # SM0: 系统运行中 (常 ON)
        self._bits[DevicePrefix.SM].set(0, True)
        # SM1: 首次扫描标志 (第一个扫描周期后清除)
        self._bits[DevicePrefix.SM].set(1, True)

    # ==================== 通用读写接口 ====================

    def read_bit(self, addr: SoftDeviceAddress) -> bool:
        """读取位软元件"""
        with self._lock:
            if addr.prefix in (DevicePrefix.VT, DevicePrefix.VC):
                if addr.prefix == DevicePrefix.VT:
                    return self._timers[addr.index].contact
                else:
                    return self._counters[addr.index].contact

            arr = self._bits.get(addr.prefix)
            if arr is None:
                raise TypeError(f"{addr} 不是位软元件")
            return arr.get(addr.index)

    def write_bit(self, addr: SoftDeviceAddress, value: bool):
        """写入位软元件"""
        if addr.is_readonly:
            raise PermissionError(f"系统软元件 {addr} 只读，不可写入")

        with self._lock:
            if addr.prefix == DevicePrefix.VT:
                self._timers[addr.index].coil = value
                return
            elif addr.prefix == DevicePrefix.VC:
                self._counters[addr.index].coil = value
                return

            arr = self._bits.get(addr.prefix)
            if arr is None:
                raise TypeError(f"{addr} 不是位软元件")
            arr.set(addr.index, value)

    def read_word(self, addr: SoftDeviceAddress) -> int:
        """读取字软元件"""
        with self._lock:
            if addr.prefix == DevicePrefix.VT:
                return self._timers[addr.index].current
            elif addr.prefix == DevicePrefix.VC:
                return self._counters[addr.index].current

            arr = self._words.get(addr.prefix)
            if arr is None:
                raise TypeError(f"{addr} 不是字软元件")
            return arr.get(addr.index)

    def write_word(self, addr: SoftDeviceAddress, value: int):
        """写入字软元件"""
        if addr.is_readonly:
            raise PermissionError(f"系统软元件 {addr} 只读，不可写入")

        with self._lock:
            if addr.prefix == DevicePrefix.VT:
                self._timers[addr.index].preset = value
                return
            elif addr.prefix == DevicePrefix.VC:
                self._counters[addr.index].preset = value
                return

            arr = self._words.get(addr.prefix)
            if arr is None:
                raise TypeError(f"{addr} 不是字软元件")
            arr.set(addr.index, value)

    # ==================== 便捷方法 ====================

    def read(self, addr_str: str):
        """通用读取 — 自动判断位/字"""
        addr = SoftDeviceAddress.parse(addr_str)
        if addr.is_bit or addr.is_timer_counter:
            return self.read_bit(addr)
        else:
            return self.read_word(addr)

    def write(self, addr_str: str, value):
        """通用写入 — 自动判断位/字"""
        addr = SoftDeviceAddress.parse(addr_str)
        if addr.is_bit or (addr.is_timer_counter and isinstance(value, bool)):
            self.write_bit(addr, bool(value))
        else:
            self.write_word(addr, int(value))

    def SET(self, addr_str: str):
        """置位 — 仿照 PLC SET 指令"""
        self.write_bit(SoftDeviceAddress.parse(addr_str), True)

    def RST(self, addr_str: str):
        """复位 — 仿照 PLC RST 指令"""
        addr = SoftDeviceAddress.parse(addr_str)
        if addr.prefix == DevicePrefix.VT:
            with self._lock:
                self._timers[addr.index].reset()
        elif addr.prefix == DevicePrefix.VC:
            with self._lock:
                self._counters[addr.index].reset()
        else:
            self.write_bit(addr, False)

    def MOV(self, src_addr: str, dst_addr: str):
        """传送 — 仿照 PLC MOV 指令"""
        value = self.read(src_addr)
        self.write(dst_addr, value)

    # ==================== 边沿检测 ====================

    def rising_edge(self, addr: SoftDeviceAddress) -> bool:
        """上升沿检测 — 仿照 PLC LDP 指令"""
        with self._lock:
            current = self.read_bit(addr)
            prev_arr = self._prev_bits.get(addr.prefix)
            if prev_arr is None:
                return False
            prev = prev_arr.get(addr.index)
            return current and not prev

    def falling_edge(self, addr: SoftDeviceAddress) -> bool:
        """下降沿检测 — 仿照 PLC LDF 指令"""
        with self._lock:
            current = self.read_bit(addr)
            prev_arr = self._prev_bits.get(addr.prefix)
            if prev_arr is None:
                return False
            prev = prev_arr.get(addr.index)
            return not current and prev

    def snapshot_for_edge_detection(self):
        """保存当前位状态快照（每个扫描周期末尾调用）"""
        with self._lock:
            for prefix, arr in self._bits.items():
                prev = self._prev_bits.get(prefix)
                if prev:
                    prev._data = bytearray(arr._data)

    # ==================== 批量读写（给 Modbus 通信层用） ====================

    def read_bits_bulk(self, prefix: DevicePrefix, start: int, count: int) -> List[bool]:
        """批量读取位软元件"""
        with self._lock:
            arr = self._bits.get(prefix)
            if arr is None:
                raise TypeError(f"{prefix.value} 不是位软元件")
            return arr.get_range(start, count)

    def write_bits_bulk(self, prefix: DevicePrefix, start: int, values: List[bool]):
        """批量写入位软元件"""
        with self._lock:
            arr = self._bits.get(prefix)
            if arr is None:
                raise TypeError(f"{prefix.value} 不是位软元件")
            arr.set_range(start, values)

    def read_words_bulk(self, prefix: DevicePrefix, start: int, count: int) -> List[int]:
        """批量读取字软元件"""
        with self._lock:
            arr = self._words.get(prefix)
            if arr is None:
                raise TypeError(f"{prefix.value} 不是字软元件")
            return arr.get_range(start, count)

    def write_words_bulk(self, prefix: DevicePrefix, start: int, values: List[int]):
        """批量写入字软元件"""
        with self._lock:
            arr = self._words.get(prefix)
            if arr is None:
                raise TypeError(f"{prefix.value} 不是字软元件")
            arr.set_range(start, values)

    # ==================== 定时器/计数器更新 ====================

    def update_timers(self, elapsed_ms: float):
        """更新所有定时器（每个扫描周期调用）"""
        with self._lock:
            for t in self._timers:
                if t.coil:
                    # 定时器计时中（单位: 10ms 递增）
                    t.current += int(elapsed_ms / 10)
                    if t.current >= t.preset and t.preset > 0:
                        t.contact = True
                elif not t.accumulative:
                    t.current = 0
                    t.contact = False

    def update_counters(self):
        """更新所有计数器（每个扫描周期调用）"""
        with self._lock:
            for c in self._counters:
                # 检测计数输入上升沿
                if c.coil and not c._prev_coil:
                    c.current += 1
                    if c.current >= c.preset and c.preset > 0:
                        c.contact = True
                c._prev_coil = c.coil

    # ==================== 系统软元件更新 ====================

    def _update_system(self, scan_cycle_ms: float, **kwargs):
        """更新系统软元件（内部调用）"""
        with self._lock:
            # SD0: 扫描周期 (ms)
            self._words[DevicePrefix.SD].set(0, int(scan_cycle_ms))
            # SD1: 已连接 PLC 数量
            self._words[DevicePrefix.SD].set(1, kwargs.get("plc_count", 0))
            # SD2: 已加载模型数量
            self._words[DevicePrefix.SD].set(2, kwargs.get("model_count", 0))
            # SD3: 已连接相机数量
            self._words[DevicePrefix.SD].set(3, kwargs.get("camera_count", 0))

            # SM1: 首次扫描标志（第一次更新后清除）
            if self._bits[DevicePrefix.SM].get(1):
                self._bits[DevicePrefix.SM].set(1, False)

    # ==================== 调试/监控 ====================

    def dump(self, prefix: DevicePrefix, start: int = 0, count: int = 16) -> str:
        """导出软元件状态（调试用）"""
        lines = []
        if prefix in self._bits:
            arr = self._bits[prefix]
            for i in range(start, min(start + count, arr.size)):
                v = arr.get(i)
                if v:
                    lines.append(f"  {prefix.value}{i} = ON")
        elif prefix in self._words:
            arr = self._words[prefix]
            for i in range(start, min(start + count, arr.size)):
                v = arr.get(i)
                if v != 0:
                    lines.append(f"  {prefix.value}{i} = {v} (H{v & 0xFFFF:04X})")

        if not lines:
            return f"  ({prefix.value}{start}~{prefix.value}{start + count - 1} 全部为 0/OFF)"
        return "\n".join(lines)
