"""Single-frame PLC-triggered inspection program block."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from app.core.image_store import save_detection_image
from app.core.persistence import save_detection_record
from app.core.softdevice.memory import SoftDeviceAddress, SoftDeviceMemory

logger = logging.getLogger("vmodule.detection")

WORD_PREFIXES = ("EW", "ED", "VW", "VD", "SD", "SW", "D", "W")
DEFAULT_DEFECT_PRIORITY = ["NG", "HP_NG", "QJ_NG", "RJ_NG", "LX_NG"]
DEFAULT_DEFECT_CODE_MAP = {
    "NG": "ng_fatal",
    "HP_NG": "ng_repairable",
    "QJ_NG": "ng_repairable",
    "RJ_NG": "ng_repairable",
    "LX_NG": "ng_repairable",
}
DEFAULT_RESULT_CODES = {"ok": 7, "ng_repairable": 6, "ng_fatal": 5}


@dataclass
class DetectionChannel:
    """Single inspection channel bound to PLC soft-device addresses."""

    name: str = ""
    trigger_addr: str = "EX0"
    busy_addr: str = "VM100"
    camera_id: str = ""
    model_id: str = ""

    conf_threshold_addr: str = ""
    ok_min_addr: str = ""
    ok_max_addr: str = ""

    done_addr: str = "EY0"
    result_addr: str = "EY1"
    defect_count_addr: str = "EW0"
    inference_time_addr: str = "EW1"
    total_count_addr: str = "VD0"
    ng_count_addr: str = "VD1"

    ack_base: int = 16
    error_code: int = 255
    result_codes: Dict[str, int] = field(default_factory=lambda: dict(DEFAULT_RESULT_CODES))
    defect_priority: List[str] = field(default_factory=lambda: list(DEFAULT_DEFECT_PRIORITY))
    defect_code_map: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_DEFECT_CODE_MAP))
    inference: Dict[str, Any] = field(default_factory=dict)

    _pending_task: Optional[asyncio.Task] = field(default=None, repr=False)


class DetectionProgramBlock:
    """PLC scan callback for single-frame visual inspection."""

    def __init__(self, camera_manager=None, inference_manager=None):
        self._camera_mgr = camera_manager
        self._inference_mgr = inference_manager
        self._channels: List[DetectionChannel] = []

    def add_channel(self, channel: DetectionChannel):
        self._channels.append(channel)
        logger.info(
            "Detection channel [%s]: trigger=%s camera=%s model=%s -> %s/%s",
            channel.name or channel.trigger_addr,
            channel.trigger_addr,
            channel.camera_id,
            channel.model_id,
            channel.done_addr,
            channel.result_addr,
        )

    async def __call__(self, memory: SoftDeviceMemory):
        for ch in self._channels:
            await self._process_channel(memory, ch)

    async def _process_channel(self, memory: SoftDeviceMemory, ch: DetectionChannel):
        try:
            if memory.read_bit(SoftDeviceAddress.parse(ch.done_addr)):
                memory.write_bit(SoftDeviceAddress.parse(ch.done_addr), False)
        except Exception:
            pass

        trigger = SoftDeviceAddress.parse(ch.trigger_addr)
        if not memory.rising_edge(trigger):
            return

        busy = SoftDeviceAddress.parse(ch.busy_addr)
        if memory.read_bit(busy):
            logger.debug("Channel [%s] is busy; trigger skipped", ch.name)
            return

        memory.write_bit(busy, True)
        logger.info("Channel [%s] triggered", ch.name)
        ch._pending_task = asyncio.create_task(self._run_detection(memory, ch))

    async def _run_detection(self, memory: SoftDeviceMemory, ch: DetectionChannel):
        busy = SoftDeviceAddress.parse(ch.busy_addr)
        start_time = time.perf_counter()

        try:
            image = await self._capture(ch)
            if image is None:
                logger.error("Channel [%s] capture failed", ch.name)
                self._write_result(memory, ch, ok=False, defects=0, time_ms=0, detections=[], result_level="error")
                return

            self._write_response(memory, ch, int(ch.ack_base), ok=True)

            result = await self._predict(ch, image)
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            detections = result.get("detections", []) if result else []
            defect_count = len(detections)

            ok_max = 0
            if ch.ok_max_addr:
                try:
                    ok_max = memory.read_word(SoftDeviceAddress.parse(ch.ok_max_addr))
                except Exception:
                    pass

            is_ok = defect_count <= ok_max
            level = "ok" if is_ok else self._classify_defects(ch, detections)
            self._write_result(memory, ch, ok=is_ok, defects=defect_count, time_ms=elapsed_ms, detections=detections, result_level=level)

            logger.info(
                "Channel [%s] done: %s defects=%s elapsed=%sms level=%s",
                ch.name,
                "OK" if is_ok else "NG",
                defect_count,
                elapsed_ms,
                level,
            )

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
            logger.error("Channel [%s] detection error: %s", ch.name, e)
            self._write_result(memory, ch, ok=False, defects=0, time_ms=0, detections=[], result_level="error")
        finally:
            memory.write_bit(busy, False)

    def _write_result(
        self,
        memory: SoftDeviceMemory,
        ch: DetectionChannel,
        ok: bool,
        defects: int,
        time_ms: int,
        detections: List[dict[str, Any]],
        result_level: str,
    ):
        try:
            memory.write_bit(SoftDeviceAddress.parse(ch.done_addr), True)
            result_code = self._result_code(ch, result_level, ok)
            self._write_response(memory, ch, result_code, ok=ok)

            if ch.defect_count_addr:
                memory.write_word(SoftDeviceAddress.parse(ch.defect_count_addr), defects)
            if ch.inference_time_addr:
                memory.write_word(SoftDeviceAddress.parse(ch.inference_time_addr), time_ms)
            if ch.total_count_addr:
                addr = SoftDeviceAddress.parse(ch.total_count_addr)
                memory.write_word(addr, memory.read_word(addr) + 1)
            if ch.ng_count_addr and not ok:
                addr = SoftDeviceAddress.parse(ch.ng_count_addr)
                memory.write_word(addr, memory.read_word(addr) + 1)
        except Exception as e:
            logger.error("Write detection result failed: %s", e)

    def _write_response(self, memory: SoftDeviceMemory, ch: DetectionChannel, value: int, ok: bool):
        if not ch.result_addr:
            return
        addr = SoftDeviceAddress.parse(ch.result_addr)
        if self._is_word_address(ch.result_addr):
            memory.write_word(addr, int(value))
        else:
            memory.write_bit(addr, bool(ok))

    def _result_code(self, ch: DetectionChannel, level: str, ok: bool) -> int:
        codes = {**DEFAULT_RESULT_CODES, **dict(ch.result_codes or {})}
        if level == "error":
            return int(ch.error_code)
        if ok:
            return int(codes.get("ok", 7))
        return int(codes.get(level, codes.get("ng_fatal", 5)))

    def _classify_defects(self, ch: DetectionChannel, detections: List[dict[str, Any]]) -> str:
        classes = {str(d.get("class", d.get("label", ""))) for d in detections}
        for defect in ch.defect_priority or DEFAULT_DEFECT_PRIORITY:
            if defect in classes:
                return (ch.defect_code_map or DEFAULT_DEFECT_CODE_MAP).get(defect, "ng_fatal")
        return "ng_fatal"

    def _is_word_address(self, address: str) -> bool:
        return address.upper().startswith(WORD_PREFIXES)

    async def _capture(self, ch: DetectionChannel) -> Optional[np.ndarray]:
        if self._camera_mgr is None:
            logger.warning("Camera manager is not initialized; using test image")
            return np.zeros((480, 640, 3), dtype=np.uint8)

        try:
            return await self._camera_mgr.capture(ch.camera_id)
        except Exception as e:
            logger.error("Camera [%s] capture failed: %s", ch.camera_id, e)
            return None

    async def _predict(self, ch: DetectionChannel, image: np.ndarray) -> Optional[dict]:
        if self._inference_mgr is None:
            logger.warning("Inference manager is not initialized; returning empty result")
            return {"detections": [], "inference_time": 0}

        kwargs = self._inference_kwargs(ch)
        try:
            return await self._inference_mgr.predict(ch.model_id, image, **kwargs)
        except Exception as e:
            logger.error("Model [%s] predict failed: %s", ch.model_id, e)
            return None

    def _inference_kwargs(self, ch: DetectionChannel) -> dict[str, Any]:
        raw = ch.inference or {}
        mapping = {
            "inference_size": "imgsz",
            "imgsz": "imgsz",
            "conf_threshold": "conf",
            "conf": "conf",
            "iou_threshold": "iou",
            "iou": "iou",
            "max_det": "max_det",
            "augment": "augment",
        }
        kwargs = {}
        for src, dst in mapping.items():
            if src in raw and raw[src] is not None:
                kwargs[dst] = raw[src]
        return kwargs
