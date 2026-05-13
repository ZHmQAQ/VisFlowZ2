# Phase Roadmap — `feat/rule-engine-wizard`

**所有 Phase 的每一个 PR 必须独立可部署。主分支始终能启动、跑现场预设。**

---

## Phase 0 — 地基勘测 + 基线测试（0.5–1 天）

**目标**：把当前行为冻结成测试，重构不退化才能合并。

### 交付

- [ ] `backend/tests/baseline/test_detection_block_baseline.py`
  - 用 `SoftDeviceMemory` + 假的 `CameraManager` + 假的 `InferenceManager`
  - 覆盖：单次触发、触发沿判断、结果写回
- [ ] `backend/tests/baseline/test_multiframe_block_baseline.py`
  - 覆盖：命令值 → 帧采集、awaiting_reset、finalize 延时、错误状态码
- [ ] `backend/tests/baseline/test_ioMapping_baseline.py`
  - 覆盖：bit / word / dword 读写双向
- [ ] `backend/tests/baseline/test_engine_tick_baseline.py`
  - 覆盖：ScanEngine 周期性能基线（记录当前平均周期 ms，作为后续性能回归基准）
- [ ] `docs/autopilot/BASELINE-METRICS.md`
  - 记录本 Phase 测得的性能数字、覆盖率数字

### 验收
- `pytest backend/tests/baseline/` 全绿
- `uvicorn app.main:app` 能起，现场预设能加载
- 性能基线数字写入文档

### 禁止
- 本阶段**不**改业务代码。只写测试。

---

## Phase 1 — 规则引擎内核 + 最小可用 Trigger/Action 集（2–3 天）

**目标**：新内核与旧 Block 并存，通过 feature flag 切换。新内核实现最简 Trigger/Action，覆盖"单相机检测"场景。

### 交付

- [ ] `backend/app/core/rules/engine.py`
  - `RuleEngine` 类：注册/删除 rule、每 tick 评估、冷却时间、优先级排序
- [ ] `backend/app/core/rules/context.py`
  - `ScanContext`、`ExecutionContext`、`ActionResult`、变量绑定（`$var` 引用）
- [ ] `backend/app/core/rules/triggers/` 初版
  - `register_rising_edge.py`
  - `register_falling_edge.py`
  - `register_equal.py`
  - `register_compare.py`（>, >=, <, <=, ==, !=）
  - `timer.py`
  - `and_or_not.py`（组合）
- [ ] `backend/app/core/rules/actions/` 初版
  - `capture.py`
  - `infer.py`
  - `write_register.py`
  - `save_image.py`
  - `sequence.py` / `parallel.py` / `branch.py` / `delay.py`
- [ ] `backend/app/core/rules/registry.py`
  - 注册表模式，支持 `type: "register_rising_edge"` 字符串 → 类解析
- [ ] `backend/app/core/rules/serializer.py`
  - Trigger/Action/Rule ↔ dict/JSON 互转
- [ ] `backend/app/db/models.py` 新增 `RuleRecord` 表
- [ ] `backend/app/db/repo/rule_repo.py` CRUD
- [ ] `backend/app/api/rules_v2.py` 提供规则 CRUD REST API
- [ ] Feature flag：`settings.RULE_ENGINE_V2 = False`（默认关闭）
  - 若开启，ScanEngine 额外跑 RuleEngine；若关闭，只跑旧 Block
- [ ] 单元测试覆盖所有 Trigger 和 Action

### 验收
- Feature flag 关闭时，现场行为 100% 不变
- Feature flag 开启时，通过单元测试能用一条手写规则"M100↑ → capture → infer → write D200"跑通
- `pytest backend/tests/rules/` 全绿

### 设计要点
- Trigger 的 `should_fire` 必须**纯内存**，不能调网络/磁盘
- Action 的 `execute` 必须是 `async`，由执行器用 `asyncio.create_task` 调度
- 每个相机一个 `asyncio.Lock`，保证同一相机的 capture 串行

