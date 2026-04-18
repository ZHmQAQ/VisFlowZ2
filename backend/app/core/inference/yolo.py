"""YOLO 推理引擎"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional
import numpy as np

from app.core.inference.base import InferenceBase

logger = logging.getLogger("vmodule.inference")


class YOLOInference(InferenceBase):
    """YOLO 推理引擎，支持 YOLOv5/v8"""

    def __init__(self, model_id: str, config: Dict[str, Any]):
        super().__init__(model_id, config)
        self._conf_threshold = config.get("conf_threshold", 0.25)
        self._iou_threshold = config.get("iou_threshold", 0.45)
        self._img_size = config.get("img_size", 640)

    async def load(self, model_path: str) -> bool:
        """加载 YOLO 模型"""
        try:
            import torch

            # PyTorch 2.6+ 默认 weights_only=True，旧 YOLOv5 权重含 numpy 会被拒绝
            # 允许 numpy 反序列化以兼容旧格式权重
            _orig_load = torch.load
            def _patched_load(*args, **kwargs):
                kwargs.setdefault("weights_only", False)
                return _orig_load(*args, **kwargs)
            torch.load = _patched_load

            try:
                # 尝试使用 ultralytics (YOLOv8)
                try:
                    from ultralytics import YOLO
                    self._model = YOLO(model_path)
                    self._model.to(self._device)
                    self._classes = self._model.names if hasattr(self._model, 'names') else []
                    if isinstance(self._classes, dict):
                        self._classes = list(self._classes.values())
                    logger.info(f"使用 ultralytics 加载模型: {model_path}")
                except ImportError:
                    # 回退到 torch.hub (YOLOv5)
                    self._model = torch.hub.load('ultralytics/yolov5', 'custom', path=model_path)
                    self._model.to(self._device)
                    self._model.conf = self._conf_threshold
                    self._model.iou = self._iou_threshold
                    self._classes = self._model.names if hasattr(self._model, 'names') else []
                    if isinstance(self._classes, dict):
                        self._classes = list(self._classes.values())
                    logger.info(f"使用 torch.hub 加载模型: {model_path}")
            finally:
                torch.load = _orig_load

            self._is_loaded = True
            logger.info(f"YOLO 模型加载成功: {self.model_id}, 类别: {self._classes}")
            return True

        except Exception as e:
            logger.error(f"加载 YOLO 模型失败: {e}")
            return False

    async def unload(self) -> None:
        """卸载模型"""
        try:
            if self._model:
                del self._model
                self._model = None

                # 清理 GPU 显存
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

            self._is_loaded = False
            logger.info(f"YOLO 模型已卸载: {self.model_id}")
        except Exception as e:
            logger.error(f"卸载模型失败: {e}")

    async def predict(self, image: np.ndarray, **kwargs) -> Dict[str, Any]:
        """执行推理"""
        if not self._is_loaded or self._model is None:
            return {"detections": [], "inference_time": 0, "error": "模型未加载"}

        try:
            start_time = time.time()

            # 推理参数：外部传入 > 模型配置 > 默认值
            effective_size = kwargs.get("imgsz", self._img_size)
            effective_conf = kwargs.get("conf", self._conf_threshold)
            effective_iou = kwargs.get("iou", 0.45)
            effective_max_det = kwargs.get("max_det", 300)
            effective_augment = kwargs.get("augment", False)

            logger.debug(
                f"[推理] model={self.model_id} | img_shape={image.shape} | "
                f"imgsz={effective_size} | conf={effective_conf:.2f} | "
                f"iou={effective_iou:.2f} | max_det={effective_max_det} | "
                f"augment={effective_augment} | device={self._device}"
            )

            # 执行推理
            results = self._model(
                image,
                imgsz=effective_size,
                conf=effective_conf,
                iou=effective_iou,
                max_det=effective_max_det,
                augment=effective_augment
            )

            # 解析结果
            detections = []

            # ultralytics (YOLOv8) 格式
            if hasattr(results, '__iter__') and hasattr(results[0], 'boxes'):
                for result in results:
                    boxes = result.boxes
                    for i in range(len(boxes)):
                        box = boxes[i]
                        cls_id = int(box.cls[0])
                        conf = float(box.conf[0])
                        xyxy = box.xyxy[0].tolist()

                        detections.append({
                            "class": self._classes[cls_id] if cls_id < len(self._classes) else str(cls_id),
                            "class_id": cls_id,
                            "confidence": round(conf, 4),
                            "bbox": [int(x) for x in xyxy]
                        })
            # torch.hub (YOLOv5) 格式
            elif hasattr(results, 'xyxy'):
                for det in results.xyxy[0]:
                    x1, y1, x2, y2, conf, cls_id = det.tolist()
                    cls_id = int(cls_id)
                    detections.append({
                        "class": self._classes[cls_id] if cls_id < len(self._classes) else str(cls_id),
                        "class_id": cls_id,
                        "confidence": round(conf, 4),
                        "bbox": [int(x1), int(y1), int(x2), int(y2)]
                    })

            inference_time = (time.time() - start_time) * 1000  # 转换为毫秒

            return {
                "detections": detections,
                "inference_time": round(inference_time, 2),
                "count": len(detections)
            }

        except Exception as e:
            logger.error(f"推理失败: {e}")
            return {"detections": [], "inference_time": 0, "error": str(e)}

    async def predict_batch(self, images: list) -> list:
        """批量推理"""
        results = []
        for img in images:
            result = await self.predict(img)
            results.append(result)
        return results

    def get_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        info = super().get_info()
        info.update({
            "type": "yolo",
            "conf_threshold": self._conf_threshold,
            "iou_threshold": self._iou_threshold,
            "img_size": self._img_size,
        })
        return info
