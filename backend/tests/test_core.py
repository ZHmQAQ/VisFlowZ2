"""
VModule 核心模块单元测试

覆盖:
  1. 软元件内存 — 位/字读写、边沿检测、定时器、计数器、SET/RST/MOV
  2. 信捷地址解析 — 地址解析、Modbus 地址转换、八进制地址
  3. Modbus 客户端 — 帧构建、MBAP 头
  4. 扫描引擎 — 生命周期、程序块注册
  5. 检测程序块 — 触发→拍照→推理→写回
  6. I/O 映射 — 分组、批量优化
"""

import asyncio
import pytest
import struct
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.softdevice.memory import (
    SoftDeviceMemory, SoftDeviceAddress, DevicePrefix,
    BitArray, WordArray, TimerDevice, CounterDevice,
    DEVICE_CAPACITY,
)
from app.core.softdevice.xinje import (
    XinjeAddress, XinjeDeviceType, IOMapping,
    COIL_TYPES, REGISTER_TYPES, OCTAL_TYPES,
)
from app.core.plc.modbus_client import (
    ModbusTCPClient, PLCConnection, ModbusFC, ModbusError,
)
from app.core.scanner.engine import ScanEngine, ScannerConfig, IOBatch
from app.core.detection.program_block import DetectionProgramBlock, DetectionChannel


# ============================================================
# 1. BitArray / WordArray 底层存储
# ============================================================

class TestBitArray:
    def test_basic_get_set(self):
        ba = BitArray(64)
        assert ba.get(0) is False
        ba.set(0, True)
        assert ba.get(0) is True
        ba.set(0, False)
        assert ba.get(0) is False

    def test_range(self):
        ba = BitArray(64)
        ba.set(3, True)
        ba.set(5, True)
        result = ba.get_range(0, 8)
        assert result == [False, False, False, True, False, True, False, False]

    def test_set_range(self):
        ba = BitArray(64)
        ba.set_range(4, [True, False, True])
        assert ba.get(4) is True
        assert ba.get(5) is False
        assert ba.get(6) is True

    def test_clear_all(self):
        ba = BitArray(32)
        ba.set(0, True)
        ba.set(31, True)
        ba.clear_all()
        assert ba.get(0) is False
        assert ba.get(31) is False

    def test_out_of_range(self):
        ba = BitArray(8)
        with pytest.raises((IndexError, ValueError)):
            ba.get(8)


class TestWordArray:
    def test_basic_get_set(self):
        wa = WordArray(64)
        assert wa.get(0) == 0
        wa.set(0, 1234)
        assert wa.get(0) == 1234

    def test_signed_overflow(self):
        wa = WordArray(16)
        wa.set(0, 32768)  # 超出有符号范围
        # 应该截断为 16 位
        val = wa.get(0)
        assert -32768 <= val <= 32767

    def test_unsigned(self):
        wa = WordArray(16)
        wa.set(0, -1)
        unsigned = wa.get_unsigned(0)
        assert unsigned == 65535

    def test_range(self):
        wa = WordArray(16)
        wa.set(0, 100)
        wa.set(1, 200)
        wa.set(2, 300)
        result = wa.get_range(0, 3)
        assert result == [100, 200, 300]

    def test_dword(self):
        wa = WordArray(16)
        wa.set_dword(0, 70000)  # 超过 16 位
        val = wa.get_dword(0)
        assert val == 70000


# ============================================================
# 2. SoftDeviceAddress 解析
# ============================================================

