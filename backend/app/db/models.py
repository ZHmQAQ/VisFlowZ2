"""数据库 ORM 模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Float
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class SystemConfig(Base):
    """系统配置 KV 存储"""
    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True)
    value = Column(JSON)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DetectionRecord(Base):
    """检测记录"""
    __tablename__ = "detection_records"

    id = Column(Integer, primary_key=True, index=True)
    channel_name = Column(String(100), index=True)
    camera_id = Column(String(100), index=True)
    model_id = Column(String(100))
    is_ok = Column(Boolean, default=True)
    defect_count = Column(Integer, default=0)
    result_json = Column(JSON)
    image_path = Column(String(500))
    inference_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
