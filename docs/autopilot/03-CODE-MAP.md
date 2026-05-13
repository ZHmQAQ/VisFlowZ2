# Code Map — 现有代码导航 + 改动热区

> 给新 agent：在动任何一行代码前，先把本文档涉及的文件**读完一遍**。本项目有精细的边界条件（触发沿、awaiting_reset、相机互斥），不读透就重构会炸。

## 仓库结构

```
VModule/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI 入口 + lifespan + 路由挂载
│   │   ├── config.py                  # Pydantic settings（HOST/PORT/DEBUG/路径）
│   │   ├── api/                       # HTTP 路由层（本文"API"列）
│   │   ├── core/                      # 业务核心（本文"CORE"列）
│   │   ├── db/                        # SQLAlchemy 模型 + Repository
│   │   └── utils/                     # 日志等工具
│   ├── MvImport/                      # 海康 MVS SDK（系统级 DLL 依赖）
│   ├── gxipy/                         # 大恒 Galaxy SDK（依赖 numpy<2）
│   ├── tests/                         # pytest
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── views/                     # Vue 页面
│   │   ├── stores/                    # Pinia
│   │   ├── api/                       # axios 封装
│   │   └── router/
│   └── package.json
├── presets/                           # 内置预设 JSON
├── scripts/                           # 打包 / preflight / 导入工具
├── docs/
│   └── autopilot/                     # ← 你在这里
└── visflowz-config-vmodule-2026-05-13.json  # 现场业务配置
```

## Backend 核心地图

### `app/core/scanner/engine.py` — ScanEngine

**作用**：心跳。每 N 毫秒扫一次，依次跑所有 `ProgramBlock.run()`。

**关键属性**
- `_memory: SoftDeviceMemory` — 共享虚拟寄存器
- `_programs: list[ProgramBlock]` — 注册的程序块
- `_config.target_cycle_ms` — 目标周期，默认 5ms

**重构相关**
- Phase 1：新 RuleEngine 作为一个"特殊 ProgramBlock"注入
- Phase 6：旧 DetectionProgramBlock / MultiFrameProgramBlock 从 `_programs` 列表撤掉

### `app/core/softdevice/memory.py` — SoftDeviceMemory

**作用**：虚拟寄存器实现。支持 X/Y/M/D/SM/SD/EW/ED 等地址格式。

**核心 API**
- `read_bit(addr)`, `write_bit(addr, bool)`
- `read_word(addr)`, `write_word(addr, int)`
- `read_dword(addr)`, `write_dword(addr, int)`

**重构相关**
- Phase 1：**新增**事件总线 / 监听器机制 → 寄存器变化时 emit 事件供 Trigger 订阅
- 不要改破坏现有读写语义

**地址解析**
- `SoftDeviceAddress.parse("M100")` → `SoftDeviceAddress(prefix='M', index=100)`
- 解析逻辑在 `address.py`，不要改

### `app/core/detection/program_block.py` — DetectionProgramBlock

**作用**：单相机检测块。每 tick 检查所有 channel 的触发信号，命中则 capture + infer + write_back。

**关键逻辑**
- 触发沿判断（`_prev_triggers` 记录上周期值）
- `_busy_cameras` 集合 — 相机互斥（同一相机同时只能处理一个检测任务）
- 结果码写回策略在 `_result_policy()` 中

**Phase 2 要做的事**
- `DetectionChannelTemplate.expand()` → 生成一条等价的 Rule
- 行为对齐：parity 测试必须绿

### `app/core/detection/multiframe.py` — MultiFrameProgramBlock

**作用**：多帧采集块。PLC 通过 `cmd_addr` 写入不同命令值（1/2/3/4），每个命令触发一次 capture。凑齐所有帧后延时 finalize。

**关键语义（极易踩雷）**
- `_last_cmd`: 记录上周期命令值。**等值不触发**（防抖）。
- `_awaiting_reset`: 出错或完成后进入此态，必须等 `cmd_val == 0` 观察到一次才解除。**启动时若 PLC 残留非零值会立刻触发**（今晚现场就是这个问题）。
- `_cycle_id`: 一个完整多帧周期的 ID，日志追踪用
- `_frames: dict[int, np.ndarray]` — 当前周期已采集的帧
- `finalize_delay_ms`: 凑齐后延时 finalize（给 PLC 留时间写回确认位）

