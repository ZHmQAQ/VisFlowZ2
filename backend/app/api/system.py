"""系统管理 API — 日志/设置/检测记录"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import select, func, desc, and_

from app.db.database import async_session
from app.db.models import DetectionRecord
from app.utils.logger import get_log_level, set_log_level
from app.core.persistence import (
    get_all_settings, set_setting, schedule_save,
)
from app.config import settings

router = APIRouter(prefix="/system", tags=["system"])


# ── 日志级别 ──

@router.get("/log-level")
async def api_get_log_level():
    return {"level": get_log_level()}


@router.put("/log-level")
async def api_set_log_level(body: dict):
    level = set_log_level(body["level"])
    return {"level": level}


# ── 设置 ──

@router.get("/settings")
async def api_get_settings():
    data = await get_all_settings()
    # 合并运行时配置
    data.setdefault("save_ok_images", settings.SAVE_OK_IMAGES)
    data.setdefault("save_ng_images", settings.SAVE_NG_IMAGES)
    return data


@router.put("/settings")
async def api_update_settings(body: dict):
    for k, v in body.items():
        await set_setting(k, v)
        # 同步到运行时
        if k == "save_ok_images":
            settings.SAVE_OK_IMAGES = bool(v)
        elif k == "save_ng_images":
            settings.SAVE_NG_IMAGES = bool(v)
    return {"status": "ok"}


@router.post("/save-now")
async def api_save_now():
    schedule_save(delay=0.1)
    return {"status": "scheduled"}


# ── 检测记录 ──

@router.get("/records")
async def api_list_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    camera_id: str = Query("", description="筛选相机"),
    channel_name: str = Query("", description="筛选通道"),
    is_ok: str = Query("", description="ok/ng/空=全部"),
):
    async with async_session() as session:
        q = select(DetectionRecord)
        count_q = select(func.count(DetectionRecord.id))

        if camera_id:
            q = q.where(DetectionRecord.camera_id == camera_id)
            count_q = count_q.where(DetectionRecord.camera_id == camera_id)
        if channel_name:
            q = q.where(DetectionRecord.channel_name == channel_name)
            count_q = count_q.where(DetectionRecord.channel_name == channel_name)
        if is_ok == "ok":
            q = q.where(DetectionRecord.is_ok == True)
            count_q = count_q.where(DetectionRecord.is_ok == True)
        elif is_ok == "ng":
            q = q.where(DetectionRecord.is_ok == False)
            count_q = count_q.where(DetectionRecord.is_ok == False)

        total = (await session.execute(count_q)).scalar() or 0
        rows = (await session.execute(
            q.order_by(desc(DetectionRecord.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )).scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": r.id,
                    "channel_name": r.channel_name,
                    "camera_id": r.camera_id,
                    "model_id": r.model_id,
                    "is_ok": r.is_ok,
                    "defect_count": r.defect_count,
                    "image_path": r.image_path,
                    "inference_ms": r.inference_ms,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ],
        }


@router.get("/records/statistics")
async def api_record_statistics(
    camera_id: str = "",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
):
    if not end_time:
        end_time = datetime.now()
    if not start_time:
        start_time = end_time.replace(hour=0, minute=0, second=0, microsecond=0)

    conditions = [
        DetectionRecord.created_at >= start_time,
        DetectionRecord.created_at <= end_time,
    ]
    if camera_id:
        conditions.append(DetectionRecord.camera_id == camera_id)

    async with async_session() as session:
        total = (await session.execute(
            select(func.count(DetectionRecord.id)).where(and_(*conditions))
        )).scalar() or 0
        ok_count = (await session.execute(
            select(func.count(DetectionRecord.id)).where(
                and_(*conditions, DetectionRecord.is_ok == True)
            )
        )).scalar() or 0
        ng_count = total - ok_count

        by_camera_rows = (await session.execute(
            select(DetectionRecord.camera_id, func.count(DetectionRecord.id))
            .where(and_(*conditions))
            .group_by(DetectionRecord.camera_id)
        )).all()

    return {
        "total_count": total,
        "ok_count": ok_count,
        "ng_count": ng_count,
        "ok_rate": round(ok_count / total * 100, 2) if total else 0,
        "by_camera": {row[0] or "unknown": row[1] for row in by_camera_rows},
        "time_range": {"start": start_time.isoformat(), "end": end_time.isoformat()},
    }


@router.delete("/records/{record_id}")
async def api_delete_record(record_id: int):
    async with async_session() as session:
        result = await session.execute(
            select(DetectionRecord).where(DetectionRecord.id == record_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            return {"message": "记录不存在"}
        await session.delete(record)
        await session.commit()
    return {"message": "记录已删除"}
