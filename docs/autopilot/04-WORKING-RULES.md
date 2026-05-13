# Working Rules — 给 agent 的操作准则

> 这是硬约束。违反会导致现场崩溃或代码被打回重做。

## 1. Git 卫生

### 分支
- 本 mission 的根分支是 **`feat/rule-engine-wizard`**
- 每个 Phase 开子分支：`feat/rule-engine-wizard/phase-0-baseline`、`…/phase-1-engine` …
- PR 目标分支：回到 `feat/rule-engine-wizard`
- **绝对不要直接 push 到 `main` 或 `feat/visflowz-launch-2026-05-13`**
- 遇到任何与现场部署相关的决策（"要不要 cherry-pick 修复"），**停下问**，不要自作主张

### Commit 粒度
- 一个 commit 一件事
- Commit 消息中文，按 `feat/fix/docs/chore/refactor/test` 前缀开头
- 示例：`feat(rules): 新增 register_rising_edge Trigger + 单测`
- 引用文档时写路径：`(见 docs/autopilot/02-PHASE-ROADMAP.md Phase 1)`

### 不做的事
- 不运行 `git push --force`、`git reset --hard`、`git clean -f`、`git branch -D`
- 不修改 `.gitignore` 除非明确需要（加新生成物时）
- 不合并 PR（主人决策的事）
- 不修改现场配置 `visflowz-config-vmodule-2026-05-13.json`
- 不修改 `main` / `feat/visflowz-launch-2026-05-13` 上的任何文件

### Git 代理
- 本机 HTTP 代理 `http://127.0.0.1:17891`
- 已经配好 `git config http.proxy` / `https.proxy`
- 若 push 失败，先确认代理端口没变

## 2. 代码规范

### Python
- Python 3.10+ 语法（`|` 联合类型、`match`、`dataclass` 等）
- 全异步：`async def` / `await`，不要混入同步阻塞（如 `time.sleep`，用 `asyncio.sleep`）
- 类型注解**齐全**：函数签名、dataclass 字段
- 用 `dataclass` 或 `pydantic.BaseModel` 明确数据结构，不用裸 dict
- 日志：`from app.utils.logger import logger` 或 `loguru.logger`
- 禁用 print

### Vue
- 全部 `<script setup>` + Composition API
- Element Plus 组件优先
- Pinia store 用 `defineStore` + Composition 风格
- `<style scoped>` 默认；全局样式进 `global.scss`
- TypeScript 非必须但鼓励（现有项目是 JS）

### 命名
- 模块/文件：`snake_case`
- 类：`PascalCase`
- 函数/变量：`snake_case`（Python）、`camelCase`（JS/Vue）
- Trigger/Action 类型字符串：`snake_case`（如 `"register_rising_edge"`）
- Rule id / Channel id：`snake_case` + 来源前缀（如 `channel_pos1_detect`）

### 目录
- 新代码**不要散落在 `core/` 根**。进合适的子包。
- 规则引擎新包：`app/core/rules/` 统一入口
- 新 API：`app/api/` 下加文件，`main.py` 里注册

## 3. 测试

### 必做
- **每个新 Trigger / Action / Template**：对应单测
- **每次重构核心逻辑**：先写基线测试覆盖旧行为（Phase 0 已写一部分）
- **Phase 1/2 的 parity 测试**：新旧引擎同配置同输入同结果
- 测试文件放 `backend/tests/`，保持现有目录结构

### 跑法
```bash
cd backend
python -m pytest tests/ -v
```

### 测试原则
- 单元测试：纯逻辑，不起 FastAPI
- 集成测试：起 app，用 TestClient，但用**假相机 + 假推理**替换硬件依赖
- 性能测试：基线对比形式，记录到 `BASELINE-METRICS.md`

## 4. 日志与可观测性

### 日志级别
- DEBUG：循环内部细节、每 tick 状态
- INFO：规则触发、action 完成、用户级事件
- WARNING：配置异常、超时、retry
- ERROR：无法恢复的错误

### 必须记录
- 每条 Rule 触发时：rule_id、trigger 详情、耗时
- 每个 Action 失败时：action_id、参数摘要、异常
- 引擎启停、加载/卸载规则

### 禁止
- 在每个 tick 里 INFO（会淹没日志）
- 把图像二进制写进日志

## 5. 交互流程

### 遇到模糊需求
**必须停下来，写到 `docs/autopilot/05-DECISIONS-LOG.md`**，标 `STATUS: PENDING`，等答复。

