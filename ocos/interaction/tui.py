"""OCOS TUI — 复刻 Hermes Agent CLI 对话界面。

外观复刻（对齐 hermes-agent.nousresearch.com/docs → CLI 界面）:
  - 欢迎横幅: ⚕ 标识 + model / 终端 / 工作目录 / 工具 / 记忆 / daemon
  - 状态栏: ⚕ model │ used/max │ [████░░] N% │ cost │ ▶bg │ 时长
    上下文条颜色阈值: 绿 <50% / 黄 50-80 / 橙 80-95 / 红 ≥95
  - kawaii 思考动画（表情轮换 + 计时）
  - 工具信息流: ┊ 前缀 + 图标 + 耗时
  - 圆角面板: 后台任务结果 / 目标执行结果（outbox 回推）/ 会话恢复 recap
    （daemon 非结果类出站消息只进 /outbox 日志视图，不刷对话流）

能力复刻:
  - 斜杠命令 + Tab 自动补全（/help /status /tools /usage /title /sessions
    /resume /clear /save /busy /background /goal /approvals /approve /deny
    /self-improve /outbox /quit）
  - 多行输入: Alt+Enter / Ctrl+J / 反斜杠续行; Ctrl+G 外部编辑器
  - busy 模式: interrupt（默认，中断并接管）/ queue（排队）/ steer（纠偏注入）
  - Ctrl+C 中断（2 秒内双击强制退出）; Ctrl+D 退出
  - 会话持久化（SQLite ~/.ocos/tui_sessions.db）+ --continue/--resume
    + 恢复时 "Previous Conversation" recap + 退出恢复摘要
  - /background（/bg）后台任务 → 完成后圆角面板回推
  - 最终回复 Markdown 剥离（保留代码块与列表）
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from rich import box as rich_box
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import OptionList, RichLog, Static, TextArea
from textual.widgets.option_list import Option

API_BASE = os.getenv("OCOS_API_BASE", "http://localhost:8900")
SESSION_DB = Path.home() / ".ocos" / "tui_sessions.db"
MAX_CONTEXT_TOKENS = 128_000
CONVERSE_TIMEOUT = 300.0
API_TIMEOUT = 10.0

# ── kawaii 思考动画帧（Hermes 风格） ─────────────────────────────────
THINKING_FRAMES = [
    ("◜", "(｡•́︿•̀｡)", "pondering..."),
    ("◝", "(´･ᴗ･`)", "thinking..."),
    ("◞", "(⊙_⊙)", "contemplating..."),
    ("◟", "q(°ᴗ°)p", "scheming..."),
]
THINKING_DONE = "✧٩(ˊᗜˋ*)و✧"

TOOL_ICONS = {"terminal": "💻", "web": "🔍", "file": "📄", "approval": "⏳", "daemon": "🧠"}

# ── 斜杠命令注册表: name → (参数提示, 描述) ──────────────────────────
COMMANDS: dict[str, tuple[str, str]] = {
    "help": ("", "显示命令帮助"),
    "status": ("", "会话信息（模型/token/时长/轮次）"),
    "tools": ("", "列出认知引擎与真实能力"),
    "usage": ("", "上下文 token 估算分解"),
    "title": ("<name>", "为当前会话命名"),
    "sessions": ("", "列出最近会话"),
    "resume": ("<id|title>", "恢复指定会话"),
    "clear": ("", "清屏"),
    "save": ("[path]", "导出会话 JSON"),
    "busy": ("<interrupt|queue|steer|status>", "设置 agent 忙碌时输入行为"),
    "queue": ("<msg>", "排队一条消息（等当前轮完成后发送）"),
    "steer": ("<msg>", "标记纠偏消息（当前轮完成后注入）"),
    "background": ("<prompt>", "后台会话运行 prompt（/bg 简写）"),
    "goal": ("<msg>", "把一句话转为待执行目标"),
    "approvals": ("", "列出待批动作"),
    "approve": ("<n|id>", "批准待批动作"),
    "deny": ("<n|id>", "拒绝待批动作"),
    "self-improve": ("", "触发自省升级提案"),
    "outbox": ("", "最近的 daemon 出站消息"),
    "quit": ("", "退出（同 Ctrl+D）"),
}
ALIASES = {"bg": "background", "exit": "quit", "?": "help"}

BUSY_TIP = "(tip) agent 工作时输入的消息会中断当前运行 — /busy queue 可改为排队, /busy steer 纠偏"


def _strip_markdown(text: str) -> str:
    """剥离最终回复中的冗余 Markdown 包装；代码块与列表保留。"""
    parts = re.split(r"(```.*?(?:```|$))", text, flags=re.S)
    out: list[str] = []
    for part in parts:
        if part.startswith("```"):
            out.append(part)
            continue
        part = re.sub(r"^#{1,6}\s+", "", part, flags=re.M)  # 标题
        part = re.sub(r"\*\*(.+?)\*\*", r"\1", part, flags=re.S)  # 粗体
        part = re.sub(r"(?<![\w*])\*([^*\n]+?)\*(?![\w*])", r"\1", part)  # 斜体
        part = re.sub(r"(?<!`)`([^`\n]+?)`(?!`)", r"\1", part)  # 行内码保留内容
        out.append(part)
    return "".join(out)


def _fmt_tokens(n: int) -> str:
    return f"{n / 1000:.1f}K" if n >= 1000 else str(n)


def _fmt_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}h{m:02d}m"
    return f"{m}m" if m else f"{s}s"


class SessionStore:
    """TUI 会话持久化 — 对齐 Hermes: SQLite 存储 + resume 谱系。"""

    def __init__(self, db_path: Path = SESSION_DB) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, title TEXT DEFAULT '',
                created_at TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS messages (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT, role TEXT, kind TEXT DEFAULT 'text',
                content TEXT, ts TEXT);
            CREATE INDEX IF NOT EXISTS idx_msg_session ON messages(session_id);
            """
        )
        conn.commit()
        conn.close()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def create_session(self) -> str:
        sid = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        now = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        conn.execute("INSERT INTO sessions (id, created_at, updated_at) VALUES (?,?,?)",
                      (sid, now, now))
        conn.commit()
        conn.close()
        return sid

    def add_message(self, sid: str, role: str, content: str, kind: str = "text") -> None:
        now = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        conn.execute(
            "INSERT INTO messages (session_id, role, kind, content, ts) VALUES (?,?,?,?,?)",
            (sid, role, kind, content, now))
        conn.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, sid))
        conn.commit()
        conn.close()

    def rename(self, sid: str, title: str) -> None:
        conn = self._conn()
        conn.execute("UPDATE sessions SET title=? WHERE id=?", (title, sid))
        conn.commit()
        conn.close()

    def list_sessions(self, limit: int = 10) -> list[dict]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT s.id, s.title, s.updated_at, "
            "(SELECT COUNT(*) FROM messages m WHERE m.session_id=s.id) "
            "FROM sessions s ORDER BY s.updated_at DESC LIMIT ?", (limit,)).fetchall()
        conn.close()
        return [dict(id=r[0], title=r[1], updated_at=r[2], messages=r[3]) for r in rows]

    def latest_session(self) -> str | None:
        conn = self._conn()
        row = conn.execute("SELECT id FROM sessions ORDER BY updated_at DESC LIMIT 1").fetchone()
        conn.close()
        return row[0] if row else None

    def find(self, id_or_title: str) -> str | None:
        conn = self._conn()
        row = conn.execute("SELECT id FROM sessions WHERE id LIKE ? ORDER BY updated_at DESC",
                           (id_or_title + "%",)).fetchone()
        if row is None:
            row = conn.execute(
                "SELECT id FROM sessions WHERE title LIKE ? ORDER BY updated_at DESC",
                (f"%{id_or_title}%",)).fetchone()
        conn.close()
        return row[0] if row else None

    def get_messages(self, sid: str) -> list[dict]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT role, kind, content, ts FROM messages WHERE session_id=? "
            "ORDER BY seq", (sid,)).fetchall()
        conn.close()
        return [dict(role=r[0], kind=r[1], content=r[2], ts=r[3]) for r in rows]

    def count_messages(self, sid: str) -> dict[str, int]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT role, COUNT(*) FROM messages WHERE session_id=? GROUP BY role",
            (sid,)).fetchall()
        conn.close()
        return {r[0]: r[1] for r in rows}