class TestSoftDeviceAddress:
    def test_parse_basic(self):
        addr = SoftDeviceAddress.parse("EX0")
        assert addr.prefix == DevicePrefix.EX
        assert addr.index == 0

    def test_parse_with_number(self):
        addr = SoftDeviceAddress.parse("VD100")
        assert addr.prefix == DevicePrefix.VD
        assert addr.index == 100

    def test_str(self):
        addr = SoftDeviceAddress.parse("VM42")
        assert str(addr) == "VM42"

    def test_is_bit(self):
        assert SoftDeviceAddress.parse("EX0").is_bit is True
        assert SoftDeviceAddress.parse("EY5").is_bit is True
        assert SoftDeviceAddress.parse("VM10").is_bit is True

    def test_is_word(self):
        assert SoftDeviceAddress.parse("ED0").is_word is True
        assert SoftDeviceAddress.parse("EW0").is_word is True
        assert SoftDeviceAddress.parse("VD0").is_word is True

    def test_is_external(self):
        assert SoftDeviceAddress.parse("EX0").is_external is True
        assert SoftDeviceAddress.parse("VM0").is_external is False

    def test_is_input_output(self):
        assert SoftDeviceAddress.parse("EX0").is_input is True
        assert SoftDeviceAddress.parse("ED0").is_input is True
        assert SoftDeviceAddress.parse("EY0").is_output is True
        assert SoftDeviceAddress.parse("EW0").is_output is True

    def test_is_readonly(self):
        assert SoftDeviceAddress.parse("SM0").is_readonly is True
        assert SoftDeviceAddress.parse("SD0").is_readonly is True
        assert SoftDeviceAddress.parse("VM0").is_readonly is False

    def test_invalid_prefix(self):
        with pytest.raises((ValueError, KeyError)):
            SoftDeviceAddress.parse("ZZ0")

    def test_out_of_capacity(self):
        with pytest.raises((ValueError, IndexError)):
            SoftDeviceAddress.parse("EX9999")

    def test_hash_and_eq(self):
        a = SoftDeviceAddress.parse("EX0")
        b = SoftDeviceAddress.parse("EX0")
        assert a == b
        assert hash(a) == hash(b)
        assert a != SoftDeviceAddress.parse("EX1")


# ============================================================
# 3. SoftDeviceMemory 读写与指令
# ============================================================

class TestSoftDeviceMemory:
    def setup_method(self):
        self.mem = SoftDeviceMemory()

    def test_read_write_bit(self):
        addr = SoftDeviceAddress.parse("VM0")
        self.mem.write_bit(addr, True)
        assert self.mem.read_bit(addr) is True
        self.mem.write_bit(addr, False)
        assert self.mem.read_bit(addr) is False

    def test_read_write_word(self):
        addr = SoftDeviceAddress.parse("VD0")
        self.mem.write_word(addr, 12345)
        assert self.mem.read_word(addr) == 12345

    def test_convenience_read_write(self):
        self.mem.write("VM5", True)
        assert self.mem.read("VM5") is True
        self.mem.write("VD10", 999)
        assert self.mem.read("VD10") == 999

    def test_SET_RST(self):
        self.mem.SET("VM0")
        assert self.mem.read("VM0") is True
        self.mem.RST("VM0")
        assert self.mem.read("VM0") is False

    def test_MOV(self):
        self.mem.write("VD0", 777)
        self.mem.MOV("VD0", "VD1")
        assert self.mem.read("VD1") == 777

    def test_readonly_write_raises(self):
        addr = SoftDeviceAddress.parse("SM0")
        with pytest.raises(PermissionError):
            self.mem.write_bit(addr, True)

    def test_bulk_bits(self):
        self.mem.write_bits_bulk(DevicePrefix.VM, 0, [True, False, True, True])
        result = self.mem.read_bits_bulk(DevicePrefix.VM, 0, 4)
        assert result == [True, False, True, True]

    def test_bulk_words(self):
        self.mem.write_words_bulk(DevicePrefix.VD, 0, [100, 200, 300])
        result = self.mem.read_words_bulk(DevicePrefix.VD, 0, 3)
        assert result == [100, 200, 300]

    def test_edge_detection(self):
        addr = SoftDeviceAddress.parse("EX0")
        # 初始快照
        self.mem.snapshot_for_edge_detection()
        # 写入 True
        self.mem.write_bit(addr, True)
        # 此时 prev=False, current=True → 上升沿
        assert self.mem.rising_edge(addr) is True
        assert self.mem.falling_edge(addr) is False
        # 更新快照
        self.mem.snapshot_for_edge_detection()
        # 状态不变 → 无边沿
        assert self.mem.rising_edge(addr) is False
        # 写入 False
        self.mem.write_bit(addr, False)
        # prev=True, current=False → 下降沿
        assert self.mem.falling_edge(addr) is True

    def test_external_io_read_write(self):
        # EX/EY 应可正常读写
        ex_addr = SoftDeviceAddress.parse("EX0")
        self.mem.write_bit(ex_addr, True)
        assert self.mem.read_bit(ex_addr) is True

        ey_addr = SoftDeviceAddress.parse("EY0")
        self.mem.write_bit(ey_addr, True)
        assert self.mem.read_bit(ey_addr) is True

    def test_ed_ew_word_io(self):
        self.mem.write("ED0", 500)
        assert self.mem.read("ED0") == 500
        self.mem.write("EW0", 600)
        assert self.mem.read("EW0") == 600


