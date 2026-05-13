# Decisions Log

**本文档是 agent 与 owner 的异步沟通渠道。**

- Agent 遇到模糊需求或设计分叉，记一条 `STATUS: PENDING`，停下等答复。
- Owner 看完后改成 `STATUS: DECIDED` 并写下决定。
- 已决议的决策作为历史存档，**不删不改**。

**格式约定**

```
## D-NNNN [STATUS: PENDING|DECIDED|OBSOLETE]
**标题**

**背景**
...

**选项**
- A: ...
- B: ...
- C: ...

**倾向**: <agent 的推荐 + 理由>

**决议**（由 owner 填写）
...
```

---

## D-0001 [STATUS: DECIDED]
**本文档存在性**

Owner 已决策要用本文档作为异步沟通渠道（见 mission brief）。

---

## D-0002 [STATUS: DECIDED]
**术语：面向 PLC 工程师的中文表达**

**决议**：按 `01-ARCHITECTURE.md` 末尾"术语对照"表采纳。若发现更地道的叫法，追加到表里并在本 log 记一条 `DECIDED`。

---

<!-- 从此开始，Agent 按顺序追加新条目 -->
