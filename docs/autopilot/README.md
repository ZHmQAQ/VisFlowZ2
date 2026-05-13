# README — autopilot 文档套件

这是给"后台持续开发 agent"的完整交接文档。**按本文顺序阅读**。

## 阅读顺序

1. **[00-MISSION.md](./00-MISSION.md)** — 北极星目标、为什么做、成功标准、精神内核
2. **[01-ARCHITECTURE.md](./01-ARCHITECTURE.md)** — 事件驱动 + 虚拟寄存器双层架构设计
3. **[02-PHASE-ROADMAP.md](./02-PHASE-ROADMAP.md)** — 分 7 个 Phase 的实施路线图 + 验收标准
4. **[03-CODE-MAP.md](./03-CODE-MAP.md)** — 现有代码导航 + 改动热区 + 推荐阅读顺序
5. **[04-WORKING-RULES.md](./04-WORKING-RULES.md)** — Git 卫生 / 代码规范 / 测试 / 交互流程
6. **[05-DECISIONS-LOG.md](./05-DECISIONS-LOG.md)** — 与 owner 的异步沟通渠道（重要！）

## 首次上手动作

1. 把上面 6 份文档**全部读完**，不要跳。
2. 按 `03-CODE-MAP.md` "推荐阅读顺序" 把 8 个核心源文件读透。
3. 开始执行 `02-PHASE-ROADMAP.md` **Phase 0**（地基勘测 + 基线测试）。
4. Phase 0 完成后**停下来**，在 `05-DECISIONS-LOG.md` 写一个 checkpoint，等 owner 确认再进 Phase 1。

## 工作原则 TL;DR

- 小步快跑，每个 Phase 独立 PR，不贪多
- 遇模糊需求写 `05-DECISIONS-LOG.md` 停下问
- 现场能跑的代码（`feat/visflowz-launch-2026-05-13`）**不要动**
- 性能、兼容性、测试，缺一不可

## 分支约定

- 本 mission 根分支：`feat/rule-engine-wizard`
- 每个 Phase 子分支：`feat/rule-engine-wizard/phase-N-<slug>`
- 绝对不要 push 到 `main`

## 出问题找谁

- 代码疑问：先读代码，再写 `05-DECISIONS-LOG.md`
- 架构疑问：在 `05-DECISIONS-LOG.md` 立 entry 等答复
- 紧急 bug：记到日志，不自己兜底

## 文档维护

- Phase 完成后打勾 `02-PHASE-ROADMAP.md`
- 新 Trigger/Action 加到 `01-ARCHITECTURE.md` 表格
- 关键架构决策必须到 `05-DECISIONS-LOG.md`
- **不要**写空话型"进度汇报"
