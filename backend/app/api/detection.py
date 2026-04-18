"""
检测通道配置 API

管理视觉检测通道:
  - 每个通道绑定: 触发地址 + 相机 + 模型 + 输出地址
  - 配置语言完全基于 PLC 软元件地址
"""

from __future__ import annotations
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.detection.program_block import DetectionChannel
from app.core.detection.multiframe import MultiFrameChannel

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
    )
    _detection_block.add_channel(ch)
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
            )
            return {"ok": True, "name": req.name}
    raise HTTPException(404, f"通道 [{name}] 不存在")


@router.delete("/channels/{name}", summary="删除检测通道")
async def delete_channel(name: str):
    if _detection_block is None:
        raise HTTPException(503, "检测程序块未初始化")
    for i, ch in enumerate(_detection_block._channels):
        if ch.name == name:
            _detection_block._channels.pop(i)
            return {"ok": True, "name": name}
    raise HTTPException(404, f"通道 [{name}] 不存在")


# ==================== Multi-frame channels ====================

class MultiFrameChannelCreate(BaseModel):
    name: str
    camera_id: str
    model_id: str
    frame_count: int = 3
    cmd_addr: str = Field(..., description="Command register (ED)")
    status_addr: str = Field(..., description="Status register (EW)")
    result_addr: str = Field(..., description="Strategy result register (EW)")
    count_addr: str = Field(default="", description="Defect count register (EW)")
    time_addr: str = Field(default="", description="Inference time register (EW)")


@router.post("/multiframe", summary="Add multi-frame channel")
async def add_multiframe_channel(req: MultiFrameChannelCreate):
    if _multiframe_block is None:
        raise HTTPException(503, "MultiFrame block not initialized")
    ch = MultiFrameChannel(
        name=req.name,
        camera_id=req.camera_id,
        model_id=req.model_id,
        frame_count=req.frame_count,
        cmd_addr=req.cmd_addr,
        status_addr=req.status_addr,
        result_addr=req.result_addr,
        count_addr=req.count_addr,
        time_addr=req.time_addr,
    )
    _multiframe_block.add_channel(ch)
    return {"ok": True, "name": req.name}


@router.get("/multiframe", summary="List multi-frame channels")
async def list_multiframe_channels():
    if _multiframe_block is None:
        raise HTTPException(503, "MultiFrame block not initialized")
    return [
        {
            "name": ch.name,
            "camera_id": ch.camera_id,
            "model_id": ch.model_id,
            "frame_count": ch.frame_count,
            "cmd_addr": ch.cmd_addr,
            "status_addr": ch.status_addr,
            "result_addr": ch.result_addr,
            "count_addr": ch.count_addr,
            "time_addr": ch.time_addr,
            "busy": ch._busy,
            "frames_collected": len(ch._frames),
        }
        for ch in _multiframe_block._channels
    ]


@router.put("/multiframe/{name}", summary="编辑多帧通道")
async def update_multiframe_channel(name: str, req: MultiFrameChannelCreate):
    if _multiframe_block is None:
        raise HTTPException(503, "MultiFrame block not initialized")
    for i, ch in enumerate(_multiframe_block._channels):
        if ch.name == name:
            _multiframe_block._channels[i] = MultiFrameChannel(
                name=req.name,
                camera_id=req.camera_id,
                model_id=req.model_id,
                frame_count=req.frame_count,
                cmd_addr=req.cmd_addr,
                status_addr=req.status_addr,
                result_addr=req.result_addr,
                count_addr=req.count_addr,
                time_addr=req.time_addr,
            )
            return {"ok": True, "name": req.name}
    raise HTTPException(404, f"通道 [{name}] 不存在")


@router.delete("/multiframe/{name}", summary="删除多帧通道")
async def delete_multiframe_channel(name: str):
    if _multiframe_block is None:
        raise HTTPException(503, "MultiFrame block not initialized")
    for i, ch in enumerate(_multiframe_block._channels):
        if ch.name == name:
            _multiframe_block._channels.pop(i)
            return {"ok": True, "name": name}
    raise HTTPException(404, f"通道 [{name}] 不存在")
