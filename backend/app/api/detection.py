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

logger = logging.getLogger("vmodule.api.detection")
router = APIRouter(prefix="/detection", tags=["检测通道"])

# 运行时存储（后续可持久化到 DB）
_detection_block = None


def set_detection_block(block):
    global _detection_block
    _detection_block = block


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


@router.get("/channels", summary="查看所有检测通道")
async def list_channels():
    if _detection_block is None:
        raise HTTPException(503, "检测程序块未初始化")
    return [
        {
            "name": ch.name,
            "trigger_addr": ch.trigger_addr,
            "camera_id": ch.camera_id,
            "model_id": ch.model_id,
            "done_addr": ch.done_addr,
            "result_addr": ch.result_addr,
            "busy": False,  # TODO: read from memory
        }
        for ch in _detection_block._channels
    ]
