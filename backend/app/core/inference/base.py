"""推理引擎抽象基类"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import numpy as np


class InferenceBase(ABC):
    """推理引擎抽象基类"""

    def __init__(self, model_id: str, config: Dict[str, Any]):
        self.model_id = model_id
        self.config = config
        self._is_loaded = False
        self._model = None
        self._classes: List[str] = []
        self._device = config.get("device", "cuda:0")

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @property
    def classes(self) -> List[str]:
        return self._classes

    @abstractmethod
    async def load(self, model_path: str) -> bool:
        """加载模型"""
        pass

    @abstractmethod
    async def unload(self) -> None:
        """卸载模型"""
        pass

    @abstractmethod
    async def predict(self, image: np.ndarray, **kwargs) -> Dict[str, Any]:
        """执行推理

        Args:
            image: 输入图像 (BGR numpy array)
            **kwargs: 推理参数 (imgsz, conf, iou, max_det, augment 等)

        返回格式:
        {
            "detections": [
                {
                    "class": "defect_name",
                    "confidence": 0.95,
                    "bbox": [x1, y1, x2, y2]
                }
            ],
            "inference_time": 0.025
        }
        """
        pass

    def get_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "model_id": self.model_id,
            "is_loaded": self._is_loaded,
            "device": self._device,
            "classes": self._classes,
        }
