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
    enabled: bool = Field(default=True, description="是否启用")


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
            "host": client.config.host,
            "port": client.config.port,
            "unit_id": client.config.unit_id,
            "timeout": client.config.timeout,
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


@router.post("/connections/{name}/connect", summary="手动连接 PLC")
async def connect_plc(name: str):
    engine = _get_engine()
    client = engine._plc_clients.get(name)
    if client is None:
        raise HTTPException(404, f"PLC [{name}] 不存在")
    try:
        await client.connect()
        return {"ok": True, "message": f"PLC [{name}] 已连接"}
    except Exception as e:
        raise HTTPException(500, f"连接失败: {e}")


@router.post("/connections/{name}/disconnect", summary="手动断开 PLC")
async def disconnect_plc(name: str):
    engine = _get_engine()
    client = engine._plc_clients.get(name)
    if client is None:
        raise HTTPException(404, f"PLC [{name}] 不存在")
    await client.disconnect()
    return {"ok": True, "message": f"PLC [{name}] 已断开"}


@router.put("/connections/{name}", summary="编辑 PLC 配置")
async def update_plc(name: str, req: PLCConnectionCreate):
    from app.core.plc.modbus_client import PLCConnection, ModbusTCPClient
    engine = _get_engine()
    client = engine._plc_clients.get(name)
    if client is None:
        raise HTTPException(404, f"PLC [{name}] 不存在")
    await client.disconnect()
    conn = PLCConnection(
        name=name,
        host=req.host,
        port=req.port,
        unit_id=req.unit_id,
        timeout=req.timeout,
    )
    engine._plc_clients[name] = ModbusTCPClient(conn)
    return {"ok": True, "message": f"PLC [{name}] 配置已更新"}


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
        enabled=req.enabled,
    )
    engine.add_mapping(mapping)
    return {"ok": True, "id": mapping.id, "message": f"映射 {req.vmodule_addr} ↔ {req.plc_addr} 已添加"}


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
            enabled=m.enabled,
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
            "id": m.id,
            "plc_name": m.plc_name,
            "plc_addr": m.plc_addr,
            "vmodule_addr": m.vmodule_addr,
            "description": m.description,
            "enabled": m.enabled,
        }
        for m in engine._io_mappings
    ]


@router.delete("/mappings", summary="清空所有 I/O 映射")
async def clear_mappings():
    engine = _get_engine()
    count = len(engine._io_mappings)
    engine._io_mappings.clear()
    return {"ok": True, "cleared": count}


@router.delete("/mappings/{mapping_id}", summary="按 ID 删除单条 I/O 映射")
async def delete_mapping(mapping_id: int):
    engine = _get_engine()
    for i, m in enumerate(engine._io_mappings):
        if m.id == mapping_id:
            engine._io_mappings.pop(i)
            return {"ok": True, "id": mapping_id}
    raise HTTPException(404, f"映射 ID [{mapping_id}] 不存在")


@router.put("/mappings/{mapping_id}", summary="按 ID 编辑单条 I/O 映射")
async def update_mapping(mapping_id: int, req: IOMappingCreate):
    from app.core.softdevice.xinje import IOMapping
    engine = _get_engine()
    for i, m in enumerate(engine._io_mappings):
        if m.id == mapping_id:
            engine._io_mappings[i] = IOMapping(
                plc_name=req.plc_name, plc_addr=req.plc_addr,
                vmodule_addr=req.vmodule_addr, description=req.description,
                enabled=req.enabled, id=mapping_id,
            )
            return {"ok": True, "id": mapping_id}
    raise HTTPException(404, f"映射 ID [{mapping_id}] 不存在")


@router.patch("/mappings/{mapping_id}/toggle", summary="切换单条映射的启用/禁用")
async def toggle_mapping(mapping_id: int):
    engine = _get_engine()
    for m in engine._io_mappings:
        if m.id == mapping_id:
            m.enabled = not m.enabled
            return {"ok": True, "id": mapping_id, "enabled": m.enabled}
    raise HTTPException(404, f"映射 ID [{mapping_id}] 不存在")


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
    from app.core.softdevice.memory import DevicePrefix
    mem = _get_memory()
    try:
        dp = DevicePrefix(prefix.upper())
        return mem.dump(dp, start, count)
    except (ValueError, KeyError):
        raise HTTPException(400, f"Invalid prefix: {prefix}. Valid: {[p.value for p in DevicePrefix]}")
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
    """Full preset config"""
    plc_connections: List[PLCConnectionCreate] = []
    io_mappings: List[IOMappingCreate] = []
    detection_channels: list = []
    multiframe_channels: list = []
    cameras: list = []
    strategy: Optional[dict] = None


