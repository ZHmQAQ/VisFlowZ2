# VModule 部署指南

本文档参考 VisFlowZ 的现场部署方式整理，但按 VModule 当前实际架构编写：后端是 FastAPI，前端是 Vue/Vite 构建后的静态页面，由后端在 `8100` 端口统一提供服务；当前没有 Electron 桌面壳。

## 1. 部署目标

VModule 面向 Windows 11 工业上位机，用作 PLC 外部视觉检测模块。当前保底业务流程是：

- 两个 USB 相机，OpenCV index `0` 和 `1`。
- 四个 PLC 寄存器：`D60/D61` 控制相机 1，`D62/D63` 控制相机 2。
- PLC 命令经 I/O 映射进入软元件：`D60 -> ED0`、`D62 -> ED2`。
- 检测状态经软元件写回 PLC：`EW0 -> D61`、`EW2 -> D63`。
- 命令 `1/2` 分别触发第一帧/第二帧，逐帧 ACK 写 `11/12`。
- 一轮帧收齐后汇总多模型结果，最终写 `7/6/5`。

## 2. 系统要求

| 项目 | 最低要求 | 推荐配置 |
| --- | --- | --- |
| 操作系统 | Windows 10 64 位 | Windows 11 64 位 |
| Python | 3.10+ | Conda env `envVModule` + Python 3.10/3.11 |
| Node.js | 18+ | 18 LTS 或 20 LTS |
| CPU | 4 核 | 8 核以上 |
| 内存 | 8 GB | 16 GB 以上 |
| GPU | 可 CPU 推理 | NVIDIA GPU + CUDA 版 PyTorch |
| 相机 | USB 摄像头 | USB/海康/大恒/RTSP 按项目适配 |
| 网络 | 能访问 PLC | 千兆局域网，固定 IP |

## 3. 脚本说明

| 脚本 | 用途 | 建议场景 |
| --- | --- | --- |
| `setup.bat` | 完整初始化，安装后端依赖，构建前端，创建数据目录 | 开发机或网络正常的现场机器 |
| `setuplite.bat` | 国内镜像初始化，优先使用/创建 Conda env `envVModule` | 国内现场首选 |
| `start.bat` | 优先启动 `VModule-Backend.exe`，没有 exe 时退回 Python | 生产启动入口 |
| `startlite.bat` | 仅 Python 启动，浏览器访问 | 调试和现场快速启动 |
| `load_preset.bat` | 调用 API 加载预设 | 切换站点或保底流程 |
| `verify_dual_usb_multiframe.bat` | 真实双 USB + 软寄存器验收 | 插相机后的现场自检 |
| `build_backend_exe.bat` | PyInstaller 打包后端 | 发布 exe 时使用 |

## 4. 首次部署

推荐现场路径：

```bat
setuplite.bat
startlite.bat
```

网络正常的开发路径：

```bat
setup.bat
start.bat
```

启动成功后访问：

- 页面：`http://localhost:8100`
- API 文档：`http://localhost:8100/docs`
- 健康检查：`http://localhost:8100/health`

## 5. 数据目录

默认数据根目录是：

```text
backend\data\
```

主要子目录：