示例：
```markdown
## D-0003 [PENDING]
**Phase 2 多帧 awaiting_reset 语义**

现有 `MultiFrameProgramBlock` 中，awaiting_reset 的解除需要观察到 cmd_addr=0 一次。
展开到规则引擎时，这个状态是：
- 方案 A：新增 `MultiframeState` 共享状态对象
- 方案 B：每个 Frame Rule 内部各自维护（可能不一致）
- 方案 C：reset 作为独立 Rule，触发是 `register_equal(0)`

倾向 A。等 owner 确认。
```

### 完成一个 Phase
**PR 模板**：

```markdown
## Phase X — <标题>

### 交付
- [x] <要点>

### 验收
- [x] 现场预设加载正常
- [x] Phase 0 baseline 测试全绿
- [x] 新增测试 N 个 全绿
- [x] 性能基线无退化（周期 XXms → XXms）

### 风险
- <有 / 无>

### 关联文档
- 02-PHASE-ROADMAP.md Phase X
```

### 遇到 Bug 发现
在 `05-DECISIONS-LOG.md` 记录 + 新建 issue（若 GH 可用）。

## 6. 性能守则

- 任何改动前读 `docs/autopilot/BASELINE-METRICS.md`
- 每个 PR 合并前跑性能回归（比对基线）
- 退化超过 20% → 说明原因 + 写到 PR 描述

## 7. 安全守则

- 不记录任何用户凭证到日志
- 不在 commit message 里嵌 IP/端口（如果是内部测试 ok，但生产部署信息要避免）
- 不禁用 pre-commit hook

## 8. 文档守则

- 每个 Phase 结束后**更新** `02-PHASE-ROADMAP.md`（打勾）
- 重要架构决策**记录到** `05-DECISIONS-LOG.md`
- 新增 Trigger / Action 时**更新** `01-ARCHITECTURE.md` 的表格
- 禁止为了"文档齐全"而写空话

## 9. 边界：什么时候停下

**必须停下问 owner 的情况**

1. 需要引入新第三方依赖（加到 requirements.txt / package.json）
2. 需要破坏性修改 SoftDeviceMemory 读写语义
3. 性能回归无法收敛
4. 遇到现场配置兼容性问题
5. 某个 Phase 工作量超估算 2 倍
6. Phase 1/2 parity 测试有无法对齐的行为差异

**不需要停下的情况**

1. 在规划内的常规实现
2. 小的重构优化
3. 补充测试
4. 文档更新

## 10. 工具

### 依赖的外部工具
- `uvicorn` / `fastapi` — 已装
- `pytest` + `pytest-asyncio` — 已装
- `vite` — 已装
- `npm run build` — 生产构建

### 启动现场环境（本地冒烟）
```bash
# 后端
cd backend
.venv\Scripts\activate
python run.py

# 前端开发模式（可选）
cd frontend
npm run dev
```

### 跑测试
```bash
cd backend
python -m pytest tests/ -v --tb=short
```

### 冷启动现场预设
```bash
# 浏览器访问 http://localhost:8100
# 仪表盘 → 内置预设下拉选 "visflowz 海康检测" → 应用预设
# 或手动上传 visflowz-config-vmodule-2026-05-13.json
```

## 11. 工作节奏

### 推荐做法
- **小步快跑**：每完成一个可独立提交的单元就 commit
- **先红后绿**：先写失败的测试，再改代码让它绿
- **日清任务**：每天（或每次长会话结束前）把当前状态写到 `05-DECISIONS-LOG.md`
- **读再写**：在 `03-CODE-MAP.md` 的"推荐阅读顺序"里的文件**全部读完**再动 Phase 1

### 避免做法
- 一次巨型 commit
- 跳过测试直接改业务代码
- 为了"看起来进度快"而写假测试（只测 happy path）
- 用 emoji 装饰代码（本仓库规范不允许）

## 12. 失败模式

**如果方法连续失败两次：**
- 停下，在 `05-DECISIONS-LOG.md` 写下"我试了 A、B 都不行，怀疑根因是 X"
- 等 owner 确认后再继续，不要第三次尝试
- 禁止"换个名字再试一次"

**如果 PR 被驳回：**
- 读驳回意见
- 在 `05-DECISIONS-LOG.md` 记一条 "PR-NNN 被驳回原因 + 应对"
- 修完再发