---

## Phase 2 — 高层模板 → 规则展开器（2–3 天）

**目标**：让"检测通道"和"多帧通道"能在新引擎下跑起来，通过 feature flag 切换。

### 交付

- [ ] `backend/app/core/rules/templates/base.py`
  - `ChannelTemplate` 抽象类：`expand() -> list[Rule]`
- [ ] `backend/app/core/rules/templates/detection_channel.py`
  - 单触发 + capture + infer + write_register + save_image，展开为 1 条 Rule
- [ ] `backend/app/core/rules/templates/multiframe_channel.py`
  - 按 frame_count 展开为 N+1 条 Rule（N 条帧采集 + 1 条 finalize）
  - 实现 `all_frames_collected` Trigger（新增）
  - 实现 `combine_frames` / `decide_final` / `reset_frames` Action（新增）
- [ ] `backend/app/core/rules/templates/registry.py`
  - 模板类型注册表
- [ ] `backend/app/db/models.py` 新增 `ChannelTemplateRecord` 表
- [ ] `backend/app/api/channels.py` 新的通道 CRUD API（模板视角）
  - POST/PUT 时自动展开为 rule 写入 RuleRecord
  - `decoupled=true` 的 rule 不覆盖
- [ ] `backend/tests/rules/test_detection_template_behavior_parity.py`
  - **关键测试**：同一配置下，新模板展开的 rule 行为与旧 DetectionBlock 一致
- [ ] `backend/tests/rules/test_multiframe_template_behavior_parity.py`
  - 同上，对 MultiframeBlock

### 验收
- Feature flag 开启 + 加载现场预设（展开成 rule 后跑），结果与 flag 关闭一致
- 两个 parity 测试全绿
- 性能不退化 > 20%（对照 Phase 0 基线）

---

## Phase 3 — 向导（Wizard）Phase A（2–3 天）

**目标**：新用户 15 分钟跑通 happy path。纯前端工作，不改后端（除了 Step 1 自检 API 若缺就补）。

### 交付

- [ ] `frontend/src/views/wizard/Wizard.vue` 容器 + `el-steps`
- [ ] `frontend/src/views/wizard/wizard-store.js` Pinia 草稿
- [ ] `frontend/src/views/wizard/components/DataFlowBadge.vue` 顶部数据流显示
- [ ] Step 0 欢迎 — 新建 / 从预设 / 导入 JSON
- [ ] Step 1 连接 PLC — 协议 + IP + 端口 + 测试连接按钮
- [ ] Step 2 配置触发信号 — 至少"自定义"一种（地址 + 名称）
- [ ] Step 3 连接相机 — 扫描 + 打开 + 试拍
- [ ] Step 4 选择模型 — 列表 + 绑定到相机 + 用刚拍的图试跑
- [ ] Step 5 组装通道 — 自动根据前面输入生成通道建议
- [ ] Step 6 测试运行 — 启动引擎 + 手动触发 + 实时结果
- [ ] Step 7 完成 — 保存预设 + 跳转仪表盘
- [ ] 路由 `/wizard` 独立 Layout（无侧边栏）
- [ ] Dashboard 加"首次配置向导"入口按钮
- [ ] 首次访问（检测到 PLC 未配 + 相机为 0）自动弹跳转提示（可关闭）

### 必须可后退
- 每一步都能点"上一步"，不丢已填数据
- 任何一步能"保存草稿并退出"，下次继续

### 验收
- **用户测试**：找一个没看过代码的人，给文档（或全靠向导），15 分钟内走通全部 7 步
- 从 `/wizard` 走完能在 Dashboard 看到数据链运行
- Wizard 的草稿状态持久化到 localStorage

---

## Phase 4 — 规则编辑器 UI（3–4 天）

**目标**：让高级用户可视化地编辑规则。

### 交付

