"""
视觉检测程序块 — VModule 的核心逻辑

这是一个 ProgramBlock（插入扫描引擎的异步回调），实现:
  EX 上升沿触发 → 相机拍照 → 模型推理 → 结果写入 EY/EW

配置语言完全基于 PLC 软元件地址，例如:
  - VM0 = 相机 ID (0=相机1, 1=相机2, ...)
  - VM1 = 模型 ID (0=模型1, 1=模型2, ...)
  - EX0 上升沿 = 触发检测
  - EY0 = 检测完成（脉冲）
  - EY1 = OK/NG 结果 (1=OK, 0=NG)
  - EW0 = 缺陷数量
  - EW1 = 推理耗时 (ms)

设计目标: PLC 工程师零学习成本
"""

from __future__ import annotations
import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from app.core.softdevice.memory import SoftDeviceMemory, SoftDeviceAddress
from app.core.image_store import save_detection_image
from app.core.persistence import save_detection_record

logger = logging.getLogger("vmodule.detection")


@dataclass
class DetectionChannel:
    """单路检测通道配置

    每个通道独立绑定:
      - 一个触发地址 (EX)
      - 一个相机
      - 一个模型
      - 一组输出地址 (EY/EW)

    PLC 工程师只需配置这些软元件地址即可完成检测流程。
    """
    name: str = ""

    # 触发
    trigger_addr: str = "EX0"       # 触发信号（上升沿检测）
    busy_addr: str = "VM100"        # 忙碌标志（检测中=1）

    # 相机 & 模型
    camera_id: str = ""             # 相机名称
    model_id: str = ""              # 模型名称

    # 检测参数（通过 VD ���置）
    conf_threshold_addr: str = ""   # 置信度阈值 (×1000, 如 VD100=500 表示 0.5)
    ok_min_addr: str = ""           # OK 最小缺陷数 (默认 0)
    ok_max_addr: str = ""           # OK 最大缺陷数 (默认 0，即无缺陷=OK)

    # 输出
    done_addr: str = "EY0"          # 检测完成（单次脉冲）
    result_addr: str = "EY1"        # OK=1, NG=0
    defect_count_addr: str = "EW0"  # 缺陷数量
    inference_time_addr: str = "EW1"  # 推理耗时 (ms)
    total_count_addr: str = "VD0"   # 累计检测次数
    ng_count_addr: str = "VD1"      # 累计 NG 次数

    # 运行时状态（非配置项）
    _pending_task: Optional[asyncio.Task] = field(default=None, repr=False)