# ============================================================
# 4. 定时器 / 计数器
# ============================================================

class TestTimerCounter:
    def setup_method(self):
        self.mem = SoftDeviceMemory()

    def test_timer_basic(self):
        # 设置定时器 VT0 预设值 = 10 (×10ms = 100ms)
        addr = SoftDeviceAddress.parse("VT0")
        self.mem.write_word(addr, 10)  # preset = 10
        # 启动定时器 (写 coil = True)
        self.mem.write_bit(addr, True)
        # 模拟时间流逝
        for _ in range(5):
            self.mem.update_timers(20)  # 5 × 20ms = 100ms
        # 应该到期了 (current >= preset)
        timer = self.mem._timers[0]
        assert timer.contact is True

    def test_counter_basic(self):
        addr = SoftDeviceAddress.parse("VC0")
        self.mem.write_word(addr, 3)  # preset = 3
        # 计数器检测 coil 从 False→True 的上升沿
        # 每轮: 先 update（记录 prev=当前coil），再设 coil=True
        for _ in range(3):
            # update 先把 _prev_coil 更新为当前 coil 值
            # 然后把 coil 设为 False（模拟下降沿）
            self.mem.write_bit(addr, False)
            self.mem.update_counters()  # prev=False
            # 再设 True（上升沿）
            self.mem.write_bit(addr, True)
            self.mem.update_counters()  # coil=True, prev=False → +1, 然后 prev=True
        counter = self.mem._counters[0]
        assert counter.current >= 3 or counter.contact is True


# ============================================================
# 5. 信捷地址映射
# ============================================================

class TestXinjeAddress:
    def test_parse_M(self):
        addr = XinjeAddress.parse("M100")
        assert addr.device_type == XinjeDeviceType.M
        assert addr.index == 100

    def test_parse_D(self):
        addr = XinjeAddress.parse("D1000")
        assert addr.device_type == XinjeDeviceType.D
        assert addr.index == 1000

    def test_parse_X_octal(self):
        addr = XinjeAddress.parse("X10")
        assert addr.device_type == XinjeDeviceType.X
        assert addr.index == 8  # 八进制 10 = 十进制 8

    def test_parse_Y_octal(self):
        addr = XinjeAddress.parse("Y7")
        assert addr.device_type == XinjeDeviceType.Y
        assert addr.index == 7

    def test_coil_register_classification(self):
        assert XinjeAddress.parse("M0").is_coil is True
        assert XinjeAddress.parse("M0").is_register is False
        assert XinjeAddress.parse("D0").is_register is True
        assert XinjeAddress.parse("D0").is_coil is False

    def test_modbus_address_M(self):
        addr = XinjeAddress.parse("M100")
        modbus = addr.to_modbus_address()
        assert modbus == 100  # M0 -> Modbus 0x0000, M100 -> 100

    def test_modbus_address_D(self):
        addr = XinjeAddress.parse("D100")
        modbus = addr.to_modbus_address()
        assert modbus == 100  # D0 -> Modbus 0x0000

    def test_modbus_address_X(self):
        addr = XinjeAddress.parse("X0")
        modbus = addr.to_modbus_address()
        assert modbus == 0x5000  # X -> base 0x5000

    def test_str(self):
        assert str(XinjeAddress.parse("M100")) == "M100"
        # X/Y 应该显示八进制
        x_addr = XinjeAddress.parse("X10")
        assert "X" in str(x_addr)

    def test_HM(self):
        addr = XinjeAddress.parse("HM0")
        assert addr.device_type == XinjeDeviceType.HM
        assert addr.is_coil is True

    def test_HD(self):
        addr = XinjeAddress.parse("HD500")
        assert addr.device_type == XinjeDeviceType.HD
        assert addr.is_register is True


