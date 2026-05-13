"""Field verifier for the dual-USB multi-frame baseline workflow.

This script does not require a PLC. It validates the baseline preset, opens the
two USB cameras, then drives ED0/EW0 and ED2/EW2 in soft-device memory.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import sys
from pathlib import Path

import cv2


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.core.camera.manager import CameraManager
from app.core.detection.multiframe import MultiFrameChannel, MultiFrameProgramBlock
from app.core.softdevice.memory import SoftDeviceMemory


def load_preset(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_preset(preset: dict):
    expected_mappings = {
        ("D60", "ED0"),
        ("D61", "EW0"),
        ("D62", "ED2"),
        ("D63", "EW2"),
    }
    actual_mappings = {
        (item["plc_addr"], item["vmodule_addr"])
        for item in preset.get("io_mappings", [])
    }
    if actual_mappings != expected_mappings:
        raise AssertionError(f"I/O mapping mismatch: {actual_mappings}")

    cameras = {item["camera_id"]: item for item in preset.get("cameras", [])}
    if cameras["usb_cam1"]["config"]["connection"]["index"] != 0:
        raise AssertionError("usb_cam1 must use OpenCV index 0")
    if cameras["usb_cam2"]["config"]["connection"]["index"] != 1:
        raise AssertionError("usb_cam2 must use OpenCV index 1")
    if not cameras["usb_cam1"].get("auto_open") or not cameras["usb_cam2"].get("auto_open"):
        raise AssertionError("usb_cam1 and usb_cam2 must set auto_open=true")

    channels = {item["name"]: item for item in preset.get("multiframe_channels", [])}
    required = {
        "cam1_baseline": ("ED0", "EW0"),
        "cam2_baseline": ("ED2", "EW2"),
    }
    for name, (cmd_addr, status_addr) in required.items():
        ch = channels[name]
        if ch["cmd_addr"] != cmd_addr or ch["status_addr"] != status_addr:
            raise AssertionError(f"{name} must use {cmd_addr}->{status_addr}")
        commands = [item["command"] for item in ch["frame_plan"]]
        statuses = [item["status_code"] for item in ch["frame_plan"]]
        if commands != [1, 2] or statuses != [11, 12]:
            raise AssertionError(f"{name} frame plan must be commands 1/2 and ACK 11/12")


def verify_raw_usb(indices: list[int]):
    results = []
    for index in indices:
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        opened = cap.isOpened()
        ret = False
        shape = None
        if opened:
            ret, frame = cap.read()
            if ret:
                shape = tuple(frame.shape)
        cap.release()
        results.append({"index": index, "opened": opened, "read": ret, "shape": shape})
        if not opened or not ret or shape is None:
            raise AssertionError(f"USB camera index {index} failed: opened={opened} read={ret} shape={shape}")
    return results


async def add_preset_cameras(camera_manager: CameraManager, preset: dict):
    for cam in preset.get("cameras", []):
        config = dict(cam.get("config", {}))
        if "exposure" in cam:
            config["exposure"] = cam["exposure"]
        if "gain" in cam:
            config["gain"] = cam["gain"]
        ok = await camera_manager.add_camera(cam["camera_id"], cam.get("camera_type", "usb"), config)
        if not ok:
            raise AssertionError(f"Failed to add camera {cam['camera_id']}")
        if cam.get("auto_open", False):
            opened = await camera_manager.open_camera(cam["camera_id"])
            if not opened:
                raise AssertionError(f"Failed to open camera {cam['camera_id']}")


async def run_cycle(block: MultiFrameProgramBlock, mem: SoftDeviceMemory, channel, cmd_addr: str, status_addr: str):
    mem.write(cmd_addr, 1)
    await block(mem)
    if channel._pending_task:
        await channel._pending_task
    if mem.read(status_addr) != 11:
        raise AssertionError(f"{status_addr} expected 11 after command 1, got {mem.read(status_addr)}")

    mem.write(cmd_addr, 0)
    await block(mem)

    mem.write(cmd_addr, 2)
    await block(mem)
    if channel._pending_task:
        await channel._pending_task
    if mem.read(status_addr) != 12:
        raise AssertionError(f"{status_addr} expected 12 after command 2, got {mem.read(status_addr)}")

    await asyncio.sleep(max(0, channel.finalize_delay_ms) / 1000 + 0.02)
    await block(mem)
    if channel._pending_task:
        await channel._pending_task
    final = mem.read(status_addr)
    if final not in (5, 6, 7):
        raise AssertionError(f"{status_addr} expected final 5/6/7, got {final}")

    mem.write(cmd_addr, 0)
    await block(mem)
    if channel._cycle_id:
        raise AssertionError(f"{channel.name} did not reset after PLC zero")
    return final


async def verify_workflow(preset: dict):
    camera_manager = CameraManager()
    mem = SoftDeviceMemory()
    block = MultiFrameProgramBlock(camera_manager=camera_manager, inference_manager=None)
    channels = []

    await add_preset_cameras(camera_manager, preset)
    try:
        for raw in preset.get("multiframe_channels", []):
            data = copy.deepcopy(raw)
            data["save_policy"] = {"mode": "off"}
            data["finalize_delay_ms"] = 0
            ch = MultiFrameChannel(**data)
            channels.append(ch)
            block.add_channel(ch)

        cam1 = next(ch for ch in channels if ch.name == "cam1_baseline")
        cam2 = next(ch for ch in channels if ch.name == "cam2_baseline")

        cam1_result = await run_cycle(block, mem, cam1, "ED0", "EW0")
        cam2_result = await run_cycle(block, mem, cam2, "ED2", "EW2")

        mem.write("ED0", 1)
        mem.write("ED2", 1)
        await block(mem)
        await asyncio.gather(cam1._pending_task, cam2._pending_task)
        if mem.read("EW0") != 11 or mem.read("EW2") != 11:
            raise AssertionError(f"parallel ACK failed: EW0={mem.read('EW0')} EW2={mem.read('EW2')}")

        return {"cam1_final": cam1_result, "cam2_final": cam2_result, "parallel_ack": [mem.read("EW0"), mem.read("EW2")]}
    finally:
        await camera_manager.close_all()


async def main():
    parser = argparse.ArgumentParser(description="Verify VModule dual USB multi-frame baseline")
    parser.add_argument(
        "--preset",
        default=str(ROOT / "presets" / "dual_usb_multiframe_baseline.json"),
        help="Path to baseline preset JSON",
    )
    args = parser.parse_args()

    preset = load_preset(Path(args.preset))
    validate_preset(preset)
    usb_results = verify_raw_usb([0, 1])
    workflow = await verify_workflow(preset)

    print("Preset: OK")
    for result in usb_results:
        print(f"USB index={result['index']} opened={result['opened']} read={result['read']} shape={result['shape']}")
    print(f"Workflow: cam1_final={workflow['cam1_final']} cam2_final={workflow['cam2_final']} parallel_ack={workflow['parallel_ack']}")


if __name__ == "__main__":
    asyncio.run(main())
