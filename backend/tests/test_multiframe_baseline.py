"""Baseline multi-frame polling workflow tests.

These tests pin the two-camera / four-register workflow used for field
acceptance without requiring a PLC or physical cameras.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings
from app.core.detection import multiframe as multiframe_mod
from app.core.detection.multiframe import MultiFrameChannel, MultiFrameProgramBlock
from app.core.softdevice.memory import SoftDeviceMemory


ROOT = Path(__file__).resolve().parents[2]
BASELINE_PRESET = ROOT / "presets" / "dual_usb_multiframe_baseline.json"


class FakeInference:
    def __init__(self, responses: dict[str, dict]):
        self.responses = responses
        self.calls: list[str] = []

    async def predict(self, model_id, image):
        self.calls.append(model_id)
        return self.responses.get(model_id, {"detections": [], "inference_time": 0})


async def run_two_frame_cycle(
    block: MultiFrameProgramBlock,
    mem: SoftDeviceMemory,
    ch: MultiFrameChannel,
    cmd_addr: str,
    status_addr: str,
):
    mem.write(cmd_addr, 1)
    await block(mem)
    assert ch._pending_task is not None
    await ch._pending_task
    assert mem.read(status_addr) == 11

    mem.write(cmd_addr, 0)
    await block(mem)

    mem.write(cmd_addr, 2)
    await block(mem)
    assert ch._pending_task is not None
    await ch._pending_task
    assert mem.read(status_addr) == 12

    await block(mem)
    assert ch._pending_task is not None
    await ch._pending_task
    return mem.read(status_addr)


def make_two_frame_channel(**overrides) -> MultiFrameChannel:
    params = {
        "name": "baseline",
        "camera_id": "usb_cam1",
        "cmd_addr": "ED0",
        "status_addr": "EW0",
        "count_addr": "VD10",
        "time_addr": "VD11",
        "frame_plan": [
            {"command": 1, "model_id": "frame1_model", "status_code": 11},
            {"command": 2, "model_id": "frame2_model", "status_code": 12},
        ],
        "finalize_delay_ms": 0,
        "save_policy": {"mode": "off"},
    }
    params.update(overrides)
    return MultiFrameChannel(**params)


def test_baseline_preset_contract():
    preset = json.loads(BASELINE_PRESET.read_text(encoding="utf-8"))

    mappings = {
        (item["plc_addr"], item["vmodule_addr"])
        for item in preset["io_mappings"]
    }
    assert mappings == {
        ("D60", "ED0"),
        ("D61", "EW0"),
        ("D62", "ED2"),
        ("D63", "EW2"),
    }

    cameras = {item["camera_id"]: item for item in preset["cameras"]}
    assert cameras["usb_cam1"]["config"]["connection"]["index"] == 0
    assert cameras["usb_cam2"]["config"]["connection"]["index"] == 1
    assert cameras["usb_cam1"]["auto_open"] is True
    assert cameras["usb_cam2"]["auto_open"] is True

    channels = {item["name"]: item for item in preset["multiframe_channels"]}
    assert channels["cam1_baseline"]["cmd_addr"] == "ED0"
    assert channels["cam1_baseline"]["status_addr"] == "EW0"
    assert channels["cam2_baseline"]["cmd_addr"] == "ED2"
    assert channels["cam2_baseline"]["status_addr"] == "EW2"
    for channel in channels.values():
        assert [item["command"] for item in channel["frame_plan"]] == [1, 2]
        assert [item["status_code"] for item in channel["frame_plan"]] == [11, 12]
        assert channel["reset_policy"]["mode"] == "wait_plc_zero"
        assert channel["save_policy"]["mode"] == "all"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("frame1", "frame2", "expected"),
    [
        ([], [], 7),
        ([{"class": "YW"}], [], 6),
        ([{"class": "CL"}], [], 5),
        ([{"class": "JS"}], [], 5),
        ([{"class": "HH"}], [], 5),
        ([{"class": "YW"}], [{"class": "JS"}], 5),
    ],
)
async def test_visflowz_result_semantics(frame1, frame2, expected, monkeypatch):
    async def noop_record(**kwargs):
        return None

    monkeypatch.setattr(multiframe_mod, "save_detection_record", noop_record)
    inference = FakeInference({
        "frame1_model": {"detections": frame1, "inference_time": 1},
        "frame2_model": {"detections": frame2, "inference_time": 1},
    })
    block = MultiFrameProgramBlock(inference_manager=inference)
    mem = SoftDeviceMemory()
    ch = make_two_frame_channel()
    block.add_channel(ch)

    assert await run_two_frame_cycle(block, mem, ch, "ED0", "EW0") == expected
    assert inference.calls == ["frame1_model", "frame2_model"]


@pytest.mark.asyncio
async def test_ignores_duplicate_command_until_plc_reset(monkeypatch):
    async def noop_record(**kwargs):
        return None

    monkeypatch.setattr(multiframe_mod, "save_detection_record", noop_record)
    block = MultiFrameProgramBlock()
    mem = SoftDeviceMemory()
    ch = make_two_frame_channel(frame_plan=[{"command": 1, "status_code": 11}])
    block.add_channel(ch)

    mem.write("ED0", 1)
    await block(mem)
    await ch._pending_task
    assert mem.read("EW0") == 11
    assert set(ch._frames) == {1}

    await block(mem)
    await ch._pending_task
    assert mem.read("EW0") == 7
    assert ch._awaiting_reset is True

    mem.write("ED0", 1)
    await block(mem)
    assert set(ch._frames) == {1}
    assert ch._awaiting_reset is True

    mem.write("ED0", 0)
    await block(mem)
    assert ch._cycle_id == ""
    assert ch._frames == {}


@pytest.mark.asyncio
async def test_inference_failure_writes_error_status_and_logs(caplog):
    inference = FakeInference({
        "frame1_model": {"detections": [], "inference_time": 0, "error": "model not loaded"},
    })
    block = MultiFrameProgramBlock(inference_manager=inference)
    mem = SoftDeviceMemory()
    ch = make_two_frame_channel(frame_plan=[{"command": 1, "model_id": "frame1_model", "status_code": 11}])
    block.add_channel(ch)

    mem.write("ED0", 1)
    await block(mem)
    await ch._pending_task

    assert mem.read("EW0") == 255
    assert ch._awaiting_reset is True
    assert "inference failed" in caplog.text


@pytest.mark.asyncio
async def test_save_policy_all_writes_cycle_images_and_json(tmp_path, monkeypatch):
    async def noop_record(**kwargs):
        return None

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(multiframe_mod, "save_detection_record", noop_record)

    block = MultiFrameProgramBlock()
    mem = SoftDeviceMemory()
    ch = make_two_frame_channel(save_policy={"mode": "all", "image_format": "jpg", "save_json": True})
    block.add_channel(ch)

    assert await run_two_frame_cycle(block, mem, ch, "ED0", "EW0") == 7

    files = {path.name for path in tmp_path.rglob("*") if path.is_file()}
    assert {"cmd1.jpg", "cmd2.jpg", "cmd1_inference.json", "cmd2_inference.json", "summary.json"} <= files

    summary_path = next(tmp_path.rglob("summary.json"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["cycle_id"].startswith("baseline_")
    assert summary["commands"] == [1, 2]
    assert summary["result_code"] == 7