# ============================================================
# 6. IOMapping
# ============================================================

class TestIOMapping:
    def test_basic_mapping(self):
        m = IOMapping(
            vmodule_addr="EX0",
            plc_addr="M100",
            plc_name="PLC1",
            description="启动信号",
        )
        assert m.is_coil is True
        assert m.is_register is False

    def test_register_mapping(self):
        m = IOMapping(
            vmodule_addr="ED0",
            plc_addr="D200",
            plc_name="PLC1",
        )
        assert m.is_register is True
        assert m.is_coil is False

    def test_modbus_address(self):
        m = IOMapping(vmodule_addr="EX0", plc_addr="M100", plc_name="PLC1")
        modbus = m.get_modbus_address()
        assert modbus == 100


# ============================================================
# 7. Modbus 客户端 — 帧构建
# ============================================================

class TestModbusClient:
    def test_mbap_header(self):
        config = PLCConnection(name="test", host="127.0.0.1")
        client = ModbusTCPClient(config)
        pdu = bytes([0x01, 0x00, 0x00, 0x00, 0x0A])  # FC01 read 10 coils from 0
        tid = 1
        frame = client._build_mbap(tid, pdu)
        # MBAP: TID(2) + Protocol(2) + Length(2) + UnitID(1) + PDU
        assert len(frame) == 7 + len(pdu)
        parsed_tid = struct.unpack(">H", frame[0:2])[0]
        assert parsed_tid == tid
        protocol_id = struct.unpack(">H", frame[2:4])[0]
        assert protocol_id == 0
        length = struct.unpack(">H", frame[4:6])[0]
        assert length == 1 + len(pdu)  # UnitID + PDU
        assert frame[6] == config.unit_id

    def test_modbus_fc_enum(self):
        assert ModbusFC.READ_COILS == 0x01
        assert ModbusFC.READ_HOLDING_REGISTERS == 0x03
        assert ModbusFC.WRITE_SINGLE_COIL == 0x05
        assert ModbusFC.WRITE_MULTIPLE_REGISTERS == 0x10

    def test_plc_connection_defaults(self):
        c = PLCConnection(name="t", host="192.168.1.1")
        assert c.port == 502
        assert c.unit_id == 1
        assert c.timeout == 2.0
        assert c.retry_count == 3


# ============================================================
# 8. IOBatch 分组优化
# ============================================================

class TestIOBatch:
    def test_group_mappings(self):
        mappings = [
            IOMapping(vmodule_addr="EX0", plc_addr="M0", plc_name="PLC1"),
            IOMapping(vmodule_addr="EX1", plc_addr="M1", plc_name="PLC1"),
            IOMapping(vmodule_addr="ED0", plc_addr="D100", plc_name="PLC2"),
        ]
        groups = IOBatch.group_mappings(mappings, is_input=True)
        assert "PLC1" in groups
        assert "PLC2" in groups

    def test_optimize_ranges(self):
        mappings = [
            IOMapping(vmodule_addr="EX0", plc_addr="M0", plc_name="PLC1"),
            IOMapping(vmodule_addr="EX1", plc_addr="M1", plc_name="PLC1"),
            IOMapping(vmodule_addr="EX2", plc_addr="M2", plc_name="PLC1"),
        ]
        ranges = IOBatch.optimize_ranges(mappings)
        # 至少应该返回结果
        assert len(ranges) >= 1


