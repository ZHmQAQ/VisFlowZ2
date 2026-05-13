"""Event-action mapping engine.

This module keeps the VisFlowZ event-action idea lightweight for VModule:
users can configure mappings, generate common templates, and dry-run events.
Runtime integration can call ``event_action_engine.emit(...)`` from program
blocks when the corresponding lifecycle hooks are wired in.
"""
from __future__ import annotations

import asyncio
from enum import Enum
from typing import Any, Awaitable, Callable

from app.utils.logger import logger


class EventType(str, Enum):
    ON_REG_CHANGED = "on_reg_changed"
    ON_DATA_RECEIVED = "on_data_received"
    ON_CAM_OK = "on_cam_ok"
    ON_CAM_FAIL = "on_cam_fail"
    ON_ALL_FRAMES_DONE = "on_all_frames_done"
    ON_INFER_OK = "on_infer_ok"
    ON_CYCLE_DONE = "on_cycle_done"


class ActionType(str, Enum):
    WRITE_REGISTER = "write_register"
    READ_REGISTER = "read_register"
    TRIGGER_CAPTURE = "trigger_capture"
    TRIGGER_INFERENCE = "trigger_inference"
    SAVE_IMAGE = "save_image"
    SEND_COMMAND = "send_command"
    TRIGGER_ALARM = "trigger_alarm"
    LOG = "log"


class ValueType(str, Enum):
    FIXED = "fixed"
    ACK = "ack"
    RESULT = "result"
    CLEAR = "clear"


DEFAULT_MAPPINGS = [
    {
        "mapping_id": "_default_ack",
        "name": "相机采集成功 -> ACK",
        "event_type": EventType.ON_CAM_OK.value,
        "event_source": "*",
        "action_type": ActionType.WRITE_REGISTER.value,
        "action_target": "",
        "action_params": {"value_type": ValueType.ACK.value},
        "order_index": 10,
        "enabled": True,
    },
    {
        "mapping_id": "_default_error",
        "name": "相机采集失败 -> 错误码",
        "event_type": EventType.ON_CAM_FAIL.value,
        "event_source": "*",
        "action_type": ActionType.WRITE_REGISTER.value,
        "action_target": "",
        "action_params": {"value_type": ValueType.FIXED.value, "value": 255},
        "order_index": 20,
        "enabled": True,
    },
    {
        "mapping_id": "_default_clear",
        "name": "全部帧完成 -> 清零",
        "event_type": EventType.ON_ALL_FRAMES_DONE.value,
        "event_source": "*",
        "action_type": ActionType.WRITE_REGISTER.value,
        "action_target": "",
        "action_params": {"value_type": ValueType.CLEAR.value},
        "order_index": 30,
        "enabled": True,
    },
    {
        "mapping_id": "_default_result",
        "name": "周期完成 -> 检测结果",
        "event_type": EventType.ON_CYCLE_DONE.value,
        "event_source": "*",
        "action_type": ActionType.WRITE_REGISTER.value,
        "action_target": "",
        "action_params": {"value_type": ValueType.RESULT.value},
        "order_index": 40,
        "enabled": True,
    },
]

ActionHandler = Callable[[str, dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any]]]


