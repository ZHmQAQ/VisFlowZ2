"""
检测通道配置 API

管理视觉检测通道:
  - 每个通道绑定: 触发地址 + 相机 + 模型 + 输出地址
  - 配置语言完全基于 PLC 软元件地址
"""

from __future__ import annotations
import logging
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.detection.program_block import DetectionChannel
from app.core.detection.multiframe import MultiFrameChannel
from app.core.persistence import schedule_save

logger = logging.getLogger("vmodule.api.detection")
router = APIRouter(prefix="/detection", tags=["Detection"])

_detection_block = None
_multiframe_block = None


def set_detection_block(block):
    global _detection_block
    _detection_block = block


def set_multiframe_block(block):
    global _multiframe_block
    _multiframe_block = block


class ChannelCreate(BaseModel):
    """检测通道创建请求"""
    name: str = Field(..., description="通道名称")
    trigger_addr: str = Field(..., description="触发地址 (EX)")
    camera_id: str = Field(..., description="相机 ID")
    model_id: str = Field(..., description="模型 ID")
    busy_addr: str = Field(default="VM100", description="忙碌标志地址")
    done_addr: str = Field(..., description="完成信号地址 (EY)")
    result_addr: str = Field(..., description="OK/NG 结果地址 (EY)")
    defect_count_addr: str = Field(default="", description="缺陷数量地址 (EW)")
    inference_time_addr: str = Field(default="", description="推理耗时地址 (EW)")
    total_count_addr: str = Field(default="", description="累计检测次数地址 (VD)")
    ng_count_addr: str = Field(default="", description="累计 NG 次数地址 (VD)")
    ok_max_addr: str = Field(default="", description="OK 最大缺陷数阈值地址 (VD)")
    ack_base: int = Field(default=16, description="ACK base code")
    error_code: int = Field(default=255, description="Capture/error code")
    result_codes: dict[str, int] = Field(default_factory=lambda: {"ok": 7, "ng_repairable": 6, "ng_fatal": 5})
    defect_priority: list[str] = Field(default_factory=lambda: ["NG", "HP_NG", "QJ_NG", "RJ_NG", "LX_NG"])
    defect_code_map: dict[str, str] = Field(default_factory=lambda: {"NG": "ng_fatal", "HP_NG": "ng_repairable", "QJ_NG": "ng_repairable", "RJ_NG": "ng_repairable", "LX_NG": "ng_repairable"})
    inference: dict[str, Any] = Field(default_factory=dict)


@router.post("/channels", summary="添加检测通道")
async def add_channel(req: ChannelCreate):
    if _detection_block is None:
        raise HTTPException(503, "检测程序块未初始化")

    ch = DetectionChannel(
        name=req.name,
        trigger_addr=req.trigger_addr,
        camera_id=req.camera_id,
        model_id=req.model_id,
        busy_addr=req.busy_addr,
        done_addr=req.done_addr,
        result_addr=req.result_addr,
        defect_count_addr=req.defect_count_addr,
        inference_time_addr=req.inference_time_addr,
        total_count_addr=req.total_count_addr,
        ng_count_addr=req.ng_count_addr,
        ok_max_addr=req.ok_max_addr,
        ack_base=req.ack_base,
        error_code=req.error_code,
        result_codes=req.result_codes,
        defect_priority=req.defect_priority,
        defect_code_map=req.defect_code_map,
        inference=req.inference,
    )
    _detection_block.add_channel(ch)
    schedule_save()
    return {"ok": True, "name": req.name}


@router.get("/channels", summary="List all detection channels")
async def list_channels():
    if _detection_block is None:
        raise HTTPException(503, "Detection block not initialized")
    return [
        {
            "name": ch.name,
            "trigger_addr": ch.trigger_addr,
            "camera_id": ch.camera_id,
            "model_id": ch.model_id,
            "busy_addr": ch.busy_addr,
            "done_addr": ch.done_addr,
            "result_addr": ch.result_addr,
            "defect_count_addr": ch.defect_count_addr,
            "inference_time_addr": ch.inference_time_addr,
            "total_count_addr": getattr(ch, "total_count_addr", ""),
            "ng_count_addr": getattr(ch, "ng_count_addr", ""),
            "ok_max_addr": getattr(ch, "ok_max_addr", ""),
            "ack_base": getattr(ch, "ack_base", 16),
            "error_code": getattr(ch, "error_code", 255),
            "result_codes": getattr(ch, "result_codes", {}),
            "defect_priority": getattr(ch, "defect_priority", []),
            "defect_code_map": getattr(ch, "defect_code_map", {}),
            "inference": getattr(ch, "inference", {}),
            "busy": getattr(ch, '_busy', False),
        }
        for ch in _detection_block._channels
    ]


@router.put("/channels/{name}", summary="编辑检测通道")
async def update_channel(name: str, req: ChannelCreate):
    if _detection_block is None:
        raise HTTPException(503, "检测程序块未初始化")
    for i, ch in enumerate(_detection_block._channels):
        if ch.name == name:
            _detection_block._channels[i] = DetectionChannel(
                name=req.name,
                trigger_addr=req.trigger_addr,
                camera_id=req.camera_id,
                model_id=req.model_id,
                busy_addr=req.busy_addr,
                done_addr=req.done_addr,
                result_addr=req.result_addr,
                defect_count_addr=req.defect_count_addr,
                inference_time_addr=req.inference_time_addr,
                total_count_addr=req.total_count_addr,
                ng_count_addr=req.ng_count_addr,
                ok_max_addr=req.ok_max_addr,
                ack_base=req.ack_base,
                error_code=req.error_code,
                result_codes=req.result_codes,
                defect_priority=req.defect_priority,
                defect_code_map=req.defect_code_map,
                inference=req.inference,
            )
            schedule_save()
            return {"ok": True, "name": req.name}
    raise HTTPException(404, f"通道 [{name}] 不存在")


