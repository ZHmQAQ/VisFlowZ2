"""
Camera management REST API + image serving
"""
import asyncio
import base64
import io
import logging
import time
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.camera.manager import camera_manager

logger = logging.getLogger("vmodule.api.camera")
router = APIRouter(prefix="/camera", tags=["Camera"])

# In-memory latest frame store: camera_id -> {jpeg_bytes, timestamp}
_latest_frames: dict = {}


class CameraAddRequest(BaseModel):
    camera_id: str
    camera_type: str = Field(default="usb", description="usb / rtsp / daheng / hikvision")
    config: dict = Field(default_factory=dict)
    exposure: int = Field(default=10000, description="曝光时间(微秒)")
    gain: float = Field(default=1.0, description="增益")


class CameraConfigUpdate(BaseModel):
    exposure: Optional[int] = None
    gain: Optional[float] = None


# ---------- CRUD ----------

@router.get("/types", summary="Available camera types")
async def list_types():
    return list(camera_manager.CAMERA_TYPES.keys())


@router.post("/add", summary="Add camera")
async def add_camera(req: CameraAddRequest):
    config = {**req.config, "exposure": req.exposure, "gain": req.gain}
    ok = await camera_manager.add_camera(req.camera_id, req.camera_type, config)
    if not ok:
        raise HTTPException(400, f"Failed to add camera [{req.camera_id}]")
    return {"ok": True, "camera_id": req.camera_id}


@router.delete("/{camera_id}", summary="Remove camera")
async def remove_camera(camera_id: str):
    ok = await camera_manager.remove_camera(camera_id)
    if not ok:
        raise HTTPException(404, f"Camera [{camera_id}] not found")
    _latest_frames.pop(camera_id, None)
    return {"ok": True}


@router.get("/list", summary="List all cameras")
async def list_cameras():
    return camera_manager.get_all_info()


@router.get("/{camera_id}/info", summary="Camera info")
async def camera_info(camera_id: str):
    info = camera_manager.get_camera_info(camera_id)
    if info is None:
        raise HTTPException(404, f"Camera [{camera_id}] not found")
    return info


# ---------- Open / Close ----------

@router.post("/{camera_id}/open", summary="Open camera")
async def open_camera(camera_id: str):
    ok = await camera_manager.open_camera(camera_id)
    if not ok:
        raise HTTPException(400, f"Failed to open camera [{camera_id}]")
    return {"ok": True}


@router.post("/{camera_id}/close", summary="Close camera")
async def close_camera(camera_id: str):
    ok = await camera_manager.close_camera(camera_id)
    return {"ok": ok}


# ---------- Capture ----------

def _encode_jpeg(image: np.ndarray, quality: int = 85) -> bytes:
    """Encode numpy image to JPEG bytes."""
    ok, buf = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("JPEG encode failed")
    return buf.tobytes()


@router.post("/{camera_id}/capture", summary="Capture one frame")
async def capture_frame(camera_id: str):
    image = await camera_manager.capture(camera_id)
    if image is None:
        raise HTTPException(400, f"Capture failed for [{camera_id}]")
    # Store latest frame
    jpeg = _encode_jpeg(image)
    _latest_frames[camera_id] = {"jpeg": jpeg, "ts": time.time(), "shape": image.shape}
    return {
        "ok": True,
        "camera_id": camera_id,
        "shape": list(image.shape),
        "size_kb": round(len(jpeg) / 1024, 1),
    }


@router.get("/{camera_id}/frame.jpg", summary="Get latest frame as JPEG")
async def get_frame_jpeg(camera_id: str):
    entry = _latest_frames.get(camera_id)
    if not entry:
        raise HTTPException(404, "No frame available")
    return Response(content=entry["jpeg"], media_type="image/jpeg")


@router.get("/{camera_id}/frame/base64", summary="Get latest frame as base64")
async def get_frame_base64(camera_id: str):
    entry = _latest_frames.get(camera_id)
    if not entry:
        raise HTTPException(404, "No frame available")
    b64 = base64.b64encode(entry["jpeg"]).decode("ascii")
    return {
        "camera_id": camera_id,
        "image": f"data:image/jpeg;base64,{b64}",
        "shape": list(entry.get("shape", [])),
        "ts": entry["ts"],
    }


@router.post("/{camera_id}/config", summary="Update camera config")
async def update_config(camera_id: str, req: CameraConfigUpdate):
    vcam = camera_manager.get_virtual_camera(camera_id)
    if not vcam:
        raise HTTPException(404, f"Camera [{camera_id}] not found")
    if req.exposure is not None:
        vcam.exposure = req.exposure
    if req.gain is not None:
        vcam.gain = req.gain
    return {"ok": True}


def store_frame(camera_id: str, image: np.ndarray):
    """Called by program blocks to store frames for UI display."""
    jpeg = _encode_jpeg(image)
    _latest_frames[camera_id] = {"jpeg": jpeg, "ts": time.time(), "shape": image.shape}