class EventActionEngine:
    def __init__(self):
        self._mappings: list[dict[str, Any]] = []
        self._handlers: dict[str, ActionHandler] = {}
        self._lock = asyncio.Lock()

    async def set_mappings(self, mappings: list[dict[str, Any]]) -> None:
        async with self._lock:
            self._mappings = sorted(
                [self._normalize(m) for m in mappings],
                key=lambda item: item.get("order_index", 0),
            )

    async def add_mapping(self, mapping: dict[str, Any]) -> None:
        item = self._normalize(mapping)
        async with self._lock:
            if any(m["mapping_id"] == item["mapping_id"] for m in self._mappings):
                raise ValueError(f"Mapping [{item['mapping_id']}] already exists")
            self._mappings.append(item)
            self._mappings.sort(key=lambda m: m.get("order_index", 0))

    async def update_mapping(self, mapping_id: str, updates: dict[str, Any]) -> bool:
        async with self._lock:
            for idx, mapping in enumerate(self._mappings):
                if mapping["mapping_id"] == mapping_id:
                    merged = {**mapping, **updates, "mapping_id": mapping_id}
                    self._mappings[idx] = self._normalize(merged)
                    self._mappings.sort(key=lambda m: m.get("order_index", 0))
                    return True
        return False

    async def delete_mapping(self, mapping_id: str) -> bool:
        async with self._lock:
            before = len(self._mappings)
            self._mappings = [m for m in self._mappings if m["mapping_id"] != mapping_id]
            return len(self._mappings) != before

    async def clear(self) -> None:
        async with self._lock:
            self._mappings.clear()

    def list_mappings(self) -> list[dict[str, Any]]:
        return [dict(m) for m in self._mappings]

    def find_mappings(self, event_type: str, event_source: str = "*") -> list[dict[str, Any]]:
        matches = []
        for mapping in self._mappings:
            if not mapping.get("enabled", True):
                continue
            if mapping.get("event_type") != event_type:
                continue
            source = mapping.get("event_source") or "*"
            if source != "*" and source != event_source:
                continue
            matches.append(dict(mapping))
        return matches

    def register_handler(self, action_type: str, handler: ActionHandler) -> None:
        self._handlers[action_type] = handler

    async def emit(self, event_type: str, event_source: str = "*", context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        context = context or {}
        results = []
        for mapping in self.find_mappings(event_type, event_source):
            action_type = mapping["action_type"]
            target = mapping.get("action_target", "")
            params = dict(mapping.get("action_params") or {})
            handler = self._handlers.get(action_type, self._default_handler)
            try:
                result = await handler(target, params, context)
                results.append({
                    "mapping_id": mapping["mapping_id"],
                    "action_type": action_type,
                    "success": bool(result.get("success", True)),
                    "result": result,
                })
            except Exception as exc:
                logger.exception("Event action failed: %s", mapping["mapping_id"])
                results.append({
                    "mapping_id": mapping["mapping_id"],
                    "action_type": action_type,
                    "success": False,
                    "error": str(exc),
                })
        return results

    def resolve_value(self, params: dict[str, Any], context: dict[str, Any]) -> int:
        value_type = params.get("value_type", ValueType.FIXED.value)
        if value_type == ValueType.CLEAR.value:
            return 0
        if value_type == ValueType.ACK.value:
            return int(context.get("ack_base", 16)) + int(context.get("frame_index", 0))
        if value_type == ValueType.RESULT.value:
            return int(context.get("result_code", 0))
        return int(params.get("value", 0))

    async def _default_handler(self, target: str, params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        return {
            "success": True,
            "dry_run": True,
            "target": target,
            "params": params,
            "resolved_value": self.resolve_value(params, context) if "value_type" in params else None,
        }

    def _normalize(self, mapping: dict[str, Any]) -> dict[str, Any]:
        mapping_id = str(mapping.get("mapping_id") or "").strip()
        if not mapping_id:
            raise ValueError("mapping_id is required")
        return {
            "mapping_id": mapping_id,
            "name": mapping.get("name") or mapping_id,
            "event_type": str(mapping.get("event_type") or EventType.ON_CAM_OK.value),
            "event_source": mapping.get("event_source") or "*",
            "event_filter": mapping.get("event_filter") or {},
            "action_type": str(mapping.get("action_type") or ActionType.LOG.value),
            "action_target": mapping.get("action_target") or "",
            "action_params": mapping.get("action_params") or {},
            "order_index": int(mapping.get("order_index") or 0),
            "enabled": mapping.get("enabled", True) is not False,
        }


event_action_engine = EventActionEngine()