@router.post("/preset/load", summary="Load preset config")
async def load_preset(preset: PresetConfig):
    from app.core.plc.modbus_client import PLCConnection
    from app.core.softdevice.xinje import IOMapping
    from app.core.detection.program_block import DetectionChannel
    from app.core.detection.multiframe import MultiFrameChannel
    from app.api.detection import _detection_block, _multiframe_block
    from app.core.camera.manager import camera_manager
    from app.api.model import _strategy_maps

    engine = _get_engine()

    # 1. PLC connections
    for p in preset.plc_connections:
        conn = PLCConnection(
            name=p.name, host=p.host, port=p.port,
            unit_id=p.unit_id, timeout=p.timeout,
        )
        engine.add_plc(conn)

    # 2. I/O mappings
    for m in preset.io_mappings:
        mapping = IOMapping(
            vmodule_addr=m.vmodule_addr,
            plc_addr=m.plc_addr,
            plc_name=m.plc_name,
            description=m.description,
        )
        engine.add_mapping(mapping)

    # 3. Detection channels (edge-triggered)
    ch_count = 0
    if _detection_block:
        for ch_data in preset.detection_channels:
            ch = DetectionChannel(**ch_data)
            _detection_block.add_channel(ch)
            ch_count += 1

    # 4. Multi-frame channels (register-polling)
    mf_count = 0
    if _multiframe_block:
        for mf_data in preset.multiframe_channels:
            ch = MultiFrameChannel(**mf_data)
            _multiframe_block.add_channel(ch)
            mf_count += 1

    # 5. Cameras
    cam_count = 0
    for cam in preset.cameras:
        config = {**cam.get("config", {})}
        if "exposure" in cam:
            config["exposure"] = cam["exposure"]
        if "gain" in cam:
            config["gain"] = cam["gain"]
        ok = await camera_manager.add_camera(
            cam.get("camera_id", ""),
            cam.get("camera_type", "usb"),
            config,
        )
        if ok:
            cam_count += 1

    # 6. Strategy
    if preset.strategy and preset.strategy.get("model_id"):
        mid = preset.strategy["model_id"]
        smap = preset.strategy.get("strategy_map", {})
        _strategy_maps[mid] = smap

    return {
        "ok": True,
        "plc_connections": len(preset.plc_connections),
        "io_mappings": len(preset.io_mappings),
        "detection_channels": ch_count,
        "multiframe_channels": mf_count,
        "cameras": cam_count,
    }


@router.get("/preset/save", summary="导出当前配置为预设 JSON")
async def save_preset():
    from app.api.detection import _detection_block, _multiframe_block
    from app.core.camera.manager import camera_manager
    from app.api.model import _strategy_maps

    engine = _get_engine()

    plc_connections = [
        {"name": name, "host": c.config.host, "port": c.config.port,
         "unit_id": c.config.unit_id, "timeout": c.config.timeout}
        for name, c in engine._plc_clients.items()
    ]

    io_mappings = [
        {"plc_name": m.plc_name, "plc_addr": m.plc_addr,
         "vmodule_addr": m.vmodule_addr, "description": m.description,
         "enabled": m.enabled}
        for m in engine._io_mappings
    ]

    detection_channels = []
    if _detection_block:
        for ch in _detection_block._channels:
            detection_channels.append({
                "name": ch.name, "trigger_addr": ch.trigger_addr,
                "camera_id": ch.camera_id, "model_id": ch.model_id,
                "busy_addr": ch.busy_addr, "done_addr": ch.done_addr,
                "result_addr": ch.result_addr,
                "defect_count_addr": ch.defect_count_addr,
                "inference_time_addr": ch.inference_time_addr,
                "total_count_addr": getattr(ch, 'total_count_addr', ''),
                "ng_count_addr": getattr(ch, 'ng_count_addr', ''),
                "ok_max_addr": getattr(ch, 'ok_max_addr', ''),
            })

    multiframe_channels = []
    if _multiframe_block:
        for ch in _multiframe_block._channels:
            multiframe_channels.append({
                "name": ch.name, "camera_id": ch.camera_id,
                "model_id": ch.model_id, "frame_count": ch.frame_count,
                "cmd_addr": ch.cmd_addr, "status_addr": ch.status_addr,
                "result_addr": ch.result_addr,
                "count_addr": ch.count_addr, "time_addr": ch.time_addr,
            })

    cameras = []
    for vcam in camera_manager.get_all_cameras().values():
        cameras.append({
            "camera_id": vcam.camera_id,
            "camera_type": vcam.camera_type,
            "config": vcam.config,
        })

    strategy = None
    if _strategy_maps:
        for mid, smap in _strategy_maps.items():
            strategy = {"model_id": mid, "strategy_map": smap}
            break

    return {
        "plc_connections": plc_connections,
        "io_mappings": io_mappings,
        "detection_channels": detection_channels,
        "multiframe_channels": multiframe_channels,
        "cameras": cameras,
        "strategy": strategy,
    }


class EngineConfigUpdate(BaseModel):
    target_cycle_ms: int = Field(default=20, ge=5, le=1000)
    modbus_timeout: float = Field(default=1.0, ge=0.1, le=10.0)


@router.put("/engine/config", summary="更新引擎运行时配置")
async def update_engine_config(req: EngineConfigUpdate):
    engine = _get_engine()
    engine.config.target_cycle_ms = req.target_cycle_ms
    for client in engine._plc_clients.values():
        client.config.timeout = req.modbus_timeout
    return {"ok": True, "target_cycle_ms": req.target_cycle_ms, "modbus_timeout": req.modbus_timeout}