class InputArea(TextArea):
    """❯ 输入区 — 多行编辑 + 斜杠补全 + 历史 + 粘贴预览。"""

    BINDINGS = [
        Binding("enter", "submit", "发送", priority=True),
        Binding("ctrl+j,alt+enter", "newline_or_submit", "换行", priority=True),
        Binding("tab", "complete", "补全", priority=True),
        Binding("shift+tab", "complete_cycle", "轮换补全", priority=True),
        Binding("up", "smart_up", "历史/上移", priority=True),
        Binding("down", "smart_down", "历史/下移", priority=True),
    ]

    def __init__(self) -> None:
        super().__init__(id="input", soft_wrap=True, show_line_numbers=False)
        self._history: list[str] = []
        self._history_idx: int | None = None
        self._draft = ""
        self._paste_slots: dict[str, str] = {}
        self._paste_count = 0

    # ── 提交 / 换行 ─────────────────────────────────────────────────
    def action_submit(self) -> None:
        text = self._expand_pastes(self.text)
        if text.endswith("\\"):  # 反斜杠续行
            self.text = text[:-1] + "\n"
            self.move_cursor(self.document.end)
            return
        if not text.strip():
            return
        self._push_history(text)
        self.text = ""
        self._paste_slots.clear()
        self._paste_count = 0
        self._history_idx = None
        self.app.submit_prompt(text)

    def action_newline_or_submit(self) -> None:
        self.insert("\n")
        self.move_cursor(self.document.end)

    # ── 补全 ────────────────────────────────────────────────────────
    def action_complete(self) -> None:
        self.app.accept_completion()

    def action_complete_cycle(self) -> None:
        self.app.cycle_completion()

    def action_smart_up(self) -> None:
        if self.app.completion_open:
            self.app.move_completion(-1)
        elif self.cursor_location[0] > 0:
            self.action_cursor_up()
        else:
            self._recall_history(-1)

    def action_smart_down(self) -> None:
        if self.app.completion_open:
            self.app.move_completion(1)
        elif self.cursor_location[0] < self.document.line_count - 1:
            self.action_cursor_down()
        else:
            self._recall_history(1)

    def _recall_history(self, delta: int) -> None:
        if not self._history:
            return
        if self._history_idx is None:
            if delta < 0:
                self._draft = self.text
                self._history_idx = len(self._history) - 1
            else:
                return
        else:
            self._history_idx += delta
            if self._history_idx >= len(self._history):
                self._history_idx = None
                self.text = self._draft
                self.move_cursor(self.document.end)
                return
            if self._history_idx < 0:
                self._history_idx = 0
        self.text = self._history[self._history_idx]
        self.move_cursor(self.document.end)

    def _push_history(self, text: str) -> None:
        if not self._history or self._history[-1] != text:
            self._history.append(text)
            self._history = self._history[-100:]

    # ── 多行粘贴预览（Hermes: [pasted: N lines, M chars]） ──────────
    async def _on_paste(self, event) -> None:  # noqa: ANN001 — textual events.Paste
        text = getattr(event, "text", "")
        if text.count("\n") >= 3:
            self._paste_count += 1
            slot = f"[pasted #{self._paste_count}: {text.count(chr(10)) + 1} lines, {len(text)} chars]"
            self._paste_slots[slot] = text
            event.stop()
            event.prevent_default()
            self.insert(slot)
            return
        await super()._on_paste(event)

    def _expand_pastes(self, text: str) -> str:
        for slot, real in self._paste_slots.items():
            text = text.replace(slot, real)
        return text


