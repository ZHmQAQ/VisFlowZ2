# 新 Agent 窗口入口 Prompt

**使用方法**：
1. 开一个全新的 agent 窗口（新 Claude Code 会话），工作目录 `D:\agentzone\VModule`
2. 先确认分支：`git checkout feat/rule-engine-wizard`
3. 把下面"完整 prompt"那一段复制粘贴回车即可

---

## 完整 prompt

```
你接手一个长期后台重构任务：把 VModule 从"相机管道"思维重构为"事件驱动 + 虚拟寄存器"架构，同时做一个用户友好的配置向导。

完整交接文档在 docs/autopilot/，必须按顺序读完再动手：

1. docs/autopilot/README.md              ← 先读这个
2. docs/autopilot/00-MISSION.md          北极星目标
3. docs/autopilot/01-ARCHITECTURE.md     双层架构设计
4. docs/autopilot/02-PHASE-ROADMAP.md    7 阶段路线图
5. docs/autopilot/03-CODE-MAP.md         现有代码导航
6. docs/autopilot/04-WORKING-RULES.md    工作准则（git/测试/边界）
7. docs/autopilot/05-DECISIONS-LOG.md    异步沟通渠道

读完 7 份文档后，按 03-CODE-MAP.md 末尾的"推荐阅读顺序"把 8 个核心源文件全部读透。然后开始执行 02-PHASE-ROADMAP.md 的 Phase 0（地基勘测 + 基线测试）。

硬约束（来自 04-WORKING-RULES.md）：
- 当前分支是 feat/rule-engine-wizard，绝对不要 push 到 main 或 feat/visflowz-launch-2026-05-13
- 每个 Phase 开子分支 feat/rule-engine-wizard/phase-N-<slug>，PR 目标是 feat/rule-engine-wizard
- git 代理是 http://127.0.0.1:17891（已配好）
- 遇模糊需求写 docs/autopilot/05-DECISIONS-LOG.md，标 STATUS: PENDING，停下等 owner 答复
- 方法连续失败两次就停下写日志，不要第三次尝试
- 不加新的第三方依赖（不加 Celery、Redis、Kafka 等）
- 绝对不要改 visflowz-config-vmodule-2026-05-13.json
- 绝对不要删 MvImport/ 和 gxipy/

Phase 0 完成后必须停下来，在 05-DECISIONS-LOG.md 写 checkpoint，等 owner 确认再进 Phase 1。

现在开始：先读 docs/autopilot/README.md。
```

---

## 首次启动后的推荐节奏

1. **第一轮**：只读文档 + 源码，不动代码，出一份"理解摘要"写到 `05-DECISIONS-LOG.md` 的 D-0003
2. **第二轮**：开 `feat/rule-engine-wizard/phase-0-baseline` 分支，写基线测试
3. **第三轮**：Phase 0 PR，等 owner 确认
4. **之后**：按路线图推进

## 与 owner 同步的方式

Agent 会在 `05-DECISIONS-LOG.md` 追加新条目。
Owner 定期（比如每天）扫一眼这个文件，对 `PENDING` 条目做决议。
Owner 确认某个 Phase 的 PR 后，agent 才能开下一个 Phase。
