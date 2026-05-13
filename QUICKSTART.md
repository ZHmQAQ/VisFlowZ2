# VModule 快速开始

这份文档只写现场最常用路径：在 Windows 11 工业电脑上部署 VModule，接入两个 USB 相机，用 `D60/D61` 和 `D62/D63` 验证多帧轮询保底流程。

## 当前可用入口

| 目标 | 脚本 | 说明 |
| --- | --- | --- |
| 完整初始化 | `setup.bat` | 创建或复用 Python 环境，安装后端依赖，构建前端，创建数据目录 |
| 国内网络初始化 | `setuplite.bat` | 使用清华 PyPI 和 npmmirror，优先创建/复用 Conda 环境 `envVModule` |
| 常规启动 | `start.bat` | 优先使用后端 exe；没有 exe 时使用 Python 环境启动 |
| 轻量启动 | `startlite.bat` | 只使用 Python 环境启动，浏览器访问 |
| 加载预设 | `load_preset.bat` | 向运行中的服务加载 JSON 预设 |
| 双 USB 验收 | `verify_dual_usb_multiframe.bat` | 检查预设、USB index 0/1、软寄存器流程 |
| 后端打包 | `build_backend_exe.bat` | 使用 `backend/pyinstaller.spec` 打包后端 exe，可选 |

VModule 当前没有 Electron 桌面壳，部署形态是 FastAPI 服务静态前端，然后用浏览器访问。

## 一分钟启动

```bat
setuplite.bat
startlite.bat
```

启动后访问：

- Web 页面：`http://localhost:8100`
- API 文档：`http://localhost:8100/docs`
- 健康检查：`http://localhost:8100/health`

如果现场网络正常，也可以使用：

```bat
setup.bat
start.bat
```

## 双 USB 多帧保底流程

推荐先插好两个 USB 相机，再运行：

```bat
verify_dual_usb_multiframe.bat
```

脚本会做三件事：

1. 检查 `presets\dual_usb_multiframe_baseline.json` 的 I/O 映射和帧计划。
2. 用 OpenCV DSHOW 打开 `index=0` 和 `index=1` 并读取真实图像。
3. 不依赖 PLC，直接驱动软元件验证 `ED0/EW0`、`ED2/EW2` 流程。

期望输出包含类似内容：

```text
Preset: OK
USB index=0 opened=True read=True shape=(480, 640, 3)
USB index=1 opened=True read=True shape=(480, 640, 3)
Workflow: cam1_final=7 cam2_final=7 parallel_ack=[11, 11]
```

## 加载保底预设

先启动服务：

```bat
startlite.bat
```

再开一个命令行窗口执行：

```bat
load_preset.bat presets\dual_usb_multiframe_baseline.json
```

保底预设的语义：

| PLC 寄存器 | VModule 软元件 | 用途 |
| --- | --- | --- |
| `D60` | `ED0` | 相机 1 命令，`1` 拍第一帧，`2` 拍第二帧 |
| `D61` | `EW0` | 相机 1 应答/结果，逐帧 `11/12`，最终 `7/6/5` |
| `D62` | `ED2` | 相机 2 命令，`1` 拍第一帧，`2` 拍第二帧 |
| `D63` | `EW2` | 相机 2 应答/结果，逐帧 `11/12`，最终 `7/6/5` |

最终结果码沿用 VisFlowZ 语义：

| 结果码 | 含义 |
| --- | --- |
| `7` | OK |
| `6` | NG 可返修 |
| `5` | NG 不可返修 |

PLC 命令寄存器归零前，同一通道不会开始下一轮同命令触发。

## 模型放置

YOLO 或其他模型权重放在：

```text
backend\data\weights\
```

保底预设中四个默认模型 ID 是：

```text
cam1_frame1_model
cam1_frame2_model
cam2_frame1_model
cam2_frame2_model
```

现场没有四个真实模型时，可以先复用同一个模型 ID 验证握手，再换成每帧独立模型。

## 常用检查命令

```bat
python -m py_compile backend\app\core\detection\multiframe.py backend\app\api\detection.py backend\app\api\plc.py scripts\verify_dual_usb_multiframe.py
python -m pytest backend\tests\test_core.py backend\tests\test_multiframe_baseline.py -q
cd frontend
npm run build
cd ..
```

## 常见问题

### 找不到 `frontend\dist\index.html`

前端还没有构建。执行：

```bat
setuplite.bat
```

或手动：

```bat
cd frontend
npm install --registry=https://registry.npmmirror.com
npm run build
cd ..
```

### USB 相机 index 不对

保底预设默认：

- `usb_cam1`: OpenCV index `0`
- `usb_cam2`: OpenCV index `1`

如果现场顺序反了，修改 `presets\dual_usb_multiframe_baseline.json` 中两个 `connection.index`。

### 端口占用

默认端口是 `8100`。临时改端口：

```bat
set VMODULE_PORT=8110
startlite.bat
```

### 需要打包 exe

先确保前端已构建，然后运行：

```bat
build_backend_exe.bat
```

深度学习依赖较大，exe 打包耗时和体积都可能比较高。现场优先推荐 Conda/Python 启动，exe 作为后续稳定发布选项。