# ============================================================
# 9. ScanEngine 生命周期
# ============================================================

class TestScanEngine:
    def test_init(self):
        mem = SoftDeviceMemory()
        engine = ScanEngine(memory=mem)
        assert engine.running is False
        assert engine.scan_count == 0

    def test_add_plc(self):
        mem = SoftDeviceMemory()
        engine = ScanEngine(memory=mem)
        conn = PLCConnection(name="PLC1", host="192.168.1.1")
        engine.add_plc(conn)
        assert "PLC1" in engine._plc_clients

    def test_add_mapping(self):
        mem = SoftDeviceMemory()
        engine = ScanEngine(memory=mem)
        m = IOMapping("PLC1", "M0", "EX0")
        engine.add_mapping(m)
        assert len(engine._io_mappings) == 1

    def test_add_program(self):
        mem = SoftDeviceMemory()
        engine = ScanEngine(memory=mem)

        async def dummy_block(memory):
            pass

        engine.add_program(dummy_block)
        assert len(engine._program_blocks) == 1

    @pytest.mark.asyncio
    async def test_start_stop(self):
        mem = SoftDeviceMemory()
        engine = ScanEngine(memory=mem, config=ScannerConfig(target_cycle_ms=100))
        await engine.start()
        assert engine.running is True
        await asyncio.sleep(0.15)  # 让它跑几个周期
        assert engine.scan_count > 0
        await engine.stop()
        assert engine.running is False

    def test_get_status(self):
        mem = SoftDeviceMemory()
        engine = ScanEngine(memory=mem)
        status = engine.get_status()
        assert "running" in status
        assert "scan_count" in status


# ============================================================
# 10. DetectionProgramBlock
# ============================================================

class TestDetectionProgramBlock:
    def test_add_channel(self):
        block = DetectionProgramBlock()
        ch = DetectionChannel(
            name="CH1",
            trigger_addr="EX0",
            camera_id="cam1",
            model_id="yolo1",
            done_addr="EY0",
            result_addr="EY1",
        )
        block.add_channel(ch)
        assert len(block._channels) == 1
        assert block._channels[0].name == "CH1"

    @pytest.mark.asyncio
    async def test_no_trigger_no_action(self):
        """无触发信号时不应执行任何检测"""
        mem = SoftDeviceMemory()
        mem.snapshot_for_edge_detection()  # 初始快照

        block = DetectionProgramBlock()
        ch = DetectionChannel(
            name="CH1",
            trigger_addr="EX0",
            done_addr="EY0",
            result_addr="EY1",
        )
        block.add_channel(ch)
        await block(mem)
        # 没有触发，done 应为 False
        assert mem.read("EY0") is False

    @pytest.mark.asyncio
    async def test_trigger_fires_detection(self):
        """上升沿触发后应执行检测并写入结果"""
        mem = SoftDeviceMemory()
        mem.snapshot_for_edge_detection()

        block = DetectionProgramBlock()  # 无相机/推理 → 用 fallback 测试数据
        ch = DetectionChannel(
            name="CH1",
            trigger_addr="EX0",
            busy_addr="VM100",
            camera_id="test",
            model_id="test",
            done_addr="EY0",
            result_addr="EY1",
            defect_count_addr="EW0",
            inference_time_addr="EW1",
            total_count_addr="VD0",
            ng_count_addr="VD1",
        )
        block.add_channel(ch)

        # 模拟 EX0 上升沿
        mem.write_bit(SoftDeviceAddress.parse("EX0"), True)
        await block(mem)

        # 等待异步任务完成
        if ch._pending_task:
            await ch._pending_task

        # fallback 推理返回空 detections → 0 缺陷 → OK
        assert mem.read("EY0") is True   # done 脉冲
        assert mem.read("EY1") is True   # OK
        assert mem.read("EW0") == 0      # 缺陷数
        assert mem.read("VD0") == 1      # 累计检测次数

    @pytest.mark.asyncio
    async def test_busy_blocks_retrigger(self):
        """忙碌时不应重复触发"""
        mem = SoftDeviceMemory()
        mem.snapshot_for_edge_detection()

        block = DetectionProgramBlock()
        ch = DetectionChannel(name="CH1", trigger_addr="EX0", busy_addr="VM100")
        block.add_channel(ch)

        # 设置忙碌
        mem.write_bit(SoftDeviceAddress.parse("VM100"), True)
        # 模拟上升沿
        mem.write_bit(SoftDeviceAddress.parse("EX0"), True)
        await block(mem)
        # 应该不会启动新任务
        assert ch._pending_task is None