**Phase 2 要做的事**
- `MultiframeChannelTemplate.expand()` → N 条 `register_equal` Trigger + 1 条 `all_frames_collected` Trigger
- 新增 Action：`store_frame`, `combine_frames`, `decide_final`, `reset_frames`
- awaiting_reset 语义**必须**在规则引擎中复现

### `app/core/rule.py` / `app/core/event_action.py`

**作用**：当前版的规则引擎和事件动作，挂在 ScanEngine 上作为"附加功能"。

**现状**
- `rule.py`：条件判断 + 执行动作，但 Trigger/Action 的抽象级别不够
- `event_action.py`：事件监听 → 动作分发，与 rule.py 功能重叠

**Phase 1 要做的事**
- **不删**，保留运行中。新引擎 `rules/` 包与旧两者并存
- Phase 6 再彻底撤下

### `app/core/persistence.py`

**作用**：配置持久化。把 scan engine + detection block + multiframe block 的状态序列化到 SQLite，启动时恢复。

**Phase 2 要做的事**
- 扩展 collector 支持 ChannelTemplate + Rule
- 保证**旧格式预设能加载**（向后兼容）

### `app/core/image_store.py`

**作用**：图像持久化。被 `save_image` Action 直接复用，不改。

### `app/core/camera/` + `app/core/inference/`

**作用**：相机管理器 / 推理管理器。规则引擎的 `capture` / `infer` Action 直接调用。不改。

### `app/core/device/`

**作用**：外部设备（Serial/TCP）。Phase 7 可能作为 Trigger 源或 Action 目标。

## Backend API 地图

| 文件 | 现状 | Phase 改动 |
|---|---|---|
| `api/plc.py` | PLC CRUD + 预设加载（含 `_do_load_preset`） | Phase 6：加载时走 ChannelTemplate 路径 |
| `api/camera.py` | 相机 CRUD + 拍照 + `store_frame` | Phase 2：`store_frame` 可能被 save_image Action 调用 |
| `api/detection.py` | DetectionChannel CRUD | Phase 6：逐步替换为 `api/channels.py` |
| `api/system.py` | 引擎启停、状态查询、健康检查 | Phase 3：增加"首次运行自检"接口 |
| `api/model.py` | 模型上传 + 绑定 | 不改 |
| `api/rule.py` | 旧规则 API | Phase 1 保留，Phase 6 废弃 |
| `api/event_action.py` | 旧事件动作 API | 同上 |
| `api/device.py` | 外部设备 CRUD | Phase 7 |
| `api/config.py` | 完整配置导入导出 | Phase 2：加入 Rules + ChannelTemplates |
| `api/gpu.py` | GPU 状态 | 不改 |

**新增**
- `api/rules_v2.py`（Phase 1）
- `api/channels.py`（Phase 2，新通道模板 API）

## Frontend 地图

| 页面 | 路径 | Phase 改动 |
|---|---|---|
| Dashboard.vue | `/dashboard` | Phase 3: 加"首次配置向导"入口；Phase 5: 加配置流程引导卡 |
| PLCConfig.vue | `/plc` | 不改 |
| IOMappings.vue | `/mappings` | 不改 |
| Detection.vue | `/detection` | Phase 6: 可选——改为 ChannelTemplates 视图 |
| Topology.vue | `/topology` | 不改 |
| Ladder.vue | `/ladder` | Phase 7 可选: 规则实时可视化 |
| DeviceMonitor.vue | `/monitor` | 不改 |
| Cameras.vue | `/cameras` | 不改 |
| Devices.vue | `/devices` | 不改 |
| EventActions.vue | `/event-actions` | Phase 6 废弃 |
| Rules.vue | `/rules` | Phase 4: 改造为 RulesEditor 或保留为"旧规则"页 |
| Models.vue | `/models` | 不改 |
| Records.vue | `/records` | 不改 |
| Settings.vue | `/settings` | 不改 |
| Layout.vue | 布局 | Phase 5: 菜单分组 |

