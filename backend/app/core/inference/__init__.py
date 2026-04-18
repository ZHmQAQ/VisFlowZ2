"""推理引擎模块"""
from app.core.inference.base import InferenceBase
from app.core.inference.yolo import YOLOInference
from app.core.inference.manager import InferenceManager, inference_manager

__all__ = ["InferenceBase", "YOLOInference", "InferenceManager", "inference_manager"]
