"""日志工具 — loguru 三路输出"""
import sys
from loguru import logger
from app.config import settings

_handler_ids = {"stdout": None, "file": None, "error": None}
_current_level = "DEBUG"


def setup_logger():
    """配置日志系统: 控制台 + 全量日志文件 + 错误日志文件"""
    global _current_level
    logger.remove()

    log_level = settings.LOG_LEVEL if not settings.DEBUG else "DEBUG"
    _current_level = log_level

    _handler_ids["stdout"] = logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=log_level,
        filter=_quiet_poll_filter,
    )

    _handler_ids["file"] = logger.add(
        str(settings.LOGS_DIR / "vmodule_{time:YYYY-MM-DD}.log"),
        rotation="00:00",
        retention=settings.LOG_RETENTION,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=log_level,
        encoding="utf-8",
    )

    _handler_ids["error"] = logger.add(
        str(settings.LOGS_DIR / "error_{time:YYYY-MM-DD}.log"),
        rotation="00:00",
        retention=settings.LOG_RETENTION,
        level="ERROR",
        encoding="utf-8",
    )

    logger.info(f"日志系统初始化完成 — 级别: {log_level}, 路径: {settings.LOGS_DIR}")


def _quiet_poll_filter(record):
    """过滤高频轮询日志"""
    msg = record["message"]
    quiet = ("/api/plc/engine/status", "/api/camera/list", "/health")
    return not any(p in msg for p in quiet)


def set_log_level(level: str) -> str:
    """运行时切换日志级别（控制台 + 全量日志文件）"""
    global _current_level
    level = level.upper()
    valid = ("TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    if level not in valid:
        raise ValueError(f"无效日志级别: {level}, 可选: {', '.join(valid)}")

    if _handler_ids["stdout"] is not None:
        logger.remove(_handler_ids["stdout"])
    if _handler_ids["file"] is not None:
        logger.remove(_handler_ids["file"])

    _handler_ids["stdout"] = logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=level,
        filter=_quiet_poll_filter,
    )

    _handler_ids["file"] = logger.add(
        str(settings.LOGS_DIR / "vmodule_{time:YYYY-MM-DD}.log"),
        rotation="00:00",
        retention=settings.LOG_RETENTION,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=level,
        encoding="utf-8",
    )

    _current_level = level
    logger.info(f"日志级别已切换为: {level}")
    return level


def get_log_level() -> str:
    return _current_level


__all__ = ["logger", "setup_logger", "set_log_level", "get_log_level"]