class ChatScreen(App):
    """⚕ OCOS — Hermes Agent CLI 风格对话界面。"""

    CSS = """
    Screen { background: #101216; }
    #chat { height: 1fr; padding: 0 1; background: #101216; }
    #thinking { display: none; height: 1; padding: 0 1; color: yellow; background: #101216; }
    #complete {
        display: none; height: auto; max-height: 12;
        background: #16191f; border-top: solid #2a2f3a;
        color: #c8ccd4; scrollbar-size: 0 0;
    }
    #status { height: 1; background: #16191f; color: #8a919c; padding: 0 1; }
    #input-row { height: auto; min-height: 1; background: #101216; padding: 0 1; }
    #prompt { width: 2; color: #56b6c2; text-style: bold; padding-top: 0; }
    #input {
        background: #101216; color: #e6e6e6; border: none; padding: 0;
        height: auto; min-height: 1; max-height: 12;
    }
    #input > .text-area--cursor-line { background: #1b1f27; }
    #hint { height: 1; background: #16191f; color: #565e6b; padding: 0 1; }
    """
    BINDINGS = [
        Binding("ctrl+c", "interrupt", "中断", priority=True),
        Binding("ctrl+d", "quit", "退出", priority=True),
        Binding("ctrl+g", "editor", "外部编辑器", priority=True),
        Binding("ctrl+l", "clear", "清屏", priority=True),
    ]

    def __init__(self, resume: str | None = None, api_base: str = API_BASE) -> None:
        super().__init__()
        self.api_base = api_base
        self.store = SessionStore()
        self.session_id = ""
        self.resume_target = resume  # "continue" | session id | None
        self.messages: list[dict] = []
        self.busy_mode = "interrupt"
        self.busy_tip_shown = False
        self.turn_queue: list[tuple[str, str]] = []  # (kind, text) kind∈msg|steer
        self.background_tasks: list[asyncio.Task] = []
        self.background_done = 0
        self.turn_active = False
        self._turn_task: asyncio.Task | None = None
        self._turn_started = 0.0
        self._spinner_idx = 0
        self._session_start = time.time()
        self._outbox_cursor = 0
        self._recent_outbox: list[dict] = []
        self._approval_hinted = False
        self._pending_approvals: list[dict] = []
        # 状态缓存（introspect/summary）
        self.provider = ""
        self.llm_configured: bool | None = None
        self.memory_counts: dict[str, int] = {}
        self.capabilities = ""
        self.engines = ""
        self.daemon_alive = False
        self.daemon_cycle = 0
        self.turn_tokens = 0

    # ── 布局 ────────────────────────────────────────────────────────
    def compose(self) -> ComposeResult:
        yield RichLog(id="chat", wrap=True, markup=False, highlight=False, min_width=60)
        yield Static("", id="thinking")
        yield OptionList(id="complete")
        yield Static("", id="status")
        with Static("", id="input-row"):
            yield Static("❯", id="prompt")
            yield InputArea()
        yield Static("msg=interrupt · /queue · /bg · /steer · Ctrl+C 中断 · Ctrl+D 退出", id="hint")

    @property
    def chat_log(self) -> RichLog:
        return self.query_one("#chat", RichLog)

    @property
    def input_area(self) -> InputArea:
        return self.query_one("#input", InputArea)

    @property
    def complete_list(self) -> OptionList:
        return self.query_one("#complete", OptionList)

    @property
    def completion_open(self) -> bool:
        return self.complete_list.display

    # ── 启动 ────────────────────────────────────────────────────────
    async def on_mount(self) -> None:
        await self._refresh_state()
        self._render_banner()
        # 会话解析：resume 目标优先，失败/无目标则新建
        sid = None
        if self.resume_target:
            sid = (self.store.latest_session() if self.resume_target == "continue"
                   else self.store.find(self.resume_target))
            if not sid:
                self._sys_line(f"[dim]未找到会话: {escape(str(self.resume_target))} — 新建会话[/dim]")
        self.session_id = sid or self.store.create_session()
        if sid:
            msgs = self.store.get_messages(sid)
            self.messages = list(msgs)
            self._render_recap(msgs)
        self.set_interval(0.12, self._tick_spinner)
        self.set_interval(10.0, self._refresh_state)
        self.set_interval(5.0, self._poll_outbox)
        self.set_interval(3.0, self._update_status)
        self.input_area.focus()
        self._update_status()

    async def _refresh_state(self) -> None:
        try:
            async with httpx.AsyncClient(base_url=self.api_base, timeout=API_TIMEOUT,
                                         trust_env=False) as client:
                resp = await client.get("/ocos/introspect")
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    self.memory_counts = data.get("memory_stats") or {}
                    self.capabilities = str(data.get("capabilities", ""))
                    self.engines = str(data.get("engines", ""))
                    llm = str(data.get("llm", ""))
                    self.llm_configured = "configured=True" in llm
                resp = await client.get("/ocos/summary")
                if resp.status_code == 200:
                    d = resp.json().get("data", {})
                    daemon = d.get("daemon", {})
                    self.daemon_alive = daemon.get("alive", False)
                    self.daemon_cycle = daemon.get("cycle", 0)
        except Exception:
            pass
        self._update_status()

    # ── 渲染原语 ────────────────────────────────────────────────────
    def _render_banner(self) -> None:
        model = self.provider or ("openai-compatible" if self.llm_configured else "mock/state-reply")
        term = os.getenv("TERM", "xterm-256color")
        tools = "fs 读写 ✓ · shell·HTTP 需审批"
        caps = self.capabilities.replace("能力: ", "").strip()
        if caps and "不可用" not in caps:
            tools = caps
        mem = self.memory_counts
        mem_str = (f"episodes={mem.get('episode_count', 0)} "
                   f"beliefs={mem.get('belief_count', 0)} "
                   f"patterns={mem.get('pattern_count', 0)}")
        daemon = f"在线 (cycle {self.daemon_cycle})" if self.daemon_alive else "离线"
        lines = [
            "",
            Text(" ⚕ OCOS — 数字生命体 (digital organism)", style="bold cyan"),
            Text(f" model      {model}", style="dim"),
            Text(f" terminal   {term} │ python {sys.version.split()[0]}", style="dim"),
            Text(f" cwd        {os.getcwd()}", style="dim"),
            Text(f" tools      {tools}", style="dim"),
            Text(f" engines    {self.engines or '—'}", style="dim"),
            Text(f" memory     {mem_str}", style="dim"),
            Text(f" daemon     {daemon}", style="dim"),
            Text(" ────────────────────────────────────────────", style="dim"),
            Text(" /help 查看命令 · Ctrl+C 中断 · Ctrl+D 退出", style="dim italic"),
            "",
        ]
        for line in lines:
            self.chat_log.write(line)

    def _render_recap(self, msgs: list[dict]) -> None:
        """会话恢复 — Previous Conversation 面板。"""
        body = Text()
        recent = msgs[-8:]
        if not recent:
            body.append("（空会话）", style="dim")
        for m in recent:
            if m["kind"] == "paste" or not str(m["content"]).strip():
                continue
            who = "❯ 你" if m["role"] == "user" else "⚕ OCOS"
            style = "cyan" if m["role"] == "user" else "default"
            body.append(f"{who}: ", style=style)
            body.append(f"{str(m['content'])[:100]}\n", style="dim")
        self.chat_log.write(Panel(body, title="⚕ Previous Conversation",
                                  title_align="left", border_style="dim",
                                  box=rich_box.ROUNDED, padding=(0, 1)))
        self._sys_line(f"[dim]已恢复会话 {self.session_id}（{len(msgs)} 条消息）[/dim]")

    def _sys_line(self, markup: str) -> None:
        self.chat_log.write(Text.from_markup(markup))

    def _user_line(self, text: str) -> None:
        line = Text()
        line.append("❯ ", style="bold cyan")
        line.append(text)
        self.chat_log.write(line)

    def _bot_line(self, text: str) -> None:
        self.chat_log.write(_strip_markdown(text))
        self.chat_log.write(Text(""))

    def _tool_line(self, icon: str, name: str, detail: str, elapsed: float | None = None) -> None:
        line = Text()
        line.append(" ┊ ", style="dim")
        line.append(f"{icon} {name}", style="magenta")
        if detail:
            line.append(f" `{detail}`", style="dim")
        if elapsed is not None:
            line.append(f" ({elapsed:.1f}s)", style="dim")
        self.chat_log.write(line)

    def _panel(self, body: str, title: str, border: str = "dim") -> None:
        self.chat_log.write(Panel(Text(body), title=f"⚕ {title}", title_align="left",
                                  border_style=border, box=rich_box.ROUNDED, padding=(0, 1)))

    # ── 思考动画 ────────────────────────────────────────────────────
    def _start_spinner(self) -> None:
        self._turn_started = time.time()
        self._spinner_idx = 0
        w = self.query_one("#thinking", Static)
        w.display = True
        self._tick_spinner()

    def _tick_spinner(self) -> None:
        if not self.turn_active:
            return
        spin, face, word = THINKING_FRAMES[self._spinner_idx % len(THINKING_FRAMES)]
        self._spinner_idx += 1
        elapsed = time.time() - self._turn_started
        self.query_one("#thinking", Static).update(
            Text(f" {spin} {face} {word} ({elapsed:.1f}s)", style="yellow"))

    def _stop_spinner(self, ok: bool = True) -> None:
        elapsed = time.time() - self._turn_started
        self.query_one("#thinking", Static).display = False
        face = THINKING_DONE if ok else "(╥_╥)"
        line = Text(f" {face} {'got it!' if ok else 'aborted'} ({elapsed:.1f}s)",
                    style="green" if ok else "red")
        self.chat_log.write(line)

    # ── 状态栏（自适应宽度 + 颜色阈值） ─────────────────────────────
    def _update_status(self) -> None:
        width = self.size.width
        model = (self.provider or
                 ("openai-compatible" if self.llm_configured else
                  ("mock" if self.llm_configured is False else "...")))
        used = self.turn_tokens + sum(len(str(m["content"])) for m in self.messages) // 4
        used = min(used, MAX_CONTEXT_TOKENS)
        pct = used / MAX_CONTEXT_TOKENS
        color = ("green" if pct < 0.5 else "yellow" if pct < 0.8
                 else "orange3" if pct < 0.95 else "red")
        bar_n = 10
        filled = int(pct * bar_n)
        bar = Text(f"[{'█' * filled}{'░' * (bar_n - filled)}] {pct:.0%}", style=color)
        dur = _fmt_duration(time.time() - self._session_start)
        bg = len([t for t in self.background_tasks if not t.done()])

        status = Text(" ⚕ ")
        status.append(model, style="bold cyan")
        if width >= 76:
            status.append(f" │ {_fmt_tokens(used)}/{_fmt_tokens(MAX_CONTEXT_TOKENS)} │ ", style="dim")
            status.append(bar)
            status.append(f" │ n/a │ {dur}", style="dim")
            if bg:
                status.append(f" │ ▶{bg}", style="magenta")
            if not self.daemon_alive:
                status.append(" │ ⚠ daemon 离线", style="yellow")
        elif width >= 52:
            status.append(f" │ {_fmt_tokens(used)} │ ", style="dim")
            status.append(bar)
            status.append(f" │ {dur}", style="dim")
        else:
            status.append(f" │ {dur}", style="dim")
        self.query_one("#status", Static).update(status)

    # ── 输入提交入口 ────────────────────────────────────────────────
    def submit_prompt(self, text: str) -> None:
        if text.lstrip().startswith("/"):
            self._dispatch_command(text.strip())
            return
        self._route_user_message(text, kind="msg")

    def _route_user_message(self, text: str, kind: str = "msg") -> None:
        """busy 模式路由 — interrupt/queue/steer（对齐 Hermes）。"""
        if self.turn_active:
            if self.busy_mode == "interrupt":
                self._cancel_turn()
                self._user_line(text)
                self.store.add_message(self.session_id, "user", text)
                self._send(text)
            else:
                self.turn_queue.append((kind, text))
                label = "排队" if kind != "steer" else "纠偏注入"
                self._sys_line(f"[dim]({label}) {escape(text[:60])}[/dim]")
                if not self.busy_tip_shown:
                    self.busy_tip_shown = True
                    self._sys_line(f"[dim italic]{BUSY_TIP}[/dim italic]")
        else:
            self._user_line(text)
            self.store.add_message(self.session_id, "user", text)
            self._send(text)

    def _cancel_turn(self) -> None:
        if self._turn_task and not self._turn_task.done():
            self._turn_task.cancel()
        self.turn_active = False
        self._stop_spinner(ok=False)
        self._sys_line("[dim]⏸ 已中断当前运行[/dim]")

    # ── 主对话轮 ────────────────────────────────────────────────────
    def _send(self, message: str) -> None:
        self.turn_active = True
        self._approval_hinted = False
        self._start_spinner()
        self._turn_task = asyncio.create_task(self._do_turn(message))
        self._update_status()

    async def _do_turn(self, message: str) -> None:
        try:
            async with httpx.AsyncClient(base_url=self.api_base, timeout=CONVERSE_TIMEOUT,
                                         trust_env=False) as client:
                # FIX-8: 携带会话 id → 服务端据此把对话写入同 session_id 的记忆
                resp = await client.post(
                    "/ocos/converse",
                    json={"message": message, "session_id": self.session_id})
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}")
            data = resp.json().get("data", {})
            reply = data.get("reply", "（无回复）")
            self.provider = data.get("provider") or self.provider
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.turn_active = False
            self._stop_spinner(ok=False)
            self._sys_line(f"[red]连接失败（ocos-server 在跑吗？）{escape(str(e)[:120])}[/red]")
            self._drain_queue()
            return

        self.turn_active = False
        self._stop_spinner(ok=True)
        self._bot_line(reply)
        self.messages.append({"role": "assistant", "kind": "text", "content": reply})
        self.store.add_message(self.session_id, "assistant", reply)
        self.turn_tokens += (len(message) + len(reply)) // 4
        self._update_status()
        self._drain_queue()

    def _drain_queue(self) -> None:
        if not self.turn_queue:
            return
        kind, text = self.turn_queue.pop(0)
        if kind == "steer":
            self._sys_line("[dim]┊ steer 注入[/dim]")
        self._user_line(text)
        self.store.add_message(self.session_id, "user", text)
        self._send(text)

    # ── outbox 轮询（工具信息流 / daemon 面板） ─────────────────────
    async def _poll_outbox(self) -> None:
        try:
            async with httpx.AsyncClient(base_url=self.api_base, timeout=API_TIMEOUT,
                                         trust_env=False) as client:
                resp = await client.get(f"/ocos/outbox?after={self._outbox_cursor}")
                if resp.status_code != 200:
                    return
                data = resp.json().get("data", {})
                rows = data.get("messages", [])
                approvals = await client.get("/ocos/approvals")
                if approvals.status_code == 200:
                    self._pending_approvals = approvals.json().get("data", {}).get("pending", [])
        except Exception:
            return
        for row in rows:
            self._outbox_cursor = max(self._outbox_cursor, row.get("rid", 0))
            content = str(row.get("content", "")).strip()
            if not content:
                continue
            self._recent_outbox.append(row)
            self._recent_outbox = self._recent_outbox[-20:]
            # UX-J: 目标执行结果（sender=ocos）→ 对话流圆角面板回推，
            # 承接 converse 里"完成后呈现结果"的承诺；其余留 /outbox 查看
            self._panel(_strip_markdown(content), "目标执行结果", border="cyan")
        if self.turn_active and self._pending_approvals and not self._approval_hinted:
            # 待批动作需要用户操作 — 每轮只提示一次，细节在 /approvals
            self._approval_hinted = True
            self._sys_line(f"[dim]⏳ {len(self._pending_approvals)} 条待批动作 — "
                           f"/approvals 查看 · /approve <n> 批准[/dim]")
        self._update_status()

    # ── 斜杠命令 ────────────────────────────────────────────────────
    def _dispatch_command(self, raw: str) -> None:
        parts = raw[1:].split(None, 1)
        name = (parts[0] if parts else "").lower()
        arg = parts[1].strip() if len(parts) > 1 else ""
        name = ALIASES.get(name, ALIASES.get(name.upper(), name))
        handler = {
            "help": self._cmd_help, "status": self._cmd_status,
            "tools": self._cmd_tools, "usage": self._cmd_usage,
            "title": self._cmd_title, "sessions": self._cmd_sessions,
            "resume": self._cmd_resume, "clear": self.action_clear,
            "save": self._cmd_save, "busy": self._cmd_busy,
            "queue": self._cmd_queue, "steer": self._cmd_steer,
            "background": self._cmd_background, "goal": self._cmd_goal,
            "approvals": self._cmd_approvals, "approve": self._cmd_approve,
            "deny": self._cmd_deny, "self-improve": self._cmd_self_improve,
            "outbox": self._cmd_outbox, "quit": self.action_quit,
        }.get(name)
        if handler is None:
            self._sys_line(f"[red]未知命令: /{escape(name)} — /help 查看命令[/red]")
            return
        result = handler(arg)
        if asyncio.iscoroutine(result):
            asyncio.create_task(result)

    def _cmd_help(self, arg: str) -> None:
        body = Text()
        for name, (args, desc) in COMMANDS.items():
            body.append(f" /{name}", style="cyan")
            if args:
                body.append(f" {args}", style="dim italic")
            body.append(f"  {desc}\n")
        body.append("\n 快捷键: ", style="dim")
        body.append("Alt+Enter/Ctrl+J 换行 · Ctrl+G 编辑器 · Ctrl+C 中断(双击退出) · Ctrl+D 退出 · Tab 补全\n",
                    style="dim")
        body.append(" 鼠标: 默认终端原生选区，直接选中复制、右键粘贴；--mouse 切换为程序内鼠标",
                    style="dim")
        self.chat_log.write(Panel(body, title="⚕ 命令", title_align="left",
                                  border_style="dim", box=rich_box.ROUNDED, padding=(0, 1)))

    def _cmd_status(self, arg: str) -> None:
        counts = self.store.count_messages(self.session_id)
        used = self.turn_tokens + sum(len(str(m["content"])) for m in self.messages) // 4
        body = Text()
        body.append(f" session    {self.session_id}\n", style="dim")
        body.append(f" model      {self.provider or '—'}\n", style="dim")
        body.append(f" tokens     ~{_fmt_tokens(used)}/{_fmt_tokens(MAX_CONTEXT_TOKENS)}\n", style="dim")
        body.append(f" duration   {_fmt_duration(time.time() - self._session_start)}\n", style="dim")
        body.append(f" turns      {counts.get('user', 0)} user / "
                    f"{counts.get('assistant', 0)} assistant\n", style="dim")
        body.append(f" busy       {self.busy_mode}\n", style="dim")
        body.append(f" memory     {self.memory_counts}\n", style="dim")
        body.append(f" daemon     {'在线' if self.daemon_alive else '离线'}", style="dim")
        self._panel_from_text(body, "status")

    def _panel_from_text(self, body: Text, title: str) -> None:
        self.chat_log.write(Panel(body, title=f"⚕ {title}", title_align="left",
                                  border_style="dim", box=rich_box.ROUNDED, padding=(0, 1)))

    def _cmd_tools(self, arg: str) -> None:
        body = Text()
        body.append(f" engines  {self.engines or '—'}\n")
        body.append(f" caps     {self.capabilities or '—'}")
        self._panel_from_text(body, "tools")

    def _cmd_usage(self, arg: str) -> None:
        user_chars = sum(len(str(m["content"])) for m in self.messages if m["role"] == "user")
        bot_chars = sum(len(str(m["content"])) for m in self.messages if m["role"] == "assistant")
        body = Text()
        body.append(f" 输入 ~{_fmt_tokens(user_chars // 4)} · "
                    f"输出 ~{_fmt_tokens(bot_chars // 4)} · "
                    f"合计 ~{_fmt_tokens((user_chars + bot_chars) // 4)}"
                    f"/{_fmt_tokens(MAX_CONTEXT_TOKENS)}\n", style="dim")
        body.append(" 费用 n/a（后端未上报用量）", style="dim")
        self._panel_from_text(body, "usage")

    def _cmd_title(self, arg: str) -> None:
        if not arg:
            self._sys_line("[dim]用法: /title <name>[/dim]")
            return
        self.store.rename(self.session_id, arg)
        self._sys_line(f"[dim]会话已命名: {escape(arg)}[/dim]")

    def _cmd_sessions(self, arg: str) -> None:
        rows = self.store.list_sessions()
        body = Text()
        if not rows:
            body.append("（无历史会话）", style="dim")
        for r in rows:
            mark = "▸" if r["id"] == self.session_id else " "
            title = r["title"] or "（未命名）"
            body.append(f" {mark} {r['id']}  {title}  "
                        f"({r['messages']} msgs, {r['updated_at'][:16]})\n", style="dim")
        self._panel_from_text(body, "sessions")

    def _cmd_resume(self, arg: str) -> None:
        if not arg:
            self._sys_line("[dim]用法: /resume <id|title>（/sessions 查看）[/dim]")
            return
        sid = self.store.find(arg)
        if not sid:
            self._sys_line(f"[red]未找到会话: {escape(arg)}[/red]")
            return
        self.session_id = sid
        msgs = self.store.get_messages(sid)
        self.messages = msgs
        self._render_recap(msgs)

    def _cmd_save(self, arg: str) -> None:
        path = Path(arg) if arg else (Path.home() / ".ocos" /
                                      f"ocos_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([
            {"role": m["role"], "content": m["content"], "ts": m.get("ts", "")}
            for m in self.messages], ensure_ascii=False, indent=2), encoding="utf-8")
        self._sys_line(f"[dim]已保存到 {escape(str(path))}[/dim]")

    def _cmd_busy(self, arg: str) -> None:
        mode = arg.strip().lower() or "status"
        if mode == "status":
            self._sys_line(f"[dim]busy 模式: {self.busy_mode}[/dim]")
            return
        if mode not in ("interrupt", "queue", "steer"):
            self._sys_line("[red]/busy <interrupt|queue|steer|status>[/red]")
            return
        self.busy_mode = mode
        self._sys_line(f"[dim]busy 模式 → {mode}[/dim]")

    def _cmd_queue(self, arg: str) -> None:
        if not arg:
            self._sys_line("[dim]用法: /queue <msg>[/dim]")
            return
        self._route_user_message(arg, kind="queue")

    def _cmd_steer(self, arg: str) -> None:
        if not arg:
            self._sys_line("[dim]用法: /steer <msg>[/dim]")
            return
        self._route_user_message(arg, kind="steer")

    def _cmd_background(self, arg: str) -> None:
        if not arg:
            self._sys_line("[dim]用法: /background <prompt>[/dim]")
            return
        self.background_done += 1
        n = self.background_done
        self._sys_line(f'[dim]🔄 Background task #{n} started: "{escape(arg[:60])}"[/dim]')
        task = asyncio.create_task(self._run_background(n, arg))
        self.background_tasks.append(task)
        task.add_done_callback(lambda _: self._update_status())
        self._update_status()

    async def _run_background(self, n: int, prompt: str) -> None:
        try:
            async with httpx.AsyncClient(base_url=self.api_base, timeout=CONVERSE_TIMEOUT,
                                         trust_env=False) as client:
                resp = await client.post("/ocos/converse", json={"message": prompt})
            reply = resp.json().get("data", {}).get("reply", "（无回复）")
            self._panel(_strip_markdown(reply), f"OCOS (background #{n})", border="cyan")
        except Exception as e:
            self._sys_line(f"[red]后台任务 #{n} 失败: {escape(str(e)[:120])}[/red]")

    async def _cmd_goal(self, arg: str) -> None:
        if not arg:
            self._sys_line("[dim]用法: /goal <msg>[/dim]")
            return
        try:
            async with httpx.AsyncClient(base_url=self.api_base, timeout=API_TIMEOUT,
                                         trust_env=False) as client:
                resp = await client.post("/ocos/goals-from-chat", json={"message": arg})
                data = resp.json()
                if resp.status_code == 200 and data.get("success"):
                    gid = data["data"]["goal_id"]
                    self._tool_line("daemon", "goal", f"已创建 {gid}")
                else:
                    self._sys_line(f"[red]目标创建失败: {escape(str(data.get('detail', ''))[:100])}[/red]")
        except Exception as e:
            self._sys_line(f"[red]目标创建失败: {escape(str(e)[:100])}[/red]")

    def _cmd_approvals(self, arg: str) -> None:
        body = Text()
        if not self._pending_approvals:
            body.append("（无待批项）", style="dim")
        for i, p in enumerate(self._pending_approvals, 1):
            body.append(f" {i}. {p.get('id', '')}  ", style="yellow")
            body.append(f"{str(p.get('text', ''))[:60]}\n")
        body.append("\n /approve <n|id> 批准 · /deny <n|id> 拒绝", style="dim")
        self._panel_from_text(body, "approvals")

    def _resolve_approval(self, arg: str) -> str | None:
        if not arg:
            return None
        if arg.isdigit():
            idx = int(arg) - 1
            if 0 <= idx < len(self._pending_approvals):
                return self._pending_approvals[idx]["id"]
            return None
        for p in self._pending_approvals:
            if p["id"].startswith(arg):
                return p["id"]
        return None

    async def _decide(self, arg: str, approved: bool) -> None:
        pid = self._resolve_approval(arg)
        if not pid:
            self._sys_line("[red]找不到待批项（/approvals 查看）[/red]")
            return
        action = "approve" if approved else "deny"
        try:
            async with httpx.AsyncClient(base_url=self.api_base, timeout=API_TIMEOUT,
                                         trust_env=False) as client:
                resp = await client.post(f"/ocos/approvals/{pid}/{action}")
                msg = resp.json().get("message", "?")
            icon = "✓" if approved else "✗"
            self._sys_line(f"[dim]{icon} {pid} → {msg}[/dim]")
        except Exception as e:
            self._sys_line(f"[red]操作失败: {escape(str(e)[:100])}[/red]")

    def _cmd_approve(self, arg: str):
        return self._decide(arg, approved=True)

    def _cmd_deny(self, arg: str):
        return self._decide(arg, approved=False)

    async def _cmd_self_improve(self, arg: str) -> None:
        self._sys_line("[dim]自省中...[/dim]")
        try:
            async with httpx.AsyncClient(base_url=self.api_base, timeout=CONVERSE_TIMEOUT,
                                         trust_env=False) as client:
                resp = await client.post("/ocos/self-improve")
                d = resp.json().get("data", {})
            proposals = d.get("proposals", [])
            if proposals:
                self._sys_line(f"[dim]自省完成，{len(proposals)} 条提案进入待批队列[/dim]")
                for p in proposals:
                    self._tool_line("daemon", "proposal", str(p.get("title", ""))[:60])
            else:
                self._sys_line(f"[dim]{escape(d.get('note', '本轮没有值得记录的改进点'))}[/dim]")
        except Exception as e:
            self._sys_line(f"[red]自省失败: {escape(str(e)[:100])}[/red]")

    def _cmd_outbox(self, arg: str) -> None:
        body = Text()
        rows = self._recent_outbox[-10:]
        if not rows:
            body.append("（暂无）", style="dim")
        for r in rows:
            body.append(f" [{str(r.get('created_at', ''))[11:16]}] ", style="dim")
            body.append(f"{str(r.get('content', ''))[:80]}\n")
        self._panel_from_text(body, "outbox")

    # ── 补全下拉 ────────────────────────────────────────────────────
    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        value = event.text_area.text
        if value.startswith("/") and " " not in value:
            self._show_completions(value)
        else:
            self._hide_completions()

    def _show_completions(self, value: str) -> None:
        query = value[1:].lower()
        matches = [c for c in COMMANDS if c.startswith(query)]
        ol = self.complete_list
        ol.clear_options()
        for name in matches:
            args, desc = COMMANDS[name]
            label = f"/{name}" + (f" {args}" if args else "")
            ol.add_option(Option(f"  {label:<38} {desc}", id=name))
        ol.display = bool(matches)
        if matches:
            ol.highlighted = 0

    def _hide_completions(self) -> None:
        self.complete_list.display = False

    def accept_completion(self) -> None:
        if not self.completion_open:
            return
        ol = self.complete_list
        option = ol.get_option_at_index(ol.highlighted or 0)
        name = str(option.id)
        args = COMMANDS.get(name, ("", ""))[0]
        self.input_area.text = f"/{name} " if args else f"/{name}"
        self._hide_completions()
        self.input_area.move_cursor(self.input_area.document.end)

    def cycle_completion(self) -> None:
        if self.completion_open:
            ol = self.complete_list
            ol.action_cursor_down()

    def move_completion(self, delta: int) -> None:
        if self.completion_open:
            ol = self.complete_list
            if delta < 0:
                ol.action_cursor_up()
            else:
                ol.action_cursor_down()

    # ── 快捷键动作 ──────────────────────────────────────────────────
    _last_ctrl_c = 0.0

    def action_interrupt(self) -> None:
        now = time.time()
        if self.turn_active:
            self._cancel_turn()
            self._last_ctrl_c = 0.0
            return
        if now - self._last_ctrl_c < 2.0:  # 2 秒内双击 → 强制退出
            self.action_quit()
            return
        self._last_ctrl_c = now
        self._sys_line("[dim]再按一次 Ctrl+C (2s 内) 强制退出 · Ctrl+D 退出[/dim]")

    async def action_editor(self) -> None:
        editor = os.getenv("EDITOR", "vi")
        tmp = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False)
        tmp.write(self.input_area._expand_pastes(self.input_area.text))
        tmp.close()
        try:
            with self.suspend():
                subprocess.call([editor, tmp.name])
            edited = Path(tmp.name).read_text(encoding="utf-8")
            if edited.strip():
                self.input_area.text = edited
                self.input_area.move_cursor(self.input_area.document.end)
        finally:
            os.unlink(tmp.name)
        self.input_area.focus()

    def action_clear(self) -> None:
        self.chat_log.clear()
        self._sys_line("[dim]对话已清屏（会话历史保留, /save 导出）[/dim]")

    # ── 退出摘要（Hermes: Resume this session with...） ─────────────
    def session_stats(self) -> dict:
        counts = self.store.count_messages(self.session_id)
        return {
            "session_id": self.session_id,
            "duration_s": time.time() - self._session_start,
            "user": counts.get("user", 0),
            "assistant": counts.get("assistant", 0),
        }


