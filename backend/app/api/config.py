"""Configuration import/export API."""
from fastapi import APIRouter

from app.core.persistence import get_all_settings, set_setting
from app.core.visflowz_check import validate_visflowz_workflow

router = APIRouter(prefix="/config", tags=["Config"])


@router.get("/export")
async def export_config():
    from app.main import detection_block, multiframe_block, scan_engine
    from app.api.plc import _collect_current_preset

    preset = await _collect_current_preset(scan_engine, detection_block, multiframe_block)
    return {
        "version": "vmodule-1.0",
        **preset,
        "system_settings": await get_all_settings(),
    }


@router.get("/visflowz-self-check")
async def visflowz_self_check():
    from app.main import detection_block, multiframe_block, scan_engine
    from app.api.plc import _collect_current_preset

    preset = await _collect_current_preset(scan_engine, detection_block, multiframe_block)
    return validate_visflowz_workflow(preset)


@router.post("/import")
async def import_config(config_data: dict):
    from app.main import detection_block, multiframe_block, scan_engine
    from app.api.plc import PresetConfig, _apply_preset
    from app.core.persistence import schedule_save

    preset = PresetConfig(**config_data)
    result = await _apply_preset(
        preset, scan_engine, detection_block, multiframe_block, replace=True
    )

    for key, value in config_data.get("system_settings", {}).items():
        await set_setting(key, value)

    schedule_save(delay=0.1)
    return {
        "message": "配置导入完成",
        "stats": {
            "plc_connections": {"added": result["plc_connections"]},
            "io_mappings": {"added": result["io_mappings"]},
            "detection_channels": {"added": result["detection_channels"]},
            "multiframe_channels": {"added": result["multiframe_channels"]},
            "cameras": {"added": result["cameras"]},
            "devices": {"added": result["devices"]},
            "event_actions": {"added": result["event_actions"]},
            "rules": {"added": result["rules"]},
        },
    }
