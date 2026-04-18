"""
Multi-frame register-polling inspection program block

Workflow per camera channel:
  1. Poll command register (ED, mapped from PLC e.g. D30)
  2. Value 1/2/3 -> capture frame 1/2/3
  3. Write status to result register (EW, mapped to PLC e.g. D31):
     11=frame1 done, 12=frame2 done, 13=frame3 done
  4. After all frames captured -> run inference on each
  5. Determine worst strategy code -> write to strategy register (EW)
  6. Reset command register to 0

Register convention per channel:
  cmd_addr   (ED)  - PLC writes 1/2/3 to trigger frame capture, VModule resets to 0
  status_addr(EW)  - VModule writes 11/12/13 for frame status, 20=inferring, 0=idle
  result_addr(EW)  - strategy code: 0=idle, 1=OK, 2=repairable, 3=unrepairable
  count_addr (EW)  - total defect count across all frames
  time_addr  (EW)  - total inference time ms
"""

from __future__ import annotations
import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from app.core.softdevice.memory import SoftDeviceMemory, SoftDeviceAddress

logger = logging.getLogger("vmodule.detection.multiframe")


@dataclass
class MultiFrameChannel:
    """Multi-frame inspection channel config"""
    name: str = ""
    camera_id: str = ""
    model_id: str = ""
    frame_count: int = 3

    # Register addresses (word devices)
    cmd_addr: str = "ED0"        # command: 1/2/3 = capture frame N
    status_addr: str = "EW0"     # status: 11/12/13=frameN done, 20=inferring, 0=idle
    result_addr: str = "EW1"     # strategy: 1=OK, 2=repairable, 3=unrepairable
    count_addr: str = "EW2"      # total defect count
    time_addr: str = "EW3"       # total inference time ms

    # Internal runtime state
    _frames: Dict[int, np.ndarray] = field(default_factory=dict, repr=False)
    _busy: bool = field(default=False, repr=False)


