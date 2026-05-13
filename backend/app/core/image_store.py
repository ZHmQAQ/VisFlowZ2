"""
图片存储管道 — 线程池写磁盘，不阻塞扫描

路径结构:
  DATA_DIR/images/{YYYYMMDD}/{camera_id}/{HHMMSS_fff}.jpg      OK图片
  DATA_DIR/ng_images/{YYYYMMDD}/{camera_id}/{HHMMSS_fff}.jpg   NG图片
  DATA_DIR/cycles/{YYYYMMDD}/{cycle_id}/{frame_id}.jpg         多帧流程逐帧图片
"""
from __future__ import annotations
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import json

from app.config import settings

logger = logging.getLogger("vmodule.image_store")

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="img-save")


def _save_sync(path: Path, image: np.ndarray) -> str:
    """同步写图片（在线程池中执行）"""
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image)
    return str(path.relative_to(settings.DATA_DIR))


async def save_detection_image(
    camera_id: str,
    image: np.ndarray,
    is_ok: bool,
) -> str:
    """
    异步保存检测图片。

    根据 is_ok 和配置决定是否保存:
      - OK 图片: settings.SAVE_OK_IMAGES
      - NG 图片: settings.SAVE_NG_IMAGES

    Returns: 相对 DATA_DIR 的路径，或空字符串（未保存）
    """
    if is_ok and not settings.SAVE_OK_IMAGES:
        return ""
    if not is_ok and not settings.SAVE_NG_IMAGES:
        return ""

    now = datetime.now()
    date_dir = now.strftime("%Y%m%d")
    filename = now.strftime("%H%M%S_%f")[:-3] + ".jpg"

    base = "images" if is_ok else "ng_images"
    path = settings.DATA_DIR / base / date_dir / camera_id / filename

    loop = asyncio.get_running_loop()
    try:
        rel_path = await loop.run_in_executor(_executor, _save_sync, path, image)
        return rel_path
    except Exception as e:
        logger.error(f"保存图片失败: {e}")
        return ""


def _save_cycle_frame_sync(path: Path, image: np.ndarray) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image)
    return str(path.relative_to(settings.DATA_DIR))


def _write_json_sync(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path.relative_to(settings.DATA_DIR))


async def save_cycle_frame(
    cycle_id: str,
    frame_id: str,
    camera_id: str,
    image: np.ndarray,
    ext: str = "jpg",
) -> str:
    """保存多帧检测流程中的单帧图片，返回相对 DATA_DIR 的路径。"""
    now = datetime.now()
    date_dir = now.strftime("%Y%m%d")
    safe_frame_id = frame_id.replace(":", "_").replace("/", "_").replace("\\", "_")
    suffix = ext.lower().lstrip(".") or "jpg"
    path = settings.DATA_DIR / "cycles" / date_dir / cycle_id / camera_id / f"{safe_frame_id}.{suffix}"

    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(_executor, _save_cycle_frame_sync, path, image)
    except Exception as e:
        logger.error(f"保存多帧图片失败: {e}")
        return ""


async def save_cycle_json(cycle_id: str, name: str, payload: dict) -> str:
    """保存多帧检测流程的 JSON 记录。"""
    now = datetime.now()
    date_dir = now.strftime("%Y%m%d")
    safe_name = name.replace(":", "_").replace("/", "_").replace("\\", "_")
    path = settings.DATA_DIR / "cycles" / date_dir / cycle_id / f"{safe_name}.json"

    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(_executor, _write_json_sync, path, payload)
    except Exception as e:
        logger.error(f"保存多帧 JSON 失败: {e}")
        return ""