@router.delete("/channels/{name}", summary="删除检测通道")
async def delete_channel(name: str):
    if _detection_block is None:
        raise HTTPException(503, "检测程序块未初始化")
    for i, ch in enumerate(_detection_block._channels):
        if ch.name == name:
            _detection_block._channels.pop(i)
            schedule_save()
            return {"ok": True, "name": name}
    raise HTTPException(404, f"通道 [{name}] 不存在")


# ==================== Multi-frame channels ====================

class MultiFrameChannelCreate(BaseModel):
    name: str
    camera_id: str
    model_id: str = ""
    frame_count: int = 3
    cmd_addr: str = Field(..., description="Command register (ED)")
    status_addr: str = Field(..., description="Status register (EW)")
    result_addr: str = Field(default="", description="Optional separate strategy result register (EW/VD)")
    count_addr: str = Field(default="", description="Optional defect count register (EW/VD)")
    time_addr: str = Field(default="", description="Optional elapsed time register (EW/VD)")
    frame_plan: list[Any] = Field(default_factory=list)
    result_policy: dict[str, Any] = Field(default_factory=dict)
    save_policy: dict[str, Any] = Field(default_factory=lambda: {"mode": "all"})
    reset_policy: dict[str, Any] = Field(default_factory=dict)
    finalize_delay_ms: int = 50


def _build_multiframe_channel(req: MultiFrameChannelCreate) -> MultiFrameChannel:
    return MultiFrameChannel(
        name=req.name,
        camera_id=req.camera_id,
        model_id=req.model_id,
        frame_count=req.frame_count,
        cmd_addr=req.cmd_addr,
        status_addr=req.status_addr,
        result_addr=req.result_addr,
        count_addr=req.count_addr,
        time_addr=req.time_addr,
        frame_plan=req.frame_plan,
        result_policy=req.result_policy,
        save_policy=req.save_policy,
        reset_policy=req.reset_policy,
        finalize_delay_ms=req.finalize_delay_ms,
    )


def _multiframe_payload(ch: MultiFrameChannel) -> dict:
    frame_plan = [
        {
            "command": item.command,
            "model_id": item.model_id,
            "status_code": ch.status_code_for(item.command),
            "exposure": item.exposure,
            "label": item.label,
        }
        for item in ch.normalized_plan()
    ]
    return {
        "name": ch.name,
        "camera_id": ch.camera_id,
        "model_id": ch.model_id,
        "frame_count": ch.frame_count,
        "cmd_addr": ch.cmd_addr,
        "status_addr": ch.status_addr,
        "result_addr": ch.result_addr,
        "count_addr": ch.count_addr,
        "time_addr": ch.time_addr,
        "frame_plan": frame_plan,
        "result_policy": ch.result_policy,
        "save_policy": ch.save_policy,
        "reset_policy": ch.reset_policy,
        "finalize_delay_ms": ch.finalize_delay_ms,
        "busy": ch._busy,
        "awaiting_reset": ch._awaiting_reset,
        "pending_finalize": ch._pending_finalize,
        "cycle_id": ch._cycle_id,
        "last_cmd": ch._last_cmd,
        "frames_collected": len(ch._frames),
        "collected_commands": sorted(ch._frames),
        "expected_commands": sorted(ch.expected_commands),
        "frame_paths": ch._frame_paths,
    }


@router.post("/multiframe", summary="Add multi-frame channel")
async def add_multiframe_channel(req: MultiFrameChannelCreate):
    if _multiframe_block is None:
        raise HTTPException(503, "MultiFrame block not initialized")
    _multiframe_block.add_channel(_build_multiframe_channel(req))
    schedule_save()
    return {"ok": True, "name": req.name}


@router.get("/multiframe", summary="List multi-frame channels")
async def list_multiframe_channels():
    if _multiframe_block is None:
        raise HTTPException(503, "MultiFrame block not initialized")
    return [_multiframe_payload(ch) for ch in _multiframe_block._channels]


@router.put("/multiframe/{name}", summary="编辑多帧通道")
async def update_multiframe_channel(name: str, req: MultiFrameChannelCreate):
    if _multiframe_block is None:
        raise HTTPException(503, "MultiFrame block not initialized")
    for i, ch in enumerate(_multiframe_block._channels):
        if ch.name == name:
            _multiframe_block._channels[i] = _build_multiframe_channel(req)
            schedule_save()
            return {"ok": True, "name": req.name}
    raise HTTPException(404, f"通道 [{name}] 不存在")


@router.delete("/multiframe/{name}", summary="删除多帧通道")
async def delete_multiframe_channel(name: str):
    if _multiframe_block is None:
        raise HTTPException(503, "MultiFrame block not initialized")
    for i, ch in enumerate(_multiframe_block._channels):
        if ch.name == name:
            _multiframe_block._channels.pop(i)
            schedule_save()
            return {"ok": True, "name": name}
    raise HTTPException(404, f"通道 [{name}] 不存在")
