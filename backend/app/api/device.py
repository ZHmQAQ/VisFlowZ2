"""Generic communication device API."""
from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.device.manager import device_manager
from app.core.persistence import schedule_save

router = APIRouter(prefix="/devices", tags=["Devices"])


class DeviceCreate(BaseModel):
    device_id: str
    name: str = ""
    type: str = Field(default="tcp", description="tcp / tcp_server / serial")
    connection: dict = Field(default_factory=dict)
    protocol: str = "raw"
    enabled: bool = True
    timeout: float = 5.0


class DeviceSend(BaseModel):
    data: str
    hex: bool = True


def _auto_save():
    try:
        schedule_save()
    except Exception:
        pass


@router.get("")
async def list_devices():
    return device_manager.get_all_info()


@router.post("")
async def add_device(req: DeviceCreate):
    ok = await device_manager.add_device(req.device_id, req.type, req.model_dump())
    if not ok:
        raise HTTPException(400, f"Device [{req.device_id}] already exists or type is unsupported")
    _auto_save()
    return {"ok": True, "device_id": req.device_id}


@router.get("/{device_id}")
async def get_device(device_id: str):
    info = device_manager.get_device_info(device_id)
    if not info:
        raise HTTPException(404, f"Device [{device_id}] not found")
    return info


@router.put("/{device_id}")
async def update_device(device_id: str, req: DeviceCreate):
    ok = await device_manager.update_device(device_id, req.type, req.model_dump())
    if not ok:
        raise HTTPException(400, f"Unsupported device type: {req.type}")
    _auto_save()
    return {"ok": True, "device_id": device_id}


@router.delete("/{device_id}")
async def remove_device(device_id: str):
    ok = await device_manager.remove_device(device_id)
    if not ok:
        raise HTTPException(404, f"Device [{device_id}] not found")
    _auto_save()
    return {"ok": True, "device_id": device_id}


@router.post("/{device_id}/connect")
async def connect_device(device_id: str):
    ok = await device_manager.connect_device(device_id)
    if not ok:
        raise HTTPException(400, f"Connect failed for [{device_id}]")
    return {"ok": True, "device_id": device_id}


@router.post("/{device_id}/disconnect")
async def disconnect_device(device_id: str):
    ok = await device_manager.disconnect_device(device_id)
    if not ok:
        raise HTTPException(404, f"Device [{device_id}] not found")
    return {"ok": True, "device_id": device_id}


@router.post("/{device_id}/send")
async def send_device(device_id: str, req: DeviceSend):
    if req.hex:
        ok = await device_manager.send_hex(device_id, req.data)
    else:
        ok = await device_manager.send(device_id, req.data.encode())
    if not ok:
        raise HTTPException(400, f"Send failed for [{device_id}]")
    return {"ok": True, "device_id": device_id}
