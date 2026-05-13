# Architecture Vision — 事件驱动 + 虚拟寄存器双层架构

## 核心范式

**所有功能 = Trigger + Action + Rule 三原语**

```
Trigger（触发源）→ Rule（编排）→ Action（动作）
           ↑                        ↓
           └──── SoftDeviceMemory ──┘
              （虚拟寄存器 + 事件总线）
```

## 三原语定义

### Trigger — 触发源

**本质：一个条件谓词，挂在 ScanEngine 的每个扫描周期里检查。**

| 类型 | 例 | 实现 |
|---|---|---|
| 寄存器上升沿 | M100: 0→1 | 记录上周期值 + 本周期值对比 |
| 寄存器下降沿 | M100: 1→0 | 同上 |
| 数值匹配 | D200 == 5 | 读寄存器，等值判断 |
| 数值区间 | D200 > 100 | 读寄存器，阈值判断 |
| 定时器 | 每 100ms | ScanEngine tick 计数 |
| 设备事件 | camera.pos1.frame_ready | 事件总线订阅 |
| 外部消息 | TCP 设备收到特定字节 | Device 层 emit 事件 |
| 组合 | M100↑ AND D200 < 50 | 多个 Trigger 与/或 |

**Trigger 接口（伪代码）**

```python
class Trigger(Protocol):
    id: str
    async def should_fire(self, ctx: ScanContext) -> bool:
        """本扫描周期是否触发。"""
```

### Action — 动作

**本质：一个异步任务，接收上下文，产生副作用 + 可选返回值。**

| 类型 | 副作用 |
|---|---|
| capture(camera_id) | 相机抓一帧，返回 image_ref |
| infer(model_id, image_ref) | 模型推理，返回 result |
| write_register(addr, value) | 改虚拟寄存器 |
| send_tcp(device_id, payload) | 外部设备写入 |
| save_image(image_ref, tags) | 图像持久化 |
| emit_event(channel, data) | 投递到事件总线 |
| delay(ms) | 异步等待 |
| branch(cond, then, else) | 条件分支（元动作） |
| parallel([a, b, c]) | 并发元动作 |
| sequence([a, b, c]) | 顺序元动作 |

**Action 接口**

```python
class Action(Protocol):
    id: str
    async def execute(self, ctx: ExecutionContext) -> ActionResult:
        """执行，返回结果写入 ctx.bindings 供后续 Action 引用。"""
```

### Rule — 编排

**本质：一个 `(Trigger, Action)` 对，加若干元数据。**

```python
@dataclass
class Rule:
    id: str
    name: str
    enabled: bool
    priority: int            # 同周期内多条规则触发时的执行顺序
    trigger: Trigger
    action: Action           # 单个 Action 或 元动作 (sequence/parallel/branch)
    tags: list[str]          # 用于"这条规则属于哪个通道模板"
    template_id: str | None  # 若由高层模板生成，记录来源，便于反向编辑
    cooldown_ms: int         # 最小重触发间隔
```

## 双层架构：高层模板 + 底层规则

### Layer 2：高层抽象（UI 直接暴露）

面向**大多数 PLC 工程师**，保留"通道"类直觉抽象：

- **检测通道（Detection Channel）**：单触发 → 单相机 → 单模型 → 单结果回写
- **多帧通道（Multiframe Channel）**：命令字驱动的多帧采集 + 合成判定
- **定时采集（Timed Capture）**：定时拍图存盘
- **外部联动（External Action）**：寄存器变化 → 外部设备指令

每个**高层模板**在后端**展开为 1~N 条底层 Rule**，持久化时**既保存模板配置也保存展开的 rule**。

### Layer 1：底层引擎（规则引擎本身）

面向**高级用户**。包含：
- Trigger 注册表
- Action 注册表
- Rule 存储 + 启用/禁用
- Rule 执行器（在 ScanEngine 每个 tick 内串行评估所有 enabled rule）
- 事件总线（Action emit_event → Trigger 订阅）

## 数据流示例

### 单相机检测（等价现有 DetectionBlock）

**UI 配置**：通道 pos1，触发 M100↑，相机 cam0，模型 huade.pt，结果回写 D200

**后端展开为 Rule**：

```yaml
rule:
  id: channel_pos1_detect
  name: "pos1 检测"
  template_id: detection_channel_pos1
  trigger:
    type: register_rising_edge
    addr: M100
  action:
    type: sequence
    steps:
      - type: capture
        camera_id: cam0
        bind: img
      - type: infer
        model_id: huade.pt
        image: "$img"
        bind: result
      - type: write_register
        addr: D200
        value: "$result.code"
      - type: save_image
        image: "$img"
        tags: ["pos1", "$result.code"]
```

### 多帧累积（等价现有 MultiframeBlock）

**后端展开为多条 Rule**（每个命令一条 + 1 条 finalize）：

