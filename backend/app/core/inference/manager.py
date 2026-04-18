"""推理引擎管理器"""
import asyncio
import logging
from typing import Dict, Optional, Type
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
import numpy as np

from app.core.inference.base import InferenceBase
from app.core.inference.yolo import YOLOInference

logger = logging.getLogger("vmodule.inference")


class InferenceManager:
    """推理引擎管理器，统一管理模型加载和推理队列"""

    # 推理引擎类型注册表
    ENGINE_TYPES: Dict[str, Type[InferenceBase]] = {
        "yolo": YOLOInference,
    }

    def __init__(self, queue_size: int = 100, workers: int = 2):
        self._engines: Dict[str, InferenceBase] = {}
        self._lock = asyncio.Lock()
        self._queue = Queue(maxsize=queue_size)
        self._executor = ThreadPoolExecutor(max_workers=workers)

    def register_type(self, type_name: str, engine_class: Type[InferenceBase]):
        """注册新的推理引擎类型"""
        self.ENGINE_TYPES[type_name] = engine_class
        logger.info(f"注册推理引擎类型: {type_name}")

    async def load_model(
        self,
        model_id: str,
        model_path: str,
        engine_type: str = "yolo",
        config: dict = None
    ) -> bool:
        """加载模型"""
        async with self._lock:
            if model_id in self._engines:
                logger.warning(f"模型已加载: {model_id}")
                return True

            if engine_type not in self.ENGINE_TYPES:
                logger.error(f"未知推理引擎类型: {engine_type}")
                return False

            config = config or {}
            engine_class = self.ENGINE_TYPES[engine_type]
            engine = engine_class(model_id, config)

            success = await engine.load(model_path)
            if success:
                self._engines[model_id] = engine
                logger.info(f"模型加载成功: {model_id}")
            return success

    async def unload_model(self, model_id: str) -> bool:
        """卸载模型"""
        async with self._lock:
            if model_id not in self._engines:
                return False

            engine = self._engines[model_id]
            await engine.unload()
            del self._engines[model_id]
            logger.info(f"模型已卸载: {model_id}")
            return True

    async def predict(self, model_id: str, image: np.ndarray, **kwargs) -> dict:
        """执行推理

        Args:
            model_id: 模型 ID
            image: 输入图像
            **kwargs: 推理参数 (imgsz, conf, iou, max_det, augment 等)
        """
        engine = self._engines.get(model_id)
        if not engine:
            return {"error": f"模型未加载: {model_id}"}

        return await engine.predict(image, **kwargs)

    async def predict_with_default(self, image: np.ndarray, **kwargs) -> dict:
        """使用默认模型推理"""
        if not self._engines:
            return {"error": "没有可用的模型"}

        # 使用第一个加载的模型
        model_id = list(self._engines.keys())[0]
        return await self.predict(model_id, image, **kwargs)

    def get_engine(self, model_id: str) -> Optional[InferenceBase]:
        """获取推理引擎实例"""
        return self._engines.get(model_id)

    def get_all_engines(self) -> Dict[str, InferenceBase]:
        """获取所有推理引擎"""
        return self._engines.copy()

    def get_model_info(self, model_id: str) -> Optional[dict]:
        """获取模型信息"""
        engine = self._engines.get(model_id)
        if not engine:
            return None
        return engine.get_info()

    def get_all_info(self) -> list:
        """获取所有模型信息"""
        return [engine.get_info() for engine in self._engines.values()]

    def get_loaded_count(self) -> int:
        """获取已加载模型数量"""
        return len(self._engines)

    async def unload_all(self):
        """卸载所有模型"""
        for model_id in list(self._engines.keys()):
            await self.unload_model(model_id)
        logger.info("所有模型已卸载")


# 全局单例
inference_manager = InferenceManager()