class MultiFrameProgramBlock:
    """Register-polling multi-frame inspection.

    Each scan cycle:
      - Read cmd register for each channel
      - If cmd=1/2/3 and not busy -> capture that frame, write status, reset cmd
      - If all frames collected -> launch async inference
    """

    def __init__(self, camera_manager=None, inference_manager=None):
        self._camera_mgr = camera_manager
        self._inference_mgr = inference_manager
        self._channels: List[MultiFrameChannel] = []
        self._strategy_getter = None  # callable(model_id) -> {class: code}

    def set_strategy_getter(self, fn):
        """Set function to get strategy map: fn(model_id) -> dict"""
        self._strategy_getter = fn

    def add_channel(self, channel: MultiFrameChannel):
        self._channels.append(channel)
        logger.info(
            f"MultiFrame channel [{channel.name}]: "
            f"cam={channel.camera_id} model={channel.model_id} "
            f"frames={channel.frame_count} cmd={channel.cmd_addr}"
        )

    async def __call__(self, memory: SoftDeviceMemory):
        for ch in self._channels:
            await self._process_channel(memory, ch)

    async def _process_channel(self, memory: SoftDeviceMemory, ch: MultiFrameChannel):
        if ch._busy:
            return

        # Read command register
        cmd_val = memory.read_word(SoftDeviceAddress.parse(ch.cmd_addr))
        if cmd_val == 0:
            return
        if cmd_val < 1 or cmd_val > ch.frame_count:
            return

        frame_idx = cmd_val  # 1-based

        # Reset command immediately (tell PLC we received it)
        memory.write_word(SoftDeviceAddress.parse(ch.cmd_addr), 0)

        # Capture frame
        ch._busy = True
        try:
            image = await self._capture(ch)
            if image is not None:
                ch._frames[frame_idx] = image
                # Store frame for UI display
                try:
                    from app.api.camera import store_frame
                    store_frame(ch.camera_id, image)
                except Exception:
                    pass

                # Write status: 10 + frame_idx (11, 12, 13)
                status_code = 10 + frame_idx
                memory.write_word(SoftDeviceAddress.parse(ch.status_addr), status_code)
                logger.info(f"[{ch.name}] Frame {frame_idx} captured, status={status_code}")
            else:
                logger.error(f"[{ch.name}] Frame {frame_idx} capture failed")
                memory.write_word(SoftDeviceAddress.parse(ch.status_addr), 90 + frame_idx)

            # Check if all frames collected
            if len(ch._frames) >= ch.frame_count:
                logger.info(f"[{ch.name}] All {ch.frame_count} frames collected, starting inference")
                memory.write_word(SoftDeviceAddress.parse(ch.status_addr), 20)
                asyncio.create_task(self._run_inference(memory, ch))
            else:
                ch._busy = False
        except Exception as e:
            logger.error(f"[{ch.name}] Capture error: {e}")
            ch._busy = False

    async def _run_inference(self, memory: SoftDeviceMemory, ch: MultiFrameChannel):
        """Run inference on all collected frames, determine strategy, write results."""
        start = time.perf_counter()
        try:
            all_detections = []
            for idx in sorted(ch._frames.keys()):
                image = ch._frames[idx]
                result = await self._predict(ch, image)
                if result:
                    dets = result.get("detections", [])
                    all_detections.extend(dets)

            elapsed_ms = int((time.perf_counter() - start) * 1000)

            # Determine strategy code from detections
            strategy_code = self._evaluate_strategy(ch, all_detections)

            # Write results
            memory.write_word(SoftDeviceAddress.parse(ch.result_addr), strategy_code)
            memory.write_word(SoftDeviceAddress.parse(ch.count_addr), len(all_detections))
            memory.write_word(SoftDeviceAddress.parse(ch.time_addr), elapsed_ms)
            memory.write_word(SoftDeviceAddress.parse(ch.status_addr), 0)  # idle

            logger.info(
                f"[{ch.name}] Inference done: strategy={strategy_code} "
                f"defects={len(all_detections)} time={elapsed_ms}ms"
            )
        except Exception as e:
            logger.error(f"[{ch.name}] Inference error: {e}")
            memory.write_word(SoftDeviceAddress.parse(ch.result_addr), 0)
            memory.write_word(SoftDeviceAddress.parse(ch.status_addr), 99)  # error
        finally:
            ch._frames.clear()
            ch._busy = False

    def _evaluate_strategy(self, ch: MultiFrameChannel, detections: list) -> int:
        """Map detection classes to strategy codes, return worst (highest) code.

        Default: no detections = 1 (OK)
        Strategy map example: {'ok':1, 'repairable':2, 'unrepairable':3}
        """
        if not detections:
            return 1  # OK

        strategy_map = {}
        if self._strategy_getter:
            strategy_map = self._strategy_getter(ch.model_id)

        if not strategy_map:
            # No strategy configured -> any detection = unrepairable
            return 3

        worst = 1
        for det in detections:
            cls_name = det.get("class", "")
            code = strategy_map.get(cls_name, 3)  # unknown class -> worst
            if code > worst:
                worst = code
        return worst

    async def _capture(self, ch: MultiFrameChannel) -> Optional[np.ndarray]:
        if self._camera_mgr is None:
            return np.zeros((480, 640, 3), dtype=np.uint8)
        try:
            return await self._camera_mgr.capture(ch.camera_id)
        except Exception as e:
            logger.error(f"Camera [{ch.camera_id}] capture failed: {e}")
            return None

    async def _predict(self, ch: MultiFrameChannel, image: np.ndarray) -> Optional[dict]:
        if self._inference_mgr is None:
            return {"detections": [], "inference_time": 0}
        try:
            return await self._inference_mgr.predict(ch.model_id, image)
        except Exception as e:
            logger.error(f"Model [{ch.model_id}] predict failed: {e}")
            return None