- [ ] `frontend/src/views/RulesEditor.vue`
  - 规则列表（启用/禁用、优先级、标签筛选）
  - 右侧编辑面板：Trigger 下拉 + Action 树状编辑
- [ ] `frontend/src/views/rules/components/TriggerEditor.vue`
  - 根据 Trigger type 渲染对应表单
- [ ] `frontend/src/views/rules/components/ActionEditor.vue`
  - 递归渲染 sequence/parallel/branch，叶子节点是具体 Action
  - 支持"变量引用"选择器：`$img`、`$result`
- [ ] "从通道展开为规则" 按钮
  - 选一个 channel template → 展开 rule 列表进入编辑器 → 标记 decoupled
- [ ] "从规则折叠回通道" 按钮（若规则集符合某个模板的形状）
- [ ] 规则调试：手动触发一次 + 显示执行结果
- [ ] 规则模拟：输入假的寄存器值，看哪些 rule 会触发

### 验收
- 能用 UI 创建 "D300 > 100 时每 5 秒抓图" 规则并跑通
- 能用 UI 展开 pos2 多帧通道为 5 条 rule，改其中一条，保存后重新加载仍保留修改

---

## Phase 5 — 菜单重组 + 仪表盘引导卡（0.5–1 天）

**目标**：整体 UX 对齐"装配线"思维。

### 交付

- [ ] 菜单分组（运行监控 / 配置装配 / 高级）
- [ ] Dashboard 顶部"配置流程"引导卡（显示 5 步完成状态）
- [ ] Dashboard "打开向导"按钮
- [ ] 菜单项术语核对（对照 01-ARCHITECTURE 的术语表）

### 验收
- 14 项菜单变成 3 组清晰分组
- 仪表盘一眼看出"我的系统配到哪一步了"

---

## Phase 6 — 旧 Block 下线 + 数据迁移（1–2 天）

**目标**：把 DetectionBlock / MultiFrameBlock 从 ScanEngine 撤掉，全部走规则引擎。

### 交付

- [ ] Feature flag 默认改为 `RULE_ENGINE_V2 = True`
- [ ] 启动时检查：若存在旧的 DetectionChannel 记录但无对应 ChannelTemplate，自动迁移（"第一次升级"场景）
- [ ] 撤掉 `backend/app/core/detection/program_block.py` 对 ScanEngine 的注册
- [ ] 撤掉 `backend/app/core/detection/multiframe.py` 对 ScanEngine 的注册
- [ ] 保留旧代码文件（标 deprecated），1 个大版本后删除
- [ ] 迁移文档 `docs/MIGRATION-V2.md`

### 验收
- 升级一个存量部署（比如 `visflowz-config-vmodule-2026-05-13.json`），一键加载，行为完全一致
- 性能基线不退化

---

## Phase 7 — 可选高级功能（看时间）

**候选列表**（按价值排序）：

- [ ] PLC 参考代码面板（Step 2 侧边展开）
- [ ] 梯形图实时可视化（Step 6 + Ladder 页合并）
- [ ] 生成接线文档 PDF
- [ ] 项目（Project）概念：把预设升级为项目
- [ ] 外部设备规则集成：TCP/Serial Device 触发 Trigger / 执行 Action
- [ ] 连续 N 次 NG 告警（需要 `accumulator` Trigger）
- [ ] 规则配置 YAML 导入导出（除 JSON 外）

---

## 并发策略

- **每个 Phase 独立一个 PR**，PR 标题格式：`phase-N: <一句话>`
- **不强求时间节点**，优先正确性
- 遇到模糊需求 → 写到 `05-DECISIONS-LOG.md` 等答复，不要自作主张
- 每个 PR 合并前：
  - 本地跑通 Phase 0 的 baseline 测试（回归护栏）
  - `uvicorn app.main:app` 能启动
  - 加载现场预设 `visflowz-config-vmodule-2026-05-13.json` 验证