# ============================================================
# 11. 集成冒烟测试
# ============================================================

class TestIntegration:
    @pytest.mark.asyncio
    async def test_full_scan_cycle_with_detection(self):
        """完整扫描周期: 引擎 + 检测程序块"""
        mem = SoftDeviceMemory()
        engine = ScanEngine(memory=mem, config=ScannerConfig(target_cycle_ms=50))

        block = DetectionProgramBlock()
        ch = DetectionChannel(
            name="Integration",
            trigger_addr="EX0",
            busy_addr="VM100",
            done_addr="EY0",
            result_addr="EY1",
            defect_count_addr="EW0",
            inference_time_addr="EW1",
            total_count_addr="VD0",
        )
        block.add_channel(ch)
        engine.add_program(block)

        await engine.start()
        assert engine.running is True

        # 等几个空闲扫描周期
        await asyncio.sleep(0.2)
        assert engine.scan_count > 0

        # 模拟触发
        mem.snapshot_for_edge_detection()
        mem.write_bit(SoftDeviceAddress.parse("EX0"), True)

        # 等待检测完成
        await asyncio.sleep(0.3)

        await engine.stop()
        # 验证引擎停止
        assert engine.running is False

    def test_memory_address_full_coverage(self):
        """验证所有软元件前缀都可正常读写"""
        mem = SoftDeviceMemory()
        # 位设备
        for prefix in ["EX", "EY", "VM"]:
            addr = SoftDeviceAddress.parse(f"{prefix}0")
            mem.write_bit(addr, True)
            assert mem.read_bit(addr) is True

        # 字设备
        for prefix in ["ED", "EW", "VD"]:
            addr = SoftDeviceAddress.parse(f"{prefix}0")
            mem.write_word(addr, 42)
            assert mem.read_word(addr) == 42

        # 只读设备可读不可写
        sm_addr = SoftDeviceAddress.parse("SM0")
        _ = mem.read_bit(sm_addr)  # 应该不报错
        with pytest.raises(PermissionError):
            mem.write_bit(sm_addr, True)

    def test_xinje_to_io_mapping_chain(self):
        """信捷地址 → Modbus → IOMapping 完整链路"""
        mapping = IOMapping(
            vmodule_addr="EX0",
            plc_addr="M100",
            plc_name="PLC1",
            description="启动信号",
        )
        # 解析链
        xinje = mapping.get_xinje_address()
        assert xinje.device_type == XinjeDeviceType.M
        assert xinje.index == 100
        modbus = mapping.get_modbus_address()
        assert modbus == 100
        # 反向解析
        reverse = XinjeAddress.from_modbus(modbus, is_coil=True)
        assert reverse is not None
        assert reverse.device_type == XinjeDeviceType.M


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
