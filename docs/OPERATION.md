# VModule 操作指南

> 本指南面向 **PLC 工程师**，用 PLC 软元件语言描述所有操作。

## 核心概念

VModule 是一个 **PLC 虚拟扩展模块**。你可以把它理解为一个带摄像头和AI的智能扩展模块，通过 Modbus TCP 挂在信捷 PLC 上。

```
你的 PLC 程序                    VModule（虚拟扩展模块）
┌─────────────┐                 ┌─────────────────────┐
│ SET M100     │ ──Modbus──►    │ EX0 上升沿 → 拍照    │
│              │                │ AI推理 → OK/NG判定    │
│ LD  M200     │ ◄──Modbus──   │ 结果写入 EY0/EY1     │
│ ANI M201     │                │ 缺陷数写入 EW0       │
│ OUT Y0       │ ← NG报警      │                      │
└─────────────┘                 └─────────────────────┘
```

## 软元件地址表

### 外部 I/O（与 PLC 通信）

| 前缀 | 类型 | 方向 | 容量 | 说明 |
|------|------|------|------|------|
| **EX** | 位 | PLC→VModule | 256点 | 外部输入（触发信号等） |
| **EY** | 位 | VModule→PLC | 256点 | 外部输出（完成/结果等） |
| **ED** | 字 | PLC→VModule | 256字 | 外部输入寄存器（型号码等） |
| **EW** | 字 | VModule→PLC | 256字 | 外部输出寄存器（缺陷数等） |

### 内部软元件

| 前缀 | 类型 | 容量 | 说明 |
|------|------|------|------|
| **VM** | 位 | 4096点 | 内部辅助继电器 |
| **VD** | 字 | 4096字 | 内部数据寄存器 |
| **VT** | 定时器 | 256个 | 内部定时器（10ms 单位） |
| **VC** | 计数器 | 256个 | 内部计数器 |
| **SM** | 位 | 256点 | 系统特殊继电器（只读） |
| **SD** | 字 | 256字 | 系统特殊寄存器（只读） |

### 系统软元件

| 地址 | 说明 |
|------|------|
| SM0 | 常 ON |
| SM1 | 常 OFF |
| SM10 | 扫描引擎运行中 |
| SM11 | 通信异常 |
| SD0 | 当前扫描周期 (ms) |
| SD1 | 已连接 PLC 数量 |

---

## 典型操作流程

### 一、单工位检测

#### 1. 启动 VModule

双击 `start.bat`，等待看到 "Started scanner engine"。

#### 2. 加载预设

```
load_preset.bat presets\single_station.json
```

或通过 API 手动配置（见下文）。

#### 3. PLC 侧编程

在信捷 XG PLC 中编写以下梯形图逻辑：

```
(* 触发拍照 — 当工件到位时置 M100 *)
LD   X0              // 光电传感器
LDP  X0              // 上升沿
SET  M100            // 触发VModule拍照

(* 读取结果 — M200=完成, M201=OK/NG *)
LD   M200            // 检测完成
RST  M100            // 清除触发
AND  M201            // 判断结果
OUT  Y0              // OK → 放行

LD   M200
ANI  M201            // NG
OUT  Y1              // NG → 报警/剔除

(* 读取详细数据 *)
// D200 = 缺陷数量
// D201 = 推理耗时(ms)
```

#### 4. I/O 映射对照表

| PLC 侧 | 方向 | VModule 侧 | 说明 |
|---------|------|-----------|------|
| M100 | → | EX0 | 拍照触发 |
| M200 | ← | EY0 | 检测完成 |
| M201 | ← | EY1 | OK=1 / NG=0 |
| D200 | ← | EW0 | 缺陷数量 |
| D201 | ← | EW1 | 推理耗时(ms) |

---

### 二、通过 API 配置

所有配置都可通过 HTTP API 完成。打开浏览器访问 http://localhost:8100/docs 查看交互式文档。

#### 添加 PLC 连接

```bash
curl -X POST http://localhost:8100/api/plc/connections \
  -H "Content-Type: application/json" \
  -d '{"name":"PLC1","host":"192.168.1.10","port":502,"unit_id":1}'
```

#### 添加 I/O 映射

```bash
curl -X POST http://localhost:8100/api/plc/mappings \
  -H "Content-Type: application/json" \
  -d '{"plc_name":"PLC1","plc_addr":"M100","vmodule_addr":"EX0","description":"拍照触发"}'
```

#### 批量添加映射

```bash
curl -X POST http://localhost:8100/api/plc/mappings/batch \
  -H "Content-Type: application/json" \
  -d '[
    {"plc_name":"PLC1","plc_addr":"M100","vmodule_addr":"EX0","description":"触发"},
    {"plc_name":"PLC1","plc_addr":"M200","vmodule_addr":"EY0","description":"完成"},
    {"plc_name":"PLC1","plc_addr":"M201","vmodule_addr":"EY1","description":"OK/NG"}
  ]'
```

