"""
PLC 连接 & I/O 映射配置 API

提供 RESTful 接口来管理:
  - PLC 连接（增删查）
  - I/O 映射（VModule 地址 ↔ 信捷 PLC 地址）
  - 软元件读写（调试用）
  - 扫描引擎控制
"""

from __future__ import annotations
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("vmodule.api.plc")
router = APIRouter(prefix="/plc", tags=["PLC"])


# ==================== 数据模型 ====================

class PLCConnectionCreate(BaseModel):
    """PLC 连接配置"""
    name: str = Field(..., description="PLC 名称，如 'PLC1'")
    host: str = Field(..., description="IP 地址")
    port: int = Field(default=502, description="Modbus TCP 端口")
    unit_id: int = Field(default=1, description="从站号")
    timeout: float = Field(default=1.0, description="超时(秒)")


class IOMappingCreate(BaseModel):
    """I/O 映射配置"""
    plc_name: str = Field(..., description="PLC 名称")
    plc_addr: str = Field(..., description="信捷 PLC 地址，如 'M100', 'D200', 'X0'")
    vmodule_addr: str = Field(..., description="VModule 地址，如 'EX0', 'ED10', 'EY5'")
    description: str = Field(default="", description="描述")


class DeviceReadRequest(BaseModel):
    """软元件读取请求"""
    address: str = Field(..., description="软元件地址，如 'VM0', 'VD100', 'EX0'")


class DeviceWriteRequest(BaseModel):
    """软元件写入请求"""
    address: str = Field(..., description="软元件地址")
    value: int | float | bool = Field(..., description="写入值")


class DeviceBulkReadRequest(BaseModel):
    """批量读取请求"""
    addresses: List[str] = Field(..., description="地址列表")


# ==================== 依赖注入 ====================

def _get_engine():
    from app.main import scan_engine
    if scan_engine is None:
        raise HTTPException(503, "扫描引擎未初始化")
    return scan_engine


def _get_memory():
    from app.main import memory
    if memory is None:
        raise HTTPException(503, "软元件内存未初始化")
    return memory


# ==================== PLC 连接管理 ====================

@router.post("/connections", summary="添加 PLC 连接")
async def add_plc(req: PLCConnectionCreate):
    from app.core.plc.modbus_client import PLCConnection
    engine = _get_engine()

    conn = PLCConnection(
        name=req.name,
        host=req.host,
        port=req.port,
        unit_id=req.unit_id,
        timeout=req.timeout,
    )
    engine.add_plc(conn)
    return {"ok": True, "message": f"PLC [{req.name}] 已添加"}


@router.get("/connections", summary="查看 PLC 连接状态")
async def list_plc():
    engine = _get_engine()
    return {
        name: {
            "connected": client.connected,
            "host": client._config.host,
            "port": client._config.port,
        }
        for name, client in engine._plc_clients.items()
    }


@router.delete("/connections/{name}", summary="移除 PLC 连接")
async def remove_plc(name: str):
    engine = _get_engine()
    client = engine._plc_clients.pop(name, None)
    if client is None:
        raise HTTPException(404, f"PLC [{name}] 不存在")
    await client.disconnect()
    return {"ok": True, "message": f"PLC [{name}] 已移除"}


# ==================== I/O 映射管理 ====================

@router.post("/mappings", summary="添加 I/O 映射")
async def add_mapping(req: IOMappingCreate):
    from app.core.softdevice.xinje import IOMapping
    engine = _get_engine()

    mapping = IOMapping(
        plc_name=req.plc_name,
        plc_addr=req.plc_addr,
        vmodule_addr=req.vmodule_addr,
        description=req.description,
    )
    engine.add_mapping(mapping)
    return {"ok": True, "message": f"映射 {req.vmodule_addr} ↔ {req.plc_addr} 已添加"}


@router.post("/mappings/batch", summary="批量添加 I/O 映射")
async def add_mappings_batch(mappings: List[IOMappingCreate]):
    from app.core.softdevice.xinje import IOMapping
    engine = _get_engine()

    items = [
        IOMapping(
            plc_name=m.plc_name,
            plc_addr=m.plc_addr,
            vmodule_addr=m.vmodule_addr,
            description=m.description,
        )
        for m in mappings
    ]
    engine.add_mappings(items)
    return {"ok": True, "count": len(items)}