def _redirect_console_logs() -> None:
    """TUI 接管终端 — 控制台日志改走文件。

    ocos CLI 导入链会给 root logger 挂 StreamHandler(stdout)（JSON 格式），
    httpx 轮询请求的 INFO 日志会绕过 Textual 渲染直写终端，在窗口里滚 JSON。
    本函数只影响 TUI 进程：摘掉控制台 handler，落盘到 ~/.ocos/tui.log。
    """
    import logging

    root = logging.getLogger()
    for h in list(root.handlers):
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
            root.removeHandler(h)
    root.setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        from ocos.logging.formatter import JSONFormatter

        log_path = SESSION_DB.parent / "tui.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(JSONFormatter())
        root.addHandler(fh)
    except Exception:
        pass  # 文件不可用则无日志兜底，绝不污染界面


def run_tui(resume: str | None = None, host: str = "localhost", port: int = 8900,
            mouse: bool = False) -> None:
    """启动 TUI（cmd_chat 入口）。退出后打印恢复摘要。

    mouse=False（默认）不占用终端鼠标上报 — 原生选中/复制/右键粘贴可用；
    传 mouse=True 则启用程序内鼠标（滚动/点击），终端选区会失效。
    """
    _redirect_console_logs()
    app = ChatScreen(resume=resume, api_base=f"http://{host}:{port}")
    app.run(mouse=mouse)
    stats = app.session_stats()
    print()
    print("Resume this session with:")
    print(f" ocos chat --resume {stats['session_id']}")
    print(f"Session: {stats['session_id']}")
    print(f"Duration: {_fmt_duration(stats['duration_s'])}")
    print(f"Messages: {stats['user'] + stats['assistant']}"
          f" ({stats['user']} user, {stats['assistant']} assistant)")


if __name__ == "__main__":
    run_tui()