#### 添加检测通道

```bash
curl -X POST http://localhost:8100/api/detection/channels \
  -H "Content-Type: application/json" \
  -d '{
    "name":"工位1",
    "trigger_addr":"EX0",
    "camera_id":"cam1",
    "model_id":"yolo_default",
    "done_addr":"EY0",
    "result_addr":"EY1",
    "defect_count_addr":"EW0",
    "inference_time_addr":"EW1"
  }'
```

---

### 三、调试与监控

#### 读取软元件状态

```bash
# 读单个
curl http://localhost:8100/api/plc/device/EX0
# 返回: {"address":"EX0","value":false}

# 批量读
curl -X POST http://localhost:8100/api/plc/device/bulk-read \
  -H "Content-Type: application/json" \
  -d '{"addresses":["EX0","EY0","EY1","EW0","VD0"]}'

# 导出一段区域
curl http://localhost:8100/api/plc/device/dump/VM?start=0&count=16
```

#### 手动写入软元件（调试用）

```bash
# 模拟触发信号（不需要PLC也能测试）
curl -X POST http://localhost:8100/api/plc/device/write \
  -H "Content-Type: application/json" \
  -d '{"address":"EX0","value":true}'
```

#### 查看引擎状态

```bash
curl http://localhost:8100/api/plc/engine/status
# 返回:
# {
#   "running": true,
#   "scan_count": 15234,
#   "last_scan_ms": 18.5,
#   "target_cycle_ms": 20,
#   "plc_clients": 1,
#   "io_mappings": 5,
#   "program_blocks": 1
# }
```

#### 查看系统健康

```bash
curl http://localhost:8100/health
```

---

## 检测通道地址分配建议

### 多工位地址规划

每个工位占用固定偏移，便于维护：

| 工位 | 触发 | 忙碌 | 完成 | OK/NG | 缺陷数 | 耗时 | 累计 | NG数 |
|------|------|------|------|-------|--------|------|------|------|
| 1号 | EX0 | VM100 | EY0 | EY1 | EW0 | EW1 | VD0 | VD1 |
| 2号 | EX1 | VM101 | EY2 | EY3 | EW2 | EW3 | VD2 | VD3 |
| 3号 | EX2 | VM102 | EY4 | EY5 | EW4 | EW5 | VD4 | VD5 |
| 4号 | EX3 | VM103 | EY6 | EY7 | EW6 | EW7 | VD6 | VD7 |

**规律**: 工位 N 的地址 = 基址 + N×2（位）或 N×2（字）

### PLC 侧对应映射建议

| VModule | PLC 建议 | 说明 |
|---------|---------|------|
| EX0~EX15 | M100~M115 | 输入触发区 |
| EY0~EY15 | M200~M215 | 输出结果区 |
| ED0~ED15 | D100~D115 | 输入数据区 |
| EW0~EW15 | D200~D215 | 输出数据区 |

---

## 信捷 PLC Modbus 通信设置

### XG 系列 PLC 设置

1. 打开 XD/XG Motion Pro 编程软件
2. 进入 **PLC 参数** → **通信设置**
3. 以太网端口设置：
   - IP 地址：192.168.1.10
   - 子网掩码：255.255.255.0
   - Modbus TCP 服务：**启用**
   - 端口：502

### 注意事项

- PLC 必须设为 **Modbus TCP Slave**（VModule 作为 Master 轮询）
- M/D/X/Y 等软元件默认对外开放读写，无需额外配置
- X/Y 地址使用**八进制**编号（X0~X7, X10~X17...）
- 确保 PC 和 PLC 在同一子网

---

## 时序说明

```
PLC 侧                          VModule 侧
─────────                        ──────────
SET M100 (触发)
       ──── Modbus 读取 ────►   EX0 = ON
                                 检测到上升沿
                                 拍照...
                                 AI推理...
                                 EY0 = ON (完成)
                                 EY1 = ON/OFF (OK/NG)
                                 EW0 = 缺陷数
       ◄──── Modbus 写入 ────
LD M200 (完成)
RST M100 (清除触发)
       ──── Modbus 读取 ────►   EX0 = OFF
                                 EY0 自动清除 (下周期)
```

**典型延迟**: 触发 → 结果 ≈ 50~200ms（取决于模型大小和相机曝光）

---

## 故障排查

| 现象 | 可能原因 | 解决方法 |
|------|---------|---------|
| API 无响应 | 服务未启动 | 运行 `start.bat` |
| PLC 连接失败 | IP/端口错误 | 检查网络，ping PLC |
| 触发无反应 | 映射未配置 | 检查 I/O 映射配置 |
| 触发无反应 | 边沿检测需要从 OFF→ON | 确保先 RST 再 SET |
| 结果一直 NG | 模型未加载 | 检查 weights 目录 |
| 扫描周期过长 | 映射点过多 | 减少映射或增大周期 |
| SM11=ON | 通信异常 | 检查 PLC 连接状态 |
