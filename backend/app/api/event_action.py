"""Event-action mapping API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.event_action import (
    ActionType,
    EventType,
    ValueType,
    event_action_engine,
)
from app.core.persistence import schedule_save

router = APIRouter(prefix="/event-actions", tags=["Event Actions"])


EVENT_TYPE_META = {
    EventType.ON_REG_CHANGED.value: ("\u5bc4\u5b58\u5668\u53d8\u5316", "PLC \u8f6e\u8be2\u68c0\u6d4b\u5230\u5bc4\u5b58\u5668\u503c\u53d8\u5316\u3002"),
    EventType.ON_DATA_RECEIVED.value: ("\u6536\u5230\u6570\u636e", "\u6536\u5230\u88ab\u52a8\u8bbe\u5907\u6570\u636e\u6216 Modbus \u62a5\u6587\u3002"),
    EventType.ON_CAM_OK.value: ("\u91c7\u96c6\u5b8c\u6210", "\u76f8\u673a\u5e27\u91c7\u96c6\u6210\u529f\u3002"),
    EventType.ON_CAM_FAIL.value: ("\u91c7\u96c6\u5931\u8d25", "\u76f8\u673a\u91c7\u96c6\u8d85\u65f6\u6216\u5931\u8d25\u3002"),
    EventType.ON_ALL_FRAMES_DONE.value: ("\u5168\u90e8\u5e27\u5b8c\u6210", "\u5f53\u524d\u76f8\u673a\u68c0\u6d4b\u5468\u671f\u7684\u5168\u90e8\u5e27\u5df2\u5b8c\u6210\u3002"),
    EventType.ON_INFER_OK.value: ("\u63a8\u7406\u5b8c\u6210", "\u5355\u5e27\u63a8\u7406\u5b8c\u6210\u3002"),
    EventType.ON_CYCLE_DONE.value: ("\u5468\u671f\u5b8c\u6210", "\u5b8c\u6574\u68c0\u6d4b\u5468\u671f\u7ed3\u675f\u3002"),
}

ACTION_TYPE_META = {
    ActionType.WRITE_REGISTER.value: ("\u5199\u5bc4\u5b58\u5668", "\u5199\u5165\u5bc4\u5b58\u5668\u6216\u6620\u5c04\u540e\u7684\u5e94\u7b54\u503c\u3002"),
    ActionType.READ_REGISTER.value: ("\u8bfb\u5bc4\u5b58\u5668", "\u8bfb\u53d6\u5bc4\u5b58\u5668\u503c\u3002"),
    ActionType.TRIGGER_CAPTURE.value: ("\u89e6\u53d1\u91c7\u96c6", "\u89e6\u53d1\u76f8\u673a\u91c7\u96c6\u3002"),
    ActionType.TRIGGER_INFERENCE.value: ("\u89e6\u53d1\u63a8\u7406", "\u5bf9\u6700\u65b0\u56fe\u50cf\u6267\u884c\u63a8\u7406\u3002"),
    ActionType.SAVE_IMAGE.value: ("\u4fdd\u5b58\u56fe\u50cf", "\u4fdd\u5b58\u5f53\u524d\u5e27\u3002"),
    ActionType.SEND_COMMAND.value: ("\u53d1\u9001\u547d\u4ee4", "\u5411\u901a\u4fe1\u8bbe\u5907\u53d1\u9001\u539f\u59cb\u6570\u636e\u3002"),
    ActionType.TRIGGER_ALARM.value: ("\u89e6\u53d1\u62a5\u8b66", "\u4ea7\u751f\u62a5\u8b66\u4e8b\u4ef6\u3002"),
    ActionType.LOG.value: ("\u8bb0\u5f55\u65e5\u5fd7", "\u5199\u5165\u8fd0\u884c\u65e5\u5fd7\u3002"),
}

VALUE_TYPE_META = {
    ValueType.FIXED.value: ("\u56fa\u5b9a\u503c", "\u4f7f\u7528\u914d\u7f6e\u7684\u6570\u5b57\u503c\u3002"),
    ValueType.ACK.value: ("ACK \u5e94\u7b54", "ack_base + frame_index\u3002"),
    ValueType.RESULT.value: ("\u68c0\u6d4b\u7ed3\u679c", "\u4f7f\u7528\u4e0a\u4e0b\u6587\u4e2d\u7684 result_code\u3002"),
    ValueType.CLEAR.value: ("\u6e05\u96f6", "\u5199\u5165 0\u3002"),
}


class EventActionMapping(BaseModel):
    mapping_id: str = Field(..., min_length=1)
    name: str = ""
    event_type: str = EventType.ON_CAM_OK.value
    event_source: str = "*"
    event_filter: dict[str, Any] = Field(default_factory=dict)
    action_type: str = ActionType.LOG.value
    action_target: str = ""
    action_params: dict[str, Any] = Field(default_factory=dict)
    order_index: int = 0
    enabled: bool = True


class EventActionUpdate(BaseModel):
    name: str | None = None
    event_type: str | None = None
    event_source: str | None = None
    event_filter: dict[str, Any] | None = None
    action_type: str | None = None
    action_target: str | None = None
    action_params: dict[str, Any] | None = None
    order_index: int | None = None
    enabled: bool | None = None


class GenerateRequest(BaseModel):
    template: str = "standard_inspection"
    cameras: list[dict[str, Any]] = Field(default_factory=list)
    replace: bool = True


class TestEventRequest(BaseModel):
    event_type: str
    event_source: str = "*"
    context: dict[str, Any] = Field(default_factory=dict)


def _auto_save():
    try:
        schedule_save()
    except Exception:
        pass


def _meta_items(meta: dict[str, tuple[str, str]]) -> list[dict[str, str]]:
    return [
        {"value": value, "label": label, "description": description}
        for value, (label, description) in meta.items()
    ]


@router.get("/meta")
async def get_meta():
    return {
        "events": _meta_items(EVENT_TYPE_META),
        "actions": _meta_items(ACTION_TYPE_META),
        "value_types": _meta_items(VALUE_TYPE_META),
    }


@router.get("")
async def list_event_actions():
    return event_action_engine.list_mappings()


@router.post("")
async def add_event_action(req: EventActionMapping):
    try:
        await event_action_engine.add_mapping(req.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    _auto_save()
    return {"ok": True, "mapping_id": req.mapping_id}


@router.put("/{mapping_id}")
async def update_event_action(mapping_id: str, req: EventActionUpdate):
    updates = req.model_dump(exclude_none=True)
    try:
        ok = await event_action_engine.update_mapping(mapping_id, updates)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if not ok:
        raise HTTPException(404, f"Mapping [{mapping_id}] not found")
    _auto_save()
    return {"ok": True, "mapping_id": mapping_id}


@router.delete("/{mapping_id}")
async def delete_event_action(mapping_id: str):
    ok = await event_action_engine.delete_mapping(mapping_id)
    if not ok:
        raise HTTPException(404, f"Mapping [{mapping_id}] not found")
    _auto_save()
    return {"ok": True, "mapping_id": mapping_id}


@router.post("/batch")
async def batch_set_event_actions(mappings: list[EventActionMapping]):
    await event_action_engine.set_mappings([m.model_dump() for m in mappings])
    _auto_save()
    return {"ok": True, "count": len(mappings)}


@router.get("/templates")
async def get_templates():
    return [
        {
            "name": "standard_inspection",
            "label": "\u6807\u51c6 PLC \u68c0\u6d4b",
            "description": "\u91c7\u96c6 ACK\u3001\u91c7\u96c6\u5931\u8d25\u3001\u6e05\u96f6\u548c\u6700\u7ec8\u7ed3\u679c\u56de\u5199\u3002",
        },
        {
            "name": "dataset_collection",
            "label": "\u6570\u636e\u96c6\u91c7\u96c6",
            "description": "\u9010\u5e27\u4fdd\u5b58\u56fe\u50cf\uff0c\u5e76\u53d1\u9001 ACK\u3001\u9519\u8bef\u548c\u6e05\u96f6\u5e94\u7b54\u3002",
        },
        {
            "name": "capture_only",
            "label": "\u4ec5\u91c7\u96c6",
            "description": "\u53ea\u53d1\u9001 ACK\u3001\u9519\u8bef\u548c\u6e05\u96f6\u5e94\u7b54\uff0c\u4e0d\u6267\u884c\u63a8\u7406\u548c\u56fe\u50cf\u4fdd\u5b58\u3002",
        },
    ]


@router.post("/generate")
async def generate_from_template(req: GenerateRequest):
    mappings = generate_template_mappings(req.template, req.cameras)
    if not mappings:
        raise HTTPException(400, "No mappings generated. Provide at least one camera_id.")
    if req.replace:
        await event_action_engine.set_mappings(mappings)
    else:
        for mapping in mappings:
            try:
                await event_action_engine.add_mapping(mapping)
            except ValueError:
                await event_action_engine.update_mapping(mapping["mapping_id"], mapping)
    _auto_save()
    return {"ok": True, "count": len(mappings), "mappings": mappings}


@router.post("/test")
async def test_event(req: TestEventRequest):
    results = await event_action_engine.emit(req.event_type, req.event_source, req.context)
    return {"ok": True, "matched": len(results), "results": results}


def generate_template_mappings(template: str, cameras: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mappings: list[dict[str, Any]] = []
    order = 10
    for camera in cameras:
        camera_id = str(camera.get("camera_id") or "").strip()
        target = str(camera.get("response_device") or camera.get("device_id") or "")
        if not camera_id:
            continue
        if template == "dataset_collection":
            mappings.append(_mapping(f"{camera_id}_save", f"{camera_id} \u4fdd\u5b58\u56fe\u50cf", camera_id, ActionType.SAVE_IMAGE.value, camera_id, {"format": "png"}, order))
            order += 1
        if template in {"standard_inspection", "dataset_collection", "capture_only"}:
            mappings.extend([
                _mapping(f"{camera_id}_ack", f"{camera_id} \u91c7\u96c6 ACK", camera_id, ActionType.WRITE_REGISTER.value, target, {"value_type": ValueType.ACK.value}, order),
                _mapping(f"{camera_id}_error", f"{camera_id} \u91c7\u96c6\u5931\u8d25", camera_id, ActionType.WRITE_REGISTER.value, target, {"value_type": ValueType.FIXED.value, "value": 255}, order + 1, EventType.ON_CAM_FAIL.value),
                _mapping(f"{camera_id}_clear", f"{camera_id} \u6e05\u96f6\u89e6\u53d1", camera_id, ActionType.WRITE_REGISTER.value, target, {"value_type": ValueType.CLEAR.value}, order + 2, EventType.ON_ALL_FRAMES_DONE.value),
            ])
            if template == "standard_inspection":
                mappings.append(_mapping(f"{camera_id}_result", f"{camera_id} \u5199\u5165\u7ed3\u679c", camera_id, ActionType.WRITE_REGISTER.value, target, {"value_type": ValueType.RESULT.value}, order + 3, EventType.ON_CYCLE_DONE.value))
        order += 10
    return mappings


def _mapping(
    mapping_id: str,
    name: str,
    source: str,
    action_type: str,
    target: str,
    params: dict[str, Any],
    order: int,
    event_type: str = EventType.ON_CAM_OK.value,
) -> dict[str, Any]:
    return {
        "mapping_id": mapping_id,
        "name": name,
        "event_type": event_type,
        "event_source": source,
        "event_filter": {},
        "action_type": action_type,
        "action_target": target,
        "action_params": params,
        "order_index": order,
        "enabled": True,
    }