@router.get("/mappings", summary="查看所有 I/O 映射")
async def list_mappings():
    engine = _get_engine()
    return [
        {
            "plc_name": m.plc_name,
            "plc_addr": m.plc_addr,
            "vmodule_addr": m.vmodule_addr,
            "description": m.description,
        }
        for m in engine._io_mappings
    ]


@router.delete("/mappings", summary="清空所有 I/O 映射")
async def clear_mappings():
    engine = _get_engine()
    count = len(engine._io_mappings)
    engine._io_mappings.clear()
    return {"ok": True, "cleared": count}


# ==================== 软元件读写（调试） ====================

@router.get("/device/{address}", summary="读取软元件")
async def read_device(address: str):
    mem = _get_memory()
    try:
        value = mem.read(address)
        return {"address": address, "value": value}
    except Exception as e:
        raise HTTPException(400, str(e))


@router.post("/device/write", summary="写入软元件")
async def write_device(req: DeviceWriteRequest):
    mem = _get_memory()
    try:
        mem.write(req.address, req.value)
        return {"ok": True, "address": req.address, "value": req.value}
    except Exception as e:
        raise HTTPException(400, str(e))


@router.post("/device/bulk-read", summary="批量读取软元件")
async def bulk_read(req: DeviceBulkReadRequest):
    mem = _get_memory()
    results = {}
    for addr in req.addresses:
        try:
            results[addr] = mem.read(addr)
        except Exception as e:
            results[addr] = {"error": str(e)}
    return results


@router.get("/device/dump/{prefix}", summary="导出某类软元件")
async def dump_device(prefix: str, start: int = 0, count: int = 32):
    mem = _get_memory()
    try:
        return mem.dump(prefix, start, count)
    except Exception as e:
        raise HTTPException(400, str(e))


# ==================== 引擎控制 ====================

@router.get("/engine/status", summary="引擎状态")
async def engine_status():
    engine = _get_engine()
    return engine.get_status()


@router.post("/engine/start", summary="启动扫描引擎")
async def engine_start():
    engine = _get_engine()
    await engine.start()
    return {"ok": True, "running": engine.running}


@router.post("/engine/stop", summary="停止扫描引擎")
async def engine_stop():
    engine = _get_engine()
    await engine.stop()
    return {"ok": True, "running": engine.running}


# ==================== 预设加载 ====================

class PresetConfig(BaseModel):
    """预设配置（一次性加载 PLC + 映射 + 检测通道）"""
    plc_connections: List[PLCConnectionCreate] = []
    io_mappings: List[IOMappingCreate] = []
    detection_channels: list = []  # 由 detection API 处理


@router.post("/preset/load", summary="加载预设配置")
async def load_preset(preset: PresetConfig):
    from app.core.plc.modbus_client import PLCConnection
    from app.core.softdevice.xinje import IOMapping
    from app.core.detection.program_block import DetectionChannel
    from app.api.detection import _detection_block

    engine = _get_engine()

    # 1. 添加 PLC 连接
    for p in preset.plc_connections:
        conn = PLCConnection(
            name=p.name, host=p.host, port=p.port,
            unit_id=p.unit_id, timeout=p.timeout,
        )
        engine.add_plc(conn)

    # 2. 添加 I/O 映射
    for m in preset.io_mappings:
        mapping = IOMapping(
            vmodule_addr=m.vmodule_addr,
            plc_addr=m.plc_addr,
            plc_name=m.plc_name,
            description=m.description,
        )
        engine.add_mapping(mapping)

    # 3. 添加检测通道
    ch_count = 0
    if _detection_block:
        for ch_data in preset.detection_channels:
            ch = DetectionChannel(**ch_data)
            _detection_block.add_channel(ch)
            ch_count += 1

    return {
        "ok": True,
        "plc_connections": len(preset.plc_connections),
        "io_mappings": len(preset.io_mappings),
        "detection_channels": ch_count,
    }