class DetectionProgramBlock:
    """视觉检测程序块

    作为 ProgramBlock 注册到 ScanEngine，每个扫描周期被调用一次。

    工作流程:
      1. 检查每个通道的触发地址是否有上升沿
      2. 如果触发且不忙碌，启动异步检测任务
      3. 检测任务完成后，写入结果到输出地址
      4. 设置完成脉冲（下个扫描周期自动清除）

    用法:
        block = DetectionProgramBlock(camera_manager, inference_manager)
        block.add_channel(DetectionChannel(
            trigger_addr="EX0",
            camera_id="cam1",
            model_id="yolo_default",
            done_addr="EY0",
            result_addr="EY1",
        ))
        scan_engine.add_program(block)
    """

    def __init__(self, camera_manager=None, inference_manager=None):
        self._camera_mgr = camera_manager
        self._inference_mgr = inference_manager
        self._channels: List[DetectionChannel] = []

    def add_channel(self, channel: DetectionChannel):
        """添加检测通道"""
        self._channels.append(channel)
        logger.info(
            f"检测通道 [{channel.name or channel.trigger_addr}]: "
            f"触发={channel.trigger_addr} 相机={channel.camera_id} "
            f"模型={channel.model_id} → {channel.done_addr}/{channel.result_addr}"
        )

    async def __call__(self, memory: SoftDeviceMemory):
        """扫描周期回调 — 每个周期被 ScanEngine 调用一次"""
        for ch in self._channels:
            await self._process_channel(memory, ch)

    async def _process_channel(self, memory: SoftDeviceMemory, ch: DetectionChannel):
        """处理单个检测通道"""

        # 清除上次的完成脉冲
        try:
            if memory.read_bit(SoftDeviceAddress.parse(ch.done_addr)):
                memory.write_bit(SoftDeviceAddress.parse(ch.done_addr), False)
        except Exception:
            pass

        # 检查触发上升沿
        trigger = SoftDeviceAddress.parse(ch.trigger_addr)
        if not memory.rising_edge(trigger):
            return

        # 检查是否忙碌
        busy = SoftDeviceAddress.parse(ch.busy_addr)
        if memory.read_bit(busy):
            logger.debug(f"通道 [{ch.name}] 忙碌中，跳过触发")
            return

        # 设置忙碌
        memory.write_bit(busy, True)
        logger.info(f"通道 [{ch.name}] 触发检测")

        # 启动异步检测（不阻塞扫描周期）
        ch._pending_task = asyncio.create_task(
            self._run_detection(memory, ch)
        )

    async def _run_detection(self, memory: SoftDeviceMemory, ch: DetectionChannel):
        """执行完整的检测流程（异步）"""
        busy = SoftDeviceAddress.parse(ch.busy_addr)
        start_time = time.perf_counter()

        try:
            # ① 相机拍照
            image = await self._capture(ch)
            if image is None:
                logger.error(f"通道 [{ch.name}] 拍照失败")
                self._write_result(memory, ch, ok=False, defects=0, time_ms=0)
                return

            # ② 模型推理
            result = await self._predict(ch, image)
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            # ③ 判定 OK/NG
            detections = result.get("detections", []) if result else []
            defect_count = len(detections)

            # 读取阈值配置
            ok_max = 0  # 默认: 0 个缺陷 = OK
            if ch.ok_max_addr:
                try:
                    ok_max = memory.read_word(SoftDeviceAddress.parse(ch.ok_max_addr))
                except Exception:
                    pass

            is_ok = defect_count <= ok_max

            # ④ 写入结果
            self._write_result(memory, ch, ok=is_ok, defects=defect_count, time_ms=elapsed_ms)

            logger.info(
                f"通道 [{ch.name}] 检测完成: "
                f"{'OK' if is_ok else 'NG'} | "
                f"缺陷={defect_count} | "
                f"耗时={elapsed_ms}ms"
            )

            # ⑤ 图片存储 + 检测记录（不阻塞）
            image_path = await save_detection_image(ch.camera_id, image, is_ok)
            asyncio.create_task(save_detection_record(
                channel_name=ch.name,
                camera_id=ch.camera_id,
                model_id=ch.model_id,
                is_ok=is_ok,
                defect_count=defect_count,
                result_json=result,
                image_path=image_path,
                inference_ms=elapsed_ms,
            ))

        except Exception as e:
            logger.error(f"通道 [{ch.name}] 检测异常: {e}")
            self._write_result(memory, ch, ok=False, defects=0, time_ms=0)
        finally:
            # 释放忙碌
            memory.write_bit(busy, False)

    def _write_result(
        self,
        memory: SoftDeviceMemory,
        ch: DetectionChannel,
        ok: bool,
        defects: int,
        time_ms: int,
    ):
        """将检测结果写入软元件"""
        try:
            # 完成脉冲
            memory.write_bit(SoftDeviceAddress.parse(ch.done_addr), True)
            # OK/NG
            memory.write_bit(SoftDeviceAddress.parse(ch.result_addr), ok)
            # 缺陷数
            if ch.defect_count_addr:
                memory.write_word(SoftDeviceAddress.parse(ch.defect_count_addr), defects)
            # 推理耗时
            if ch.inference_time_addr:
                memory.write_word(SoftDeviceAddress.parse(ch.inference_time_addr), time_ms)
            # 累计计数
            if ch.total_count_addr:
                addr = SoftDeviceAddress.parse(ch.total_count_addr)
                memory.write_word(addr, memory.read_word(addr) + 1)
            if ch.ng_count_addr and not ok:
                addr = SoftDeviceAddress.parse(ch.ng_count_addr)
                memory.write_word(addr, memory.read_word(addr) + 1)
        except Exception as e:
            logger.error(f"写入结果异常: {e}")

    async def _capture(self, ch: DetectionChannel) -> Optional[np.ndarray]:
        """相机拍照"""
        if self._camera_mgr is None:
            logger.warning("相机管理器未初始化，使用测试图像")
            # 返回测试图像用于开发调试
            return np.zeros((480, 640, 3), dtype=np.uint8)

        try:
            return await self._camera_mgr.capture(ch.camera_id)
        except Exception as e:
            logger.error(f"相机 [{ch.camera_id}] 拍照失败: {e}")
            return None

    async def _predict(self, ch: DetectionChannel, image: np.ndarray) -> Optional[dict]:
        """模型推理"""
        if self._inference_mgr is None:
            logger.warning("推理管理器未初始化，返回空结果")
            return {"detections": [], "inference_time": 0}

        try:
            return await self._inference_mgr.predict(ch.model_id, image)
        except Exception as e:
            logger.error(f"模型 [{ch.model_id}] 推理失败: {e}")
            return None
