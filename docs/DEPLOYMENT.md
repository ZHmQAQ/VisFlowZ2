# VModule 部署指南

## 系统要求

| 项目 | 最低要求 | 推荐配置 |
|------|---------|---------|
| OS | Windows 10 64位 | Windows 11 |
| Python | 3.10+ | 3.11 |
| CPU | 4核 | 8核+ |
| 内存 | 8GB | 16GB+ |
| GPU | 无（CPU推理） | NVIDIA RTX 3060+（CUDA 推理） |
| 网络 | 能连接PLC的局域网 | 千兆以太网 |

## 快速部署（3步）

```
git clone <仓库地址> VModule
cd VModule
setup.bat          ← 安装依赖（仅首次）
start.bat          ← 启动服务
```

启动后访问 http://localhost:8100/docs 查看 API 文档。

## 详细步骤

### 1. 安装 Python

从 https://python.org 下载 Python 3.11+，安装时勾选 **"Add to PATH"**。

验证：
```bash
python --version
# Python 3.11.x
```

### 2. 克隆项目

```bash
git clone <仓库地址> D:\VModule
cd D:\VModule
```

### 3. 安装依赖

**方式A：自动安装（推荐）**
```
setup.bat
```

**方式B：手动安装**
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

#### GPU 加速（可选）

如果有 NVIDIA GPU，替换 CPU 版 PyTorch：
```bash
pip uninstall torch
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

### 4. 放置模型文件

将 YOLO 模型文件（.pt）放到 `backend/data/weights/` 目录：
```
backend/data/weights/
├── yolo_default.pt      ← 默认模型
├── yolo_sorting.pt      ← 分拣模型（可选）
└── ...
```

### 5. 启动服务

```
start.bat
```

看到以下输出表示成功：
```
INFO:     Uvicorn running on http://0.0.0.0:8100
INFO:     Started scanner engine, cycle=20ms
```

## 网络配置

### PLC 连接拓扑

```
┌──────────┐    Modbus TCP    ┌──────────┐
│ 信捷 PLC  │◄──────────────►│  VModule  │
│ 192.168.1.10:502          │  PC 端    │
└──────────┘                 └──────────┘
      │                            │
   生产线                     工业相机(USB/GigE)
```

### 防火墙设置

VModule 需要以下网络访问：
- **出站 TCP 502**：连接 PLC（Modbus TCP）
- **入站 TCP 8100**：API 服务端口（如需远程访问）
- **入站/出站**：相机 SDK 端口（大恒/海康 GigE 相机）

### 多 PLC 配置

VModule 支持同时连接多台 PLC，每台 PLC 需要独立 IP：
```
PLC1: 192.168.1.10:502  (unit_id=1)
PLC2: 192.168.1.11:502  (unit_id=1)
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VMODULE_HOST` | 0.0.0.0 | 监听地址 |
| `VMODULE_PORT` | 8100 | API 端口 |
| `VMODULE_DEBUG` | true | 调试模式（生产环境设为 false） |
| `VMODULE_DEFAULT_SCAN_CYCLE_MS` | 20 | 扫描周期(ms) |
| `VMODULE_DEFAULT_MODBUS_TIMEOUT` | 1.0 | Modbus 超时(秒) |

## 目录结构

```
VModule/
├── start.bat                 启动服务
├── setup.bat                 安装依赖
├── load_preset.bat           加载预设
├── presets/                   预设配置
│   ├── single_station.json   单工位
│   ├── dual_station.json     双工位
│   └── sorting_line.json     分拣线
├── backend/
│   ├── run.py                入口
│   ├── requirements.txt      依赖
│   ├── data/
│   │   └── weights/          模型文件
│   └── app/                  源码
└── docs/                     文档
```

## 生产环境建议

1. **关闭调试模式**：设置环境变量 `VMODULE_DEBUG=false`
2. **固定IP**：VModule 所在 PC 使用静态 IP
3. **开机自启**：将 `start.bat` 快捷方式放入启动文件夹
4. **日志**：生产环境建议将日志输出到文件，在 `run.py` 中配置 logging
5. **UPS**：工控 PC 配备 UPS 防止断电丢失检测数据