| 路径 | 内容 |
| --- | --- |
| `backend\data\weights\` | 模型权重，例如 `.pt` |
| `backend\data\logs\` | 运行日志和错误日志 |
| `backend\data\cycles\` | 多帧检测每轮图片、帧 JSON、汇总 JSON |
| `backend\data\images\` | 单帧 OK 图片 |
| `backend\data\ng_images\` | 单帧 NG 图片 |
| `backend\data\vmodule.db` | SQLite 配置和记录库 |

`start.bat` 和 `startlite.bat` 会设置 `VMODULE_DATA_DIR=backend\data`，保证 Python 启动和 exe 启动使用同一份数据。

## 6. 加载双 USB 保底预设

启动服务后执行：

```bat
load_preset.bat presets\dual_usb_multiframe_baseline.json
```

预设包含：

| 配置项 | 值 |
| --- | --- |
| PLC | `PLC1`，默认 `192.168.1.10:502` |
| 相机 1 | `usb_cam1`，OpenCV index `0`，自动打开 |
| 相机 2 | `usb_cam2`，OpenCV index `1`，自动打开 |
| 相机 1 通道 | `cam1_baseline`，`ED0 -> EW0` |
| 相机 2 通道 | `cam2_baseline`，`ED2 -> EW2` |
| 帧计划 | 命令 `1/2`，ACK `11/12` |
| 保存策略 | 默认 `all`，保存每帧图像、推理 JSON、summary JSON |
| 复位策略 | `wait_plc_zero`，等待 PLC 命令寄存器归零 |

PLC 地址映射：

| PLC 地址 | VModule 地址 | 方向 | 用途 |
| --- | --- | --- | --- |
| `D60` | `ED0` | PLC 到 VModule | 相机 1 命令 |
| `D61` | `EW0` | VModule 到 PLC | 相机 1 ACK/最终结果 |
| `D62` | `ED2` | PLC 到 VModule | 相机 2 命令 |
| `D63` | `EW2` | VModule 到 PLC | 相机 2 ACK/最终结果 |

## 7. 现场验收

插好两个 USB 相机后运行：

```bat
verify_dual_usb_multiframe.bat
```

通过标准：

```text
Preset: OK
USB index=0 opened=True read=True shape=(480, 640, 3)
USB index=1 opened=True read=True shape=(480, 640, 3)
Workflow: cam1_final=7 cam2_final=7 parallel_ack=[11, 11]
```

这个验收不依赖真实 PLC。它直接写软元件：

- 写 `ED0=1`，期望 `EW0=11`。
- 写 `ED0=2`，期望 `EW0=12`，随后最终 `7/6/5`。
- 对 `ED2/EW2` 重复相同流程。
- 同时写 `ED0=1` 和 `ED2=1`，期望 `EW0=11`、`EW2=11`。

## 8. 模型部署

模型权重放入：

```text
backend\data\weights\
```

保底预设默认四个 frame model id：

```text
cam1_frame1_model
cam1_frame2_model
cam2_frame1_model
cam2_frame2_model
```

可以每帧独立模型，也可以多帧复用同一个模型。结果汇总语义：

| 缺陷类别 | 默认结果 |
| --- | --- |
| 无缺陷 | `7 = OK` |
| `YW` | `6 = NG 可返修` |
| `CL` / `JS` / `HH` | `5 = NG 不可返修` |

默认优先级：

```text
CL > JS > HH > YW > OK
```

## 9. 日志与存档

VModule 使用 loguru，支持：

- `TRACE`
- `DEBUG`
- `INFO`
- `WARNING`
- `ERROR`
- `CRITICAL`

日志文件：

```text
backend\data\logs\vmodule_YYYY-MM-DD.log
backend\data\logs\error_YYYY-MM-DD.log
```

多帧流程会生成：

- `cycle_id`：一轮检测链路。
- `frame_id`：每帧采集/推理记录。
- 每帧图片。
- 每帧推理 JSON。
- 最终 summary JSON。

通过 API 可切换日志级别：

```bat
curl -X PUT http://localhost:8100/api/system/log-level -H "Content-Type: application/json" -d "{\"level\":\"TRACE\"}"
```

## 10. PLC 网络与防火墙

需要放行：

| 方向 | 端口 | 用途 |
| --- | --- | --- |
| 出站 | TCP 502 | Modbus TCP 访问 PLC |
| 入站 | TCP 8100 | Web/API 访问 |
| 相机 SDK | 按厂商要求 | 海康/大恒/GigE 相机发现与采流 |

生产建议：

- 工业 PC 使用固定 IP。
- PLC 和上位机在同一生产网段。
- 禁用系统休眠。
- 相机 USB 口固定，不要频繁换口。
- Windows 更新避开生产时段。

## 11. 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `VMODULE_HOST` | `0.0.0.0` | 后端监听地址 |
| `VMODULE_PORT` | `8100` | 后端端口 |
| `VMODULE_DATA_DIR` | `backend\data` | 数据目录，启动脚本会设置 |
| `VMODULE_LOG_LEVEL` | `INFO` | 初始日志级别 |
| `VMODULE_DEFAULT_SCAN_CYCLE_MS` | `20` | 扫描周期 |
| `VMODULE_DEFAULT_MODBUS_TIMEOUT` | `1.0` | Modbus 超时秒数 |

临时改端口：

```bat
set VMODULE_PORT=8110
startlite.bat
```

## 12. 打包 exe

先构建前端并安装依赖：

```bat
setuplite.bat
```

再打包：

```bat
build_backend_exe.bat
```

输出：

```text
backend\dist\VModule-Backend.exe
```

如果 PyInstaller 生成的是目录模式，也可能是：

```text
backend\dist\VModule-Backend\VModule-Backend.exe
```

`start.bat` 会优先检测这两个位置。深度学习依赖体积较大，打包失败不影响 Python 模式运行。

## 13. 离线部署建议

离线现场推荐使用“预构建包”：

1. 在有网络的机器运行 `setuplite.bat`。
2. 确认 `frontend\dist\index.html` 存在。
3. 确认 `.venv` 或 Conda 环境可用。
4. 复制项目目录到现场机器。
5. 现场运行 `startlite.bat`。

更稳的离线包做法：

- 保留 `frontend\dist\`，现场不再跑 npm。
- 准备 Python wheelhouse 或直接复制已验证的 `.venv`。
- 模型提前放入 `backend\data\weights\`。
- 相机 SDK 在现场机器提前安装。

## 14. 自动化回归

部署脚本不默认跑完整测试，避免现场首次安装太慢。开发机建议手动执行：

```bat
python -m py_compile backend\app\core\detection\multiframe.py backend\app\api\detection.py backend\app\api\plc.py scripts\verify_dual_usb_multiframe.py
python -m pytest backend\tests\test_core.py backend\tests\test_multiframe_baseline.py -q
cd frontend
npm run build
cd ..
python scripts\verify_dual_usb_multiframe.py
```

最后一条需要两个真实 USB 相机。

## 15. 常见问题

### 前端页面打不开，但 API 文档能打开

通常是 `frontend\dist` 不存在或构建失败。运行：

```bat
setuplite.bat
```

### `verify_dual_usb_multiframe.bat` 读不到第二个相机

检查：

- Windows 相机权限。
- 是否有其他软件占用了相机。
- USB 口是否供电稳定。
- OpenCV index 是否需要从 `1` 改为 `2`。

### PLC 不触发

先用 API 或前端监控页确认软元件是否变化：

```bat
curl http://localhost:8100/api/plc/device/ED0
curl http://localhost:8100/api/plc/device/EW0
```

如果软元件不变化，优先检查 I/O 映射和 Modbus 连接。如果软元件变化但不拍照，检查多帧通道是否加载、相机是否打开。

### 日志太多

生产默认使用 `INFO`。只有排查扫描周期、PLC 命令边沿、相机采集和模型推理链路时再切到 `TRACE`。

### PyTorch 下载太慢

`setuplite.bat` 已使用清华 PyPI，但 CUDA 版 PyTorch 常需要按现场 CUDA 版本单独安装。可先安装 CPU 版验证握手，再补 GPU 版。