```yaml
- id: pos2_cmd1
  trigger: { type: register_equal, addr: ED60, value: 1 }
  action: { sequence: [ capture(cam_pos2, exp=3000), infer, store(pos2.frames[1]), write(EW61, 17) ] }

- id: pos2_cmd2
  trigger: { type: register_equal, addr: ED60, value: 2 }
  action: { sequence: [ capture(cam_pos2, exp=5000), infer, store(pos2.frames[2]), write(EW61, 18) ] }

# ... cmd3, cmd4

- id: pos2_finalize
  trigger: { type: all_frames_collected, channel: pos2 }
  action: { sequence: [ combine_frames, decide_final, write(EW61, final_code), reset_frames ] }
```

这样多帧的语义完全被规则覆盖，不需要单独的 MultiframeBlock。

### 用户自定义规则（现有架构做不到）

**"D300 > 100 时每 5 秒抓图"**

```yaml
rule:
  name: "高水位采样"
  trigger:
    type: and
    children:
      - { type: register_greater, addr: D300, value: 100 }
      - { type: timer, interval_ms: 5000 }
  action:
    sequence:
      - capture: cam0
        bind: img
      - save_image: "$img"
        tags: ["high_watermark_sample"]
```

## 与现有代码的关系

**保留**：
- `SoftDeviceMemory` — 作为规则引擎的共享状态。**需要扩展**：发布寄存器变化事件到事件总线。
- `ScanEngine` — 作为规则评估的心跳。**需要扩展**：每个 tick 里按 priority 顺序评估所有 rule。
- `IOMapping` — 桥接真实 PLC ↔ 虚拟寄存器，不变。
- `CameraManager` / `InferenceManager` — 被 `capture` / `infer` Action 调用，不变。

**重构**：
- `DetectionProgramBlock` → **删除**，替换为 `DetectionChannelTemplate`（展开为 Rule）。
- `MultiFrameProgramBlock` → **删除**，替换为 `MultiframeChannelTemplate`（展开为 N 条 Rule + 合成器）。
- `rule.py` / `event_action.py` → **合并**为新的 `rules/` 包（引擎 + Trigger/Action 注册表 + 执行器）。

**新增**：
- `backend/app/core/rules/` 包（引擎）
- `backend/app/core/rules/triggers/` 各类 Trigger 实现
- `backend/app/core/rules/actions/` 各类 Action 实现
- `backend/app/core/rules/templates/` 高层模板 → 规则展开器
- `backend/app/api/rules_v2.py` 新规则 API
- 向导页（frontend/src/views/wizard/）

## 持久化

**SQLite schema（新增）**

```sql
CREATE TABLE rules (
    id TEXT PRIMARY KEY,
    name TEXT,
    enabled INTEGER DEFAULT 1,
    priority INTEGER DEFAULT 100,
    trigger_json TEXT,  -- 序列化 Trigger 配置
    action_json TEXT,   -- 序列化 Action 配置
    tags TEXT,
    template_id TEXT,
    cooldown_ms INTEGER DEFAULT 0,
    updated_at INTEGER
);

CREATE TABLE channel_templates (
    id TEXT PRIMARY KEY,
    type TEXT,          -- detection | multiframe | timed_capture | external_action
    config_json TEXT,   -- 模板配置（UI 视角）
    rule_ids TEXT,      -- 展开后产生的 rule id 列表
    updated_at INTEGER
);
```

**现有表保留**，新旧并行至 Phase 4 迁移收尾。

## 性能考量

- Rule 评估在 ScanEngine 每个 tick 内串行做**谓词判断**（should_fire）。谓词必须**便宜**（纯内存读）。
- Action 执行**异步**，不阻塞扫描周期。用 `asyncio.create_task` 并发。
- 多帧场景：同一个 camera 的连续 capture 不应并发（相机互斥），引擎需要**每相机串行队列**。
- 规则数量：单实例 ≤ 500 条 rule 时要保证扫描周期 ≤ 50ms。

## 反向可编辑性（关键）

**用户从 UI 改通道配置 → 后端自动重生成规则，替换旧规则。**

为保证可逆：
1. 每个由模板展开的 Rule 都带 `template_id`。
2. 模板更新时，先**删除** `template_id` 匹配的旧 rule，再**插入**新 rule。
3. 用户若在规则编辑器**手动改**了某条 template 生成的 rule，后台打标 `decoupled=true`，不再被模板覆盖。
4. "展开为规则"动作 = 把 template 展开结果放到规则编辑器，所有 rule 标记 `decoupled=true`。

## 术语对照（对 PLC 工程师）

| 代码术语 | UI 术语 |
|---|
| trigger | 触发条件 |
| action | 执行动作 |
| rule | 自动化规则 |
| register_rising_edge | 信号上升沿 |
| register_equal | 数值匹配 |
| timer | 定时触发 |
| capture | 拍照 |
| infer | 推理判定 |
| write_register | 写入地址 |
| send_tcp | 发送到外部设备 |
| save_image | 保存图像 |
| channel template | 通道（检测通道/多帧通道） |
| decoupled rule | 自定义规则 |
