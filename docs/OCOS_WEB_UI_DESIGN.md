# OCOS Web 交互前端设计（v1.0，2026-08-30）

> **定位**: 本地 Web UI，是"数字生命的对话窗口 + 观察面板"——不是通用 Web 应用。
> **原则**: 单文件静态页（零前端构建链）、复用既有 API 语义、localhost-only、与 CLI/REPL 同一数据源（共享 SQLite）。

---

## 一、交互模型

```
浏览器 (http://127.0.0.1:8900/ui)
   │  POST /ocos/converse  {message}        ← 对话（同步回复，走 ChatResponder）
   │  GET  /ocos/summary                    ← 侧栏状态轮询（5s）
   │  GET/POST /ocos/approvals[...]         ← 待批动作处理
   ▼
FastAPI (ocos-server)
   │  共享 ~/.ocos/ocos.db
   ├─ ChatResponder（LLM / 状态回复）
   ├─ PendingStore（待批）
   ├─ UserInbox（消息留痕，daemon 亦消费）
   └─ GoalStore / MemoryHub（上下文与状态）
```

两条对话路径的关系：
- **Web UI / `ocos-server` 直答**：`POST /ocos/converse` 同步调 ChatResponder——无需 daemon 在跑，秒回。
- **`ocos say --wait`**：写收件箱，由 `ocos run` daemon 消费并回写——消息会**同时进入感知管道**（USER_INPUT 事件 → 注意力 → 认知循环），agent 的行为轨迹里有这次对话。
- 两路共用同一 ChatResponder 与同一记忆上下文，回复口径一致。

## 二、界面设计（单页两栏）

```
┌─────────────────────────────────────┬──────────────────────┐
│  OCOS 数字生命                        │  状态侧栏（5s 轮询）   │
│  ─────────────────────────────────  │  ──────────────────  │
│  [对话流]                            │  ● 运行状态            │
│   user: 你好，最近有什么新记忆？        │    goals P/A 计数      │
│   ocos: （回复气泡，mock 标注灰色）     │    approvals 待批数    │
│   user: ...                         │    inbox 未读          │
│                                     │    episodes/beliefs   │
│                                     │  ──────────────────   │
│                                     │  待批动作卡片           │
│  [输入框]                 [发送 ⏎]    │   PEND-xx dag_create  │
│                                     │   [批准] [拒绝]        │
└─────────────────────────────────────┴──────────────────────┘
```

- 消息气泡：`mock: true` 的回复带浅灰底 + "状态回复（未配置 LLM）"角标——**诚实展示降级**。
- 待批卡片：点击批准/拒绝 → POST → 刷新。
- 无路由、无登录（localhost 假定单用户=主人）；后续多端（Telegram 等）走同一 API。

## 三、API 契约（新增）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/ocos/converse` | `{message}` → `{reply, provider, mock}`（同步，`asyncio.to_thread`） |
| GET | `/ocos/summary` | goals/approvals/inbox/memory 计数 JSON（侧栏数据源） |
| GET | `/ocos/approvals` | 待批列表 |
| POST | `/ocos/approvals/{id}/approve` \| `/deny` | 审批（人工=authority） |
| GET | `/ui` | 单文件聊天页（`interaction/api/static/index.html`） |

既有 `/ocos/chat`（OpenTale 写作意图路由）保持不动——写作域入口。

## 四、演进路线

| 阶段 | 内容 |
|---|---|
| v1（本次） | 单文件聊天页 + converse/summary/approvals API |
| v2 | SSE 流式回复；消息经收件箱喂 daemon（行为与对话同流）；trace 时间线视图 |
| v3 | 记忆/信念浏览页；goal 甘特图；Telegram 等外发通道复用同一 API |
