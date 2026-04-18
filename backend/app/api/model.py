"""
Model management REST API
"""
import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.core.inference.manager import inference_manager

logger = logging.getLogger("vmodule.api.model")
router = APIRouter(prefix="/model", tags=["Model"])


class ModelLoadRequest(BaseModel):
    model_id: str
    filename: str = Field(..., description="weights filename under data/weights/")
    engine_type: str = "yolo"
    config: dict = Field(default_factory=dict)


class ClassStrategyRequest(BaseModel):
    """Detection class -> PLC strategy mapping"""
    model_id: str
    strategy_map: dict = Field(
        ...,
        description="class_name -> strategy_code, e.g. {'ok':1, 'repairable':2, 'unrepairable':3}",
    )


# Global strategy maps: model_id -> {class_name: strategy_code}
_strategy_maps: dict = {}


def get_strategy_map(model_id: str) -> dict:
    return _strategy_maps.get(model_id, {})


# ---------- CRUD ----------

@router.get("/weights", summary="List available weight files")
async def list_weights():
    wdir = settings.WEIGHTS_DIR
    if not wdir.is_dir():
        return []
    files = []
    for f in wdir.iterdir():
        if f.suffix in ('.pt', '.onnx', '.engine', '.pth'):
            files.append({
                "filename": f.name,
                "size_mb": round(f.stat().st_size / 1024 / 1024, 1),
            })
    return files


@router.post("/load", summary="Load model")
async def load_model(req: ModelLoadRequest):
    path = settings.WEIGHTS_DIR / req.filename
    if not path.is_file():
        raise HTTPException(404, f"Weight file not found: {req.filename}")
    ok = await inference_manager.load_model(
        req.model_id, str(path), req.engine_type, req.config
    )
    if not ok:
        raise HTTPException(400, f"Failed to load model [{req.model_id}]")
    return {"ok": True, "model_id": req.model_id}


@router.post("/{model_id}/unload", summary="Unload model")
async def unload_model(model_id: str):
    ok = await inference_manager.unload_model(model_id)
    if not ok:
        raise HTTPException(404, f"Model [{model_id}] not found")
    _strategy_maps.pop(model_id, None)
    return {"ok": True}


@router.get("/list", summary="List loaded models")
async def list_models():
    infos = inference_manager.get_all_info()
    for info in infos:
        mid = info.get("model_id", "")
        info["strategy_map"] = _strategy_maps.get(mid, {})
    return infos


@router.get("/{model_id}/info", summary="Model info")
async def model_info(model_id: str):
    info = inference_manager.get_model_info(model_id)
    if info is None:
        raise HTTPException(404, f"Model [{model_id}] not found")
    info["strategy_map"] = _strategy_maps.get(model_id, {})
    return info


# ---------- Strategy ----------

@router.post("/strategy", summary="Set class->strategy mapping")
async def set_strategy(req: ClassStrategyRequest):
    _strategy_maps[req.model_id] = req.strategy_map
    logger.info(f"Strategy map for [{req.model_id}]: {req.strategy_map}")
    return {"ok": True, "model_id": req.model_id, "strategy_map": req.strategy_map}


@router.get("/{model_id}/strategy", summary="Get strategy mapping")
async def get_strategy(model_id: str):
    return _strategy_maps.get(model_id, {})
