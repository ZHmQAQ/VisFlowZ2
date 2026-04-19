"""
信捷 PLC 软元件地址 → Modbus 地址转换

参考: 信捷 XG 系列 PLC 用户手册 [基本指令篇] 第 6-2-3 节

信捷 PLC Modbus 地址映射表（线圈/位对象）:
  M0~M20479        → Modbus 0x0000~0x4FFF     (FC 0x01/0x05/0x0F)
  X0~X77 (八进制)   → Modbus 0x5000~0x503F
  Y0~Y77 (八进制)   → Modbus 0x6000~0x603F
  S0~S4095         → Modbus 0x7000~0x7FFF
  HM0~HM6143       → Modbus 0xC100~0xD8FF

信捷 PLC Modbus 地址映射表（寄存器/字对象）:
  D0~D20479        → Modbus 0x0000~0x4FFF     (FC 0x03/0x06/0x10)
  HD0~HD6143       → Modbus 0xA080~0xB87F
  SD0~SD4095       → Modbus 0x7000~0x7FFF
  FD0~FD8191       → Modbus 0xC4C0~0xE4BF
  TD0~TD4095       → Modbus 0x8000~0x8FFF
  CD0~CD4095       → Modbus 0x9000~0x9FFF

注意:
  1. X/Y 为八进制编址，转 Modbus 时需先转十进制
  2. 线圈和寄存器的 Modbus 地址空间是独立的
  3. FC 0x01/0x05/0x0F 操作线圈；FC 0x03/0x06/0x10 操作寄存器
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple
import re
import logging

logger = logging.getLogger("vmodule.xinje")


class XinjeDeviceType(str, Enum):
    """信捷 PLC 软元件类型"""
    # 位对象（线圈）
    M = "M"       # 辅助继电器
    HM = "HM"     # 掉电保持辅助继电器
    X = "X"       # 输入继电器（八进制）
    Y = "Y"       # 输出继电器（八进制）
    S = "S"       # 状态继电器
    HS = "HS"     # 掉电保持状态继电器
    SM = "SM"     # 特殊辅助继电器（只读）
    T = "T"       # 定时器触点
    C = "C"       # 计数器触点

    # 字对象（寄存器）
    D = "D"       # 数据寄存器
    HD = "HD"     # 掉电保持数据寄存器
    SD = "SD"     # 特殊数据寄存器（只读）
    FD = "FD"     # FlashROM 寄存器
    TD = "TD"     # 定时器当前值
    CD = "CD"     # 计数器当前值
    HSD = "HSD"   # 掉电保持特殊数据寄存器
    ID = "ID"     # 输入寄存器
    QD = "QD"     # 输出寄存器


# 线圈类型
COIL_TYPES = {XinjeDeviceType.M, XinjeDeviceType.HM, XinjeDeviceType.X,
              XinjeDeviceType.Y, XinjeDeviceType.S, XinjeDeviceType.HS,
              XinjeDeviceType.SM, XinjeDeviceType.T, XinjeDeviceType.C}

# 寄存器类型
REGISTER_TYPES = {XinjeDeviceType.D, XinjeDeviceType.HD, XinjeDeviceType.SD,
                  XinjeDeviceType.FD, XinjeDeviceType.TD, XinjeDeviceType.CD,
                  XinjeDeviceType.HSD, XinjeDeviceType.ID, XinjeDeviceType.QD}

# 八进制编址类型
OCTAL_TYPES = {XinjeDeviceType.X, XinjeDeviceType.Y}


# Modbus 地址映射表（线圈）
_COIL_MAP = {
    XinjeDeviceType.M:  (0x0000, 0, 20480),
    XinjeDeviceType.X:  (0x5000, 0, 64),       # 本体 X0~X77
    XinjeDeviceType.Y:  (0x6000, 0, 64),       # 本体 Y0~Y77
    XinjeDeviceType.S:  (0x7000, 0, 4096),
    XinjeDeviceType.SM: (0x8000, 0, 2048),
    XinjeDeviceType.T:  (0x9000, 0, 4096),
    XinjeDeviceType.C:  (0xA000, 0, 4096),
    XinjeDeviceType.HM: (0xC100, 0, 6144),
    XinjeDeviceType.HS: (0xD900, 0, 1000),
}

# Modbus 地址映射表（寄存器）
_REGISTER_MAP = {
    XinjeDeviceType.D:   (0x0000, 0, 20480),
    XinjeDeviceType.SD:  (0x7000, 0, 4096),
    XinjeDeviceType.TD:  (0x8000, 0, 4096),
    XinjeDeviceType.CD:  (0x9000, 0, 4096),
    XinjeDeviceType.HD:  (0xA080, 0, 6144),
    XinjeDeviceType.HSD: (0xB880, 0, 1024),
    XinjeDeviceType.FD:  (0xC4C0, 0, 8192),
}


@dataclass
class XinjeAddress:
    """信捷 PLC 软元件地址

    示例:
      M100   → 辅助继电器 100
      D1000  → 数据寄存器 1000
      X0     → 输入继电器 0（八进制）
      Y17    → 输出继电器 17（八进制，十进制=15）
      HD500  → 掉电保持寄存器 500
    """
    device_type: XinjeDeviceType
    index: int  # 十进制索引（X/Y 已从八进制转换）

    def __str__(self) -> str:
        if self.device_type in OCTAL_TYPES:
            return f"{self.device_type.value}{oct(self.index)[2:]}"
        return f"{self.device_type.value}{self.index}"

    @property
    def is_coil(self) -> bool:
        return self.device_type in COIL_TYPES

    @property
    def is_register(self) -> bool:
        return self.device_type in REGISTER_TYPES

    def to_modbus_address(self) -> int:
        """转换为 Modbus 协议地址

        返回: Modbus 地址（16bit 无符号）
        Raises: ValueError 如果地址不在映射范围内
        """
        table = _COIL_MAP if self.is_coil else _REGISTER_MAP
        entry = table.get(self.device_type)
        if entry is None:
            raise ValueError(f"不支持的软元件类型: {self.device_type.value}")

        base_modbus, base_index, capacity = entry
        offset = self.index - base_index
        if not (0 <= offset < capacity):
            raise ValueError(
                f"{self} 地址越界: "
                f"有效范围 {self.device_type.value}{base_index}~"
                f"{self.device_type.value}{base_index + capacity - 1}"
            )
        return base_modbus + offset

    @classmethod
    def parse(cls, addr_str: str) -> "XinjeAddress":
        """从字符串解析信捷软元件地址

        支持:
          "M100", "D1000", "X0", "Y17", "HD500", "HM200", "SM10"
        """
        addr_str = addr_str.strip().upper()

        # 按前缀长度降序匹配（HSD > HS > H, 防止误匹配）
        for dt in sorted(XinjeDeviceType, key=lambda x: -len(x.value)):
            if addr_str.startswith(dt.value):
                idx_str = addr_str[len(dt.value):]
                if not idx_str.isdigit():
                    continue

                if dt in OCTAL_TYPES:
                    # X/Y 为八进制编址
                    index = int(idx_str, 8)
                else:
                    index = int(idx_str)

                return cls(device_type=dt, index=index)

        raise ValueError(f"无法解析信捷软元件地址: '{addr_str}'")

    @classmethod
    def from_modbus(cls, modbus_addr: int, is_coil: bool) -> Optional["XinjeAddress"]:
        """从 Modbus 地址反向解析信捷软元件地址

        Args:
            modbus_addr: Modbus 地址
            is_coil: True 查线圈表，False 查寄存器表
        """
        table = _COIL_MAP if is_coil else _REGISTER_MAP
        best = None
        best_offset = 0xFFFF

        for dt, (base, start, cap) in table.items():
            offset = modbus_addr - base
            if 0 <= offset < cap and offset < best_offset:
                best = cls(device_type=dt, index=start + offset)
                best_offset = offset

        return best


@dataclass
class IOMapping:
    """外部 I/O 映射条目 — VModule 软元件 ↔ PLC 软元件

    一条映射定义了:
      VModule 侧地址 (EX0/EY0/ED0/EW0 等)
      PLC 侧地址 (M100/D1000 等)
      方向: input (PLC→VModule) / output (VModule→PLC)
      所属 PLC 连接名称

    示例:
      IOMapping(
          vmodule_addr="EX0",
          plc_addr="M100",
          plc_name="1号机PLC",
          description="工位1触发"
      )
    """
    vmodule_addr: str          # VModule 软元件地址 (如 "EX0")
    plc_addr: str              # 信捷 PLC 软元件地址 (如 "M100")
    plc_name: str              # PLC 连接名称
    description: str = ""      # 描述
    enabled: bool = True       # 是否启用（False 时扫描引擎跳过此映射）

    def get_xinje_address(self) -> XinjeAddress:
        """解析 PLC 侧地址"""
        return XinjeAddress.parse(self.plc_addr)

    def get_modbus_address(self) -> int:
        """获取 Modbus 协议地址"""
        return self.get_xinje_address().to_modbus_address()

    @property
    def is_coil(self) -> bool:
        return self.get_xinje_address().is_coil

    @property
    def is_register(self) -> bool:
        return self.get_xinje_address().is_register
