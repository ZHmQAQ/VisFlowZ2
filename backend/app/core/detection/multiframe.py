"""Multi-frame register-polling inspection program block.

This block keeps VModule's PLC-style register handshake while making the
workflow configurable enough for the baseline two-camera / two-frame process:

  PLC command register (ED) changes to a configured command value
      -> capture one frame with the configured camera
      -> run that frame's configured model
      -> cache detections
      -> write per-frame status to EW, normally 10 + command (11, 12, ...)

  all configured commands collected
      -> aggregate detections using VisFlowZ 7/6/5 semantics
      -> write the final result to the status/result register
      -> wait for PLC reset or apply the configured reset policy

The command register is input-only from VModule's point of view. PLC reset or
VModule reset behavior is selected by reset_policy rather than hard-coded.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from app.core.image_store import save_cycle_frame, save_cycle_json
from app.core.persistence import save_detection_record
from app.core.softdevice.memory import SoftDeviceAddress, SoftDeviceMemory
from app.utils.logger import logger as loguru_logger

logger = logging.getLogger("vmodule.detection.multiframe")


DEFAULT_DEFECT_PRIORITY = ["CL", "JS", "HH", "YW"]
DEFAULT_DEFECT_CODE_MAP = {
    "CL": "ng_fatal",
    "JS": "ng_fatal",
    "HH": "ng_fatal",
    "YW": "ng_repairable",
}
DEFAULT_RESULT_CODES = {"ok": 7, "ng_repairable": 6, "ng_fatal": 5}


@dataclass
class FramePlanItem:
    """Single frame command configuration."""

    command: int
    model_id: str = ""
    status_code: Optional[int] = None
    exposure: Optional[int] = None
    label: str = ""

    @classmethod
    def from_raw(cls, raw: Any, fallback_model_id: str = "") -> "FramePlanItem":
        if isinstance(raw, cls):
            return raw
        if isinstance(raw, int):
            return cls(command=raw, model_id=fallback_model_id)
        if isinstance(raw, dict):
            command = int(raw.get("command", raw.get("frame_index", 0)))
            status = raw.get("status_code")
            exposure = raw.get("exposure")
            return cls(
                command=command,
                model_id=raw.get("model_id") or fallback_model_id,
                status_code=int(status) if status is not None else None,
                exposure=int(exposure) if exposure is not None else None,
                label=raw.get("label", ""),
            )
        raise ValueError(f"Invalid frame_plan item: {raw!r}")


@dataclass
class ResultPolicy:
    defect_priority: List[str] = field(default_factory=lambda: list(DEFAULT_DEFECT_PRIORITY))
    defect_code_map: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_DEFECT_CODE_MAP))
    result_codes: Dict[str, int] = field(default_factory=lambda: dict(DEFAULT_RESULT_CODES))
    error_code: int = 255

    @classmethod
    def from_raw(cls, raw: Optional[dict]) -> "ResultPolicy":
        raw = raw or {}
        return cls(
            defect_priority=list(raw.get("defect_priority", DEFAULT_DEFECT_PRIORITY)),
            defect_code_map=dict(raw.get("defect_code_map", DEFAULT_DEFECT_CODE_MAP)),
            result_codes={**DEFAULT_RESULT_CODES, **dict(raw.get("result_codes", {}))},
            error_code=int(raw.get("error_code", 255)),
        )


@dataclass
class SavePolicy:
    mode: str = "all"  # all / ng / off
    image_format: str = "jpg"
    save_json: bool = True

    @classmethod
    def from_raw(cls, raw: Optional[dict]) -> "SavePolicy":
        raw = raw or {}
        return cls(
            mode=raw.get("mode", "all"),
            image_format=raw.get("image_format", raw.get("format", "jpg")),
            save_json=bool(raw.get("save_json", True)),
        )


@dataclass
class ResetPolicy:
    mode: str = "wait_plc_zero"  # wait_plc_zero / immediate / none
    clear_status_on_zero: bool = False

    @classmethod
    def from_raw(cls, raw: Optional[dict]) -> "ResetPolicy":
        raw = raw or {}
        return cls(
            mode=raw.get("mode", "wait_plc_zero"),
            clear_status_on_zero=bool(raw.get("clear_status_on_zero", False)),
        )


@dataclass
class MultiFrameChannel:
    """Multi-frame inspection channel config."""

    name: str = ""
    camera_id: str = ""
    model_id: str = ""  # fallback model for frame_plan entries
    frame_count: int = 0

    # Word device addresses.
    cmd_addr: str = "ED0"       # PLC -> VModule command value.
    status_addr: str = "EW0"    # Per-frame status and final result.
    result_addr: str = ""       # Optional legacy separate result register.
    count_addr: str = ""        # Optional total defect count.
    time_addr: str = ""         # Optional total elapsed time in ms.
    finalize_delay_ms: int = 50 # Keep the last frame ACK visible before final result.

    frame_plan: List[Any] = field(default_factory=list)
    result_policy: Dict[str, Any] = field(default_factory=dict)
    save_policy: Dict[str, Any] = field(default_factory=lambda: {"mode": "all"})
    reset_policy: Dict[str, Any] = field(default_factory=dict)

    # Runtime state.
    _frames: Dict[int, np.ndarray] = field(default_factory=dict, repr=False)
    _frame_results: Dict[int, dict] = field(default_factory=dict, repr=False)
    _frame_paths: Dict[int, str] = field(default_factory=dict, repr=False)
    _busy: bool = field(default=False, repr=False)
    _last_cmd: int = field(default=0, repr=False)
    _cycle_id: str = field(default="", repr=False)
    _cycle_started_at: float = field(default=0, repr=False)
    _awaiting_reset: bool = field(default=False, repr=False)
    _pending_finalize: bool = field(default=False, repr=False)
    _finalize_due_at: float = field(default=0, repr=False)
    _pending_task: Optional[asyncio.Task] = field(default=None, repr=False)

    def normalized_plan(self) -> List[FramePlanItem]:
        if self.frame_plan:
            return [FramePlanItem.from_raw(item, self.model_id) for item in self.frame_plan]
        count = self.frame_count or 3
        return [FramePlanItem(command=i, model_id=self.model_id) for i in range(1, count + 1)]

    def plan_by_command(self) -> Dict[int, FramePlanItem]:
        return {item.command: item for item in self.normalized_plan()}

    def status_code_for(self, command: int) -> int:
        for idx, item in enumerate(self.normalized_plan(), start=1):
            if item.command == command:
                return item.status_code if item.status_code is not None else 10 + idx
        return 10 + command

    @property
    def expected_commands(self) -> set[int]:
        return set(self.plan_by_command().keys())

    @property
    def effective_frame_count(self) -> int:
        return len(self.expected_commands)


class MultiFrameProgramBlock:
    """Register-polling multi-frame inspection block."""

    def __init__(self, camera_manager=None, inference_manager=None):
        self._camera_mgr = camera_manager
        self._inference_mgr = inference_manager
        self._channels: List[MultiFrameChannel] = []
        self._strategy_getter = None  # Legacy callable(model_id) -> {class: code}

    def set_strategy_getter(self, fn):
        """Set legacy strategy getter for old presets."""
        self._strategy_getter = fn

    def add_channel(self, channel: MultiFrameChannel):
        self._channels.append(channel)
        logger.info(
            "MultiFrame channel [%s]: cam=%s frames=%s cmd=%s status=%s",
            channel.name,
            channel.camera_id,
            sorted(channel.expected_commands),
            channel.cmd_addr,
            channel.status_addr,
        )

    async def __call__(self, memory: SoftDeviceMemory):
        for ch in self._channels:
            await self._process_channel(memory, ch)

    async def _process_channel(self, memory: SoftDeviceMemory, ch: MultiFrameChannel):
        if ch._busy:
            loguru_logger.trace("[{}] busy, scan skipped", ch.name)
            return

        if ch._pending_finalize:
            if time.perf_counter() >= ch._finalize_due_at:
                ch._busy = True
                ch._pending_task = asyncio.create_task(self._run_finalize(memory, ch))
            return

        cmd_val = memory.read_word(SoftDeviceAddress.parse(ch.cmd_addr))

        if cmd_val == 0:
            if ch._last_cmd != 0:
                loguru_logger.trace("[{}] command reset observed: {} -> 0", ch.name, ch._last_cmd)
            ch._last_cmd = 0
            if ch._awaiting_reset:
                self._reset_cycle_state(ch, memory)
            return

        if cmd_val == ch._last_cmd:
            return
        ch._last_cmd = cmd_val

        if ch._awaiting_reset:
            logger.warning("[%s] awaiting reset, ignored command: %s", ch.name, cmd_val)
            return

        plan = ch.plan_by_command()
        frame = plan.get(cmd_val)
        if frame is None:
            logger.warning("[%s] invalid command value: %s expected=%s", ch.name, cmd_val, sorted(plan))
            return

        if not ch._cycle_id:
            ch._cycle_id = self._new_cycle_id(ch)
            ch._cycle_started_at = time.perf_counter()
            loguru_logger.info("[{}] cycle {} started by command {}", ch.name, ch._cycle_id, cmd_val)

        ch._busy = True
        ch._pending_task = asyncio.create_task(self._run_frame_command(memory, ch, frame))

    async def _run_frame_command(
        self,
        memory: SoftDeviceMemory,
        ch: MultiFrameChannel,
        frame: FramePlanItem,
    ):
        try:
            await self._capture_predict_and_ack(memory, ch, frame)

            if ch.expected_commands.issubset(ch._frames.keys()):
                delay_s = max(0, int(ch.finalize_delay_ms)) / 1000
                ch._pending_finalize = True
                ch._finalize_due_at = time.perf_counter() + delay_s
                loguru_logger.trace(
                    "[{}] cycle={} finalization scheduled in {}ms",
                    ch.name,
                    ch._cycle_id,
                    int(delay_s * 1000),
                )
            ch._busy = False
        except Exception:
            loguru_logger.exception("[{}] multi-frame command failed", ch.name)
            ch._awaiting_reset = True
            ch._busy = False

    async def _run_finalize(self, memory: SoftDeviceMemory, ch: MultiFrameChannel):
        try:
            await self._finalize_cycle(memory, ch)
        except Exception:
            loguru_logger.exception("[{}] multi-frame finalization failed", ch.name)
            ch._pending_finalize = False
            ch._finalize_due_at = 0
            ch._awaiting_reset = True
            ch._busy = False

    async def _capture_predict_and_ack(
        self,
        memory: SoftDeviceMemory,
        ch: MultiFrameChannel,
        frame: FramePlanItem,
    ):
        command = frame.command
        frame_id = f"cmd{command}"
        loguru_logger.trace(
            "[{}] cycle={} command={} camera={} model={}",
            ch.name,
            ch._cycle_id,
            command,
            ch.camera_id,
            frame.model_id,
        )

        image = await self._capture(ch, frame)
        if image is None:
            logger.error("[%s] frame command %s capture failed", ch.name, command)
            memory.write_word(SoftDeviceAddress.parse(ch.status_addr), self._result_policy(ch).error_code)
            raise RuntimeError(f"capture failed for command {command}")

        ch._frames[command] = image
        try:
            from app.api.camera import store_frame
            store_frame(ch.camera_id, image)
        except Exception:
            pass

        result, inference_ms = await self._predict_timed(frame.model_id, image)
        if result.get("error"):
            logger.error("[%s] frame command %s inference failed: %s", ch.name, command, result.get("error"))
            memory.write_word(SoftDeviceAddress.parse(ch.status_addr), self._result_policy(ch).error_code)
            ch._frame_results[command] = result
            raise RuntimeError(f"inference failed for command {command}: {result.get('error')}")

        ch._frame_results[command] = result or {"detections": []}

        frame_path = await self._save_frame_if_needed(ch, frame_id, image)
        if frame_path:
            ch._frame_paths[command] = frame_path

        await self._save_frame_result_if_needed(ch, frame_id, frame, result, inference_ms)

        status_code = ch.status_code_for(command)
        memory.write_word(SoftDeviceAddress.parse(ch.status_addr), status_code)
        logger.info(
            "[%s] frame command %s captured, model=%s status=%s inference=%sms",
            ch.name,
            command,
            frame.model_id or ch.model_id,
            status_code,
            inference_ms,
        )

    async def _finalize_cycle(self, memory: SoftDeviceMemory, ch: MultiFrameChannel):
        ch._pending_finalize = False
        ch._finalize_due_at = 0
        start = ch._cycle_started_at or time.perf_counter()
        all_detections = []
        for command in sorted(ch._frame_results):
            all_detections.extend((ch._frame_results.get(command) or {}).get("detections", []))

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        result_code = self._evaluate_strategy(ch, all_detections)
        ok_code = self._result_policy(ch).result_codes.get("ok", 7)
        is_ok = result_code == ok_code

        memory.write_word(SoftDeviceAddress.parse(ch.status_addr), result_code)
        if ch.result_addr:
            memory.write_word(SoftDeviceAddress.parse(ch.result_addr), result_code)
        self._write_optional_word(memory, ch.count_addr, len(all_detections), ch.name)
        self._write_optional_word(memory, ch.time_addr, elapsed_ms, ch.name)

        if not is_ok:
            await self._save_ng_frames_if_needed(ch)

        summary = {
            "cycle_id": ch._cycle_id,
            "channel": ch.name,
            "camera_id": ch.camera_id,
            "commands": sorted(ch._frames),
            "result_code": result_code,
            "is_ok": is_ok,
            "defect_count": len(all_detections),
            "detections": all_detections,
            "frame_paths": ch._frame_paths,
            "elapsed_ms": elapsed_ms,
            "created_at": datetime.now().isoformat(),
        }
        await self._save_summary_if_needed(ch, summary)

        image_path = ""
        if ch._frame_paths:
            image_path = ch._frame_paths[sorted(ch._frame_paths)[-1]]

        asyncio.create_task(save_detection_record(
            channel_name=ch.name,
            camera_id=ch.camera_id,
            model_id=",".join(sorted({item.model_id for item in ch.normalized_plan() if item.model_id})),
            is_ok=is_ok,
            defect_count=len(all_detections),
            result_json=summary,
            image_path=image_path,
            inference_ms=elapsed_ms,
        ))

        await self._run_cycle_rules(ch, summary)

        logger.info(
            "[%s] cycle %s done: result=%s defects=%s time=%sms",
            ch.name,
            ch._cycle_id,
            result_code,
            len(all_detections),
            elapsed_ms,
        )

        reset_policy = self._reset_policy(ch)
        if reset_policy.mode == "immediate":
            self._reset_cycle_state(ch, memory)
        elif reset_policy.mode == "none":
            ch._busy = False
        else:
            ch._awaiting_reset = True
            ch._busy = False

    def _reset_cycle_state(self, ch: MultiFrameChannel, memory: SoftDeviceMemory):
        reset_policy = self._reset_policy(ch)
        if reset_policy.clear_status_on_zero:
            try:
                memory.write_word(SoftDeviceAddress.parse(ch.status_addr), 0)
            except Exception as e:
                logger.warning("[%s] failed clearing status on reset: %s", ch.name, e)

        loguru_logger.debug("[{}] reset cycle state: {}", ch.name, ch._cycle_id)
        ch._frames.clear()
        ch._frame_results.clear()
        ch._frame_paths.clear()
        ch._cycle_id = ""
        ch._cycle_started_at = 0
        ch._awaiting_reset = False
        ch._pending_finalize = False
        ch._finalize_due_at = 0
        ch._busy = False
        ch._pending_task = None

    def _new_cycle_id(self, ch: MultiFrameChannel) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        safe_name = (ch.name or "channel").replace(" ", "_")
        return f"{safe_name}_{timestamp}_{uuid.uuid4().hex[:6]}"

    def _result_policy(self, ch: MultiFrameChannel) -> ResultPolicy:
        if ch.result_policy:
            return ResultPolicy.from_raw(ch.result_policy)

        # Backward compatibility with older class->code strategy maps.
        if self._strategy_getter and ch.model_id:
            strategy = self._strategy_getter(ch.model_id)
            if strategy:
                defect_code_map = {}
                for cls_name, code in strategy.items():
                    code = int(code)
                    if code in (2, 6):
                        defect_code_map[cls_name] = "ng_repairable"
                    elif code in (1, 7):
                        defect_code_map[cls_name] = "ok"
                    else:
                        defect_code_map[cls_name] = "ng_fatal"
                return ResultPolicy(defect_code_map={**DEFAULT_DEFECT_CODE_MAP, **defect_code_map})

        return ResultPolicy.from_raw(None)

    def _save_policy(self, ch: MultiFrameChannel) -> SavePolicy:
        return SavePolicy.from_raw(ch.save_policy)

    def _reset_policy(self, ch: MultiFrameChannel) -> ResetPolicy:
        return ResetPolicy.from_raw(ch.reset_policy)

    async def _save_frame_if_needed(
        self,
        ch: MultiFrameChannel,
        frame_id: str,
        image: np.ndarray,
    ) -> str:
        policy = self._save_policy(ch)
        if policy.mode in ("off", "ng"):
            return ""
        return await save_cycle_frame(
            ch._cycle_id,
            frame_id,
            ch.camera_id,
            image,
            ext=policy.image_format,
        )

    async def _save_summary_if_needed(self, ch: MultiFrameChannel, summary: dict):
        policy = self._save_policy(ch)
        if policy.mode == "off" or not policy.save_json:
            return
        if policy.mode == "ng" and summary.get("is_ok"):
            return
        await save_cycle_json(ch._cycle_id, "summary", summary)

    async def _save_ng_frames_if_needed(self, ch: MultiFrameChannel):
        policy = self._save_policy(ch)
        if policy.mode != "ng":
            return
        for command, image in sorted(ch._frames.items()):
            if command in ch._frame_paths:
                continue
            ch._frame_paths[command] = await save_cycle_frame(
                ch._cycle_id,
                f"cmd{command}",
                ch.camera_id,
                image,
                ext=policy.image_format,
            )

    async def _run_cycle_rules(self, ch: MultiFrameChannel, summary: dict):
        try:
            from app.core.rule import rule_engine

            trigger_source = f"{ch.camera_id}.capture_done"
            context = {
                "cycle_id": summary.get("cycle_id"),
                "channel": ch.name,
                "camera_id": ch.camera_id,
                "is_ok": summary.get("is_ok"),
                "defect_count": summary.get("defect_count", 0),
                "result_code": summary.get("result_code"),
                "detections": summary.get("detections", []),
                "frame_paths": summary.get("frame_paths", {}),
                "elapsed_ms": summary.get("elapsed_ms", 0),
                "result": summary,
            }
            outcome = await rule_engine.evaluate_and_execute(trigger_source, context)
            if outcome.get("matched"):
                logger.info("[%s] rules executed: %s actions", ch.name, outcome.get("matched"))
        except Exception as exc:
            logger.warning("[%s] rule evaluation failed: %s", ch.name, exc)

    async def _save_frame_result_if_needed(
        self,
        ch: MultiFrameChannel,
        frame_id: str,
        frame: FramePlanItem,
        result: dict,
        inference_ms: int,
    ):
        policy = self._save_policy(ch)
        if policy.mode != "all" or not policy.save_json:
            return
        payload = {
            "cycle_id": ch._cycle_id,
            "frame_id": frame_id,
            "command": frame.command,
            "label": frame.label,
            "camera_id": ch.camera_id,
            "model_id": frame.model_id or ch.model_id,
            "status_code": ch.status_code_for(frame.command),
            "inference_ms": inference_ms,
            "result": result,
            "created_at": datetime.now().isoformat(),
        }
        await save_cycle_json(ch._cycle_id, f"{frame_id}_inference", payload)

    def _write_optional_word(self, memory: SoftDeviceMemory, addr: str, value: int, channel_name: str):
        if not addr:
            return
        try:
            memory.write_word(SoftDeviceAddress.parse(addr), value)
        except Exception as e:
            logger.warning("[%s] failed writing %s=%s: %s", channel_name, addr, value, e)

    def _evaluate_strategy(self, ch: MultiFrameChannel, detections: list) -> int:
        policy = self._result_policy(ch)
        if not detections:
            return policy.result_codes["ok"]

        priority_map = {name: idx for idx, name in enumerate(policy.defect_priority)}
        worst_class = ""
        worst_priority = 9999
        for det in detections:
            cls_name = det.get("class", "")
            priority = priority_map.get(cls_name, 999)
            if priority < worst_priority:
                worst_priority = priority
                worst_class = cls_name

        level = policy.defect_code_map.get(worst_class, "ng_fatal")
        return policy.result_codes.get(level, policy.result_codes["ng_fatal"])

    async def _capture(self, ch: MultiFrameChannel, frame: FramePlanItem) -> Optional[np.ndarray]:
        if self._camera_mgr is None:
            return np.zeros((480, 640, 3), dtype=np.uint8)

        try:
            if frame.exposure is not None:
                vcam = self._camera_mgr.get_virtual_camera(ch.camera_id)
                if vcam:
                    old_exposure = vcam.exposure
                    vcam.exposure = frame.exposure
                    try:
                        return await self._camera_mgr.capture(ch.camera_id)
                    finally:
                        vcam.exposure = old_exposure
            return await self._camera_mgr.capture(ch.camera_id)
        except Exception as e:
            logger.error("Camera [%s] capture failed: %s", ch.camera_id, e)
            return None

    async def _predict_timed(self, model_id: str, image: np.ndarray) -> tuple[dict, int]:
        start = time.perf_counter()
        result = await self._predict(model_id, image)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        if result and result.get("inference_time"):
            try:
                elapsed_ms = int(result["inference_time"])
            except Exception:
                pass
        return result or {"detections": []}, elapsed_ms

    async def _predict(self, model_id: str, image: np.ndarray) -> Optional[dict]:
        if self._inference_mgr is None:
            return {"detections": [], "inference_time": 0}
        if not model_id:
            logger.warning("No model configured for frame, returning empty result")
            return {"detections": [], "inference_time": 0, "warning": "no_model"}
        try:
            return await self._inference_mgr.predict(model_id, image)
        except Exception as e:
            logger.error("Model [%s] predict failed: %s", model_id, e)
            return {"detections": [], "inference_time": 0, "error": str(e)}
