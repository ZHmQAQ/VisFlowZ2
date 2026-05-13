"""GPU monitoring API."""
from fastapi import APIRouter

router = APIRouter(prefix="/gpu", tags=["GPU"])


@router.get("")
async def get_gpu_info():
    """Return available GPU utilization and memory information."""
    gpu_info = []

    try:
        import pynvml
        pynvml.nvmlInit()
        try:
            for i in range(pynvml.nvmlDeviceGetCount()):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8")
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                try:
                    temp = pynvml.nvmlDeviceGetTemperature(
                        handle, pynvml.NVML_TEMPERATURE_GPU
                    )
                except Exception:
                    temp = None
                gpu_info.append({
                    "index": i,
                    "name": name,
                    "gpu_util": util.gpu,
                    "memory_used": mem_info.used,
                    "memory_total": mem_info.total,
                    "memory_util": round(mem_info.used / mem_info.total * 100, 1)
                    if mem_info.total else 0,
                    "temperature": temp,
                })
        finally:
            pynvml.nvmlShutdown()
    except ImportError:
        try:
            import torch
            if torch.cuda.is_available():
                for i in range(torch.cuda.device_count()):
                    mem_used = torch.cuda.memory_allocated(i)
                    mem_total = torch.cuda.get_device_properties(i).total_memory
                    gpu_info.append({
                        "index": i,
                        "name": torch.cuda.get_device_name(i),
                        "gpu_util": None,
                        "memory_used": mem_used,
                        "memory_total": mem_total,
                        "memory_util": round(mem_used / mem_total * 100, 1)
                        if mem_total else 0,
                        "temperature": None,
                    })
        except Exception:
            pass
    except Exception:
        pass

    return {"gpus": gpu_info, "available": bool(gpu_info)}