**新增页面（全在 `views/wizard/` 下）**
- Wizard.vue
- steps/Step0Welcome.vue … Step7Done.vue
- components/DataFlowBadge.vue 等

**新增页面（Phase 4）**
- RulesEditor.vue（替代或扩展 Rules.vue）
- rules/components/TriggerEditor.vue
- rules/components/ActionEditor.vue

## 关键数据结构

### 现场业务配置（Phase 0/1/2 必须持续兼容）

`visflowz-config-vmodule-2026-05-13.json` 结构概要：

```json
{
  "plc_connections": [ { "id", "host", "port", ... } ],
  "io_mappings": [ { "id", "plc_addr", "soft_addr", "type", ... } ],
  "detection_channels": [ { "name", "camera_id", "model_id", "trigger_addr", "status_addr", ... } ],
  "multiframe_channels": [ { "name", "camera_id", "cmd_addr", "status_addr", "frames": [...], ... } ],
  "cameras": [ ... ],
  "models": [ ... ],
  "rules": [ ... ],             # 旧规则
  "event_actions": [ ... ]      # 旧事件
}
```

**Phase 2 扩展后**

```json
{
  ... 原有字段全保留 ...
  "channel_templates": [ ... ],   # 新
  "rules_v2": [ ... ]             # 新，区别于旧 rules
}
```

加载器行为：
- 旧字段有则走旧加载路径
- 新字段有则走新加载路径
- 两种路径**互不影响**（由 feature flag 控制哪个生效）

## SoftDevice 地址常用

| 前缀 | 含义 | 位/字 |
|---|---|---|
| X | 输入 | bit |
| Y | 输出 | bit |
| M | 内部辅助 | bit |
| D | 数据寄存器 | word |
| ED | 扩展双字 | dword |
| EW | 扩展字 | word |
| SM | 系统辅助 | bit |
| SD | 系统数据 | word |

## 性能基线（Phase 0 要测得实际数字）

| 指标 | 目标 |
|---|---|
| Scan engine 平均周期 | ≤ 50ms（正常负载） |
| 单次 capture 延时 | ≤ 200ms |
| 单次 infer 延时 | 依模型（huade.pt 约 50ms） |
| 500 条 rule 评估开销 | ≤ 10ms/tick |

## 别碰的东西

1. **`MvImport/` / `gxipy/`** — 厂商 SDK，二进制 + numpy<2 依赖
2. **`app/core/softdevice/memory.py` 的读写语义** — 只加监听器，不改读写
3. **`app/core/camera/` 内部** — 相机管理器内部，只走公开接口
4. **`ScanEngine` 的 tick 节拍** — 只能加 `ProgramBlock`，不改节拍机制
5. **现场业务配置** `visflowz-config-vmodule-2026-05-13.json` — 测试加载可用，但不要当测试夹具（会随现场变化）

## 可以放心重构的东西

1. `app/core/detection/program_block.py` — Phase 6 前只标 deprecated 不删
2. `app/core/detection/multiframe.py` — 同上
3. `app/core/rule.py` / `app/core/event_action.py` — 同上
4. `frontend/src/views/Rules.vue` / `EventActions.vue` — 同上

## 推荐阅读顺序

1. `backend/app/main.py` — 理解 lifespan 流程
2. `backend/app/core/scanner/engine.py` — 心跳
3. `backend/app/core/softdevice/memory.py` + `address.py` — 数据底座
4. `backend/app/core/detection/program_block.py` — 最简单 Block 作为参考
5. `backend/app/core/detection/multiframe.py` — 最复杂 Block（awaiting_reset 重点看）
6. `backend/app/core/persistence.py` — 持久化
7. `backend/app/api/plc.py::_do_load_preset` — 预设加载入口
8. `frontend/src/router/index.js` + `Layout.vue` + `Dashboard.vue` — 前端骨架
