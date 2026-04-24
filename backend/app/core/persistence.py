"""
自动保存/恢复配置 — 防抖写入 + 启动恢复

API 写操作后调用 schedule_save()，2 秒防抖后批量保存当前配置到数据库。
启动时调用 restore_config() 从数据库恢复上次配置。
"""
from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select

from app.db.database import async_session
from app.db.models import SystemConfig, DetectionRecord

logger = logging.getLogger("vmodule.persistence")

_save_task: Optional[asyncio.Task] = None
_config_collector = None  # 回调函数，由 main.py 设置


def set_config_collector(fn):
    """设置配置收集回调: async def fn() -> dict"""
    global _config_collector
    _config_collector = fn


def schedule_save(delay: float = 2.0):
    """防抖触发配置保存"""
    global _save_task
    if _save_task and not _save_task.done():
        _save_task.cancel()
    _save_task = asyncio.create_task(_delayed_save(delay))


async def _delayed_save(delay: float):
    """延迟保存"""
    try:
        await asyncio.sleep(delay)
        if _config_collector is None:
            return
        data = await _config_collector()
        await set_setting("preset.current", data)
        logger.info("配置已自动保存")
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"自动保存失败: {e}")


async def get_setting(key: str) -> Any:
    """读取单项设置"""
    async with async_session() as session:
        result = await session.execute(
            select(SystemConfig).where(SystemConfig.key == key)
        )
        row = result.scalar_one_or_none()
        return row.value if row else None


async def set_setting(key: str, value: Any):
    """写入单项设置"""
    async with async_session() as session:
        result = await session.execute(
            select(SystemConfig).where(SystemConfig.key == key)
        )
        row = result.scalar_one_or_none()
        if row:
            row.value = value
            row.updated_at = datetime.utcnow()
        else:
            session.add(SystemConfig(key=key, value=value))
        await session.commit()


async def get_all_settings() -> dict:
    """获取所有设置"""
    async with async_session() as session:
        result = await session.execute(select(SystemConfig))
        rows = result.scalars().all()
        return {r.key: r.value for r in rows}


async def restore_config() -> Optional[dict]:
    """启动时从数据库恢复配置，返回预设数据或 None"""
    data = await get_setting("preset.current")
    if data:
        logger.info("从数据库恢复上次配置")
    return data


async def save_detection_record(
    channel_name: str,
    camera_id: str,
    model_id: str,
    is_ok: bool,
    defect_count: int,
    result_json: dict | None,
    image_path: str = "",
    inference_ms: int = 0,
):
    """Fire-and-forget 写检测记录"""
    try:
        async with async_session() as session:
            session.add(DetectionRecord(
                channel_name=channel_name,
                camera_id=camera_id,
                model_id=model_id,
                is_ok=is_ok,
                defect_count=defect_count,
                result_json=result_json,
                image_path=image_path,
                inference_ms=inference_ms,
            ))
            await session.commit()
    except Exception as e:
        logger.error(f"保存检测记录失败: {e}")
