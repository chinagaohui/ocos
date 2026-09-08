"""ocos.tui.tui_client — 纯前端 TUI 客户端（无任何业务逻辑）。

只做：界面渲染、接收用户输入、转交给 Gateway；消费 Gateway 事件并展示。
认知/决策/记忆/LLM 全部在后台 Gateway；关闭本 TUI 不影响内核运行。

启动：python -m ocos.tui.tui_client [--host H --port P]
"""

from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Static
from rich.text import Text

from ocos.tui.ws_client import OcosWsClient
from ocos.tui.widgets import InputBox, LogView, StatusBar


class OcosTuiFrontend(App):
    """与 Gateway 交互的纯前端终端界面。"""

    TITLE = "OCOS TUI"

    CSS = """
    Screen { background: #101216; }
    #log { height: 1fr; padding: 0 1; background: #101216; }
    #typing { display: none; height: auto; max-height: 6; padding: 0 1;
              color: #c8ccd4; background: #101216; }
    #status { height: 2; background: #16191f; color: #8a919c; padding: 0 1; }
    #input { background: #101216; color: #e6e6e6; border: none; padding: 0 1;
             height: auto; min-height: 1; max-height: 8; }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "退出", priority=True),
        Binding("ctrl+l", "clear_log", "清屏", priority=True),
        Binding("pageup", "page_up", "上翻", priority=True),
        Binding("pagedown", "page_down", "下翻", priority=True),
        Binding("home", "page_home", "置顶", priority=True),
        Binding("end", "page_end", "置底", priority=True),
    ]

    def __init__(self, url: str, token: str = "") -> None:
        super().__init__()
        self.ws = OcosWsClient(url=url, token=token)
        self.session_id = ""
        self.conn_state = "connecting…"
        self.agent_state = "idle"
        self.model = ""
        self.tok_in = 0
        self.tok_out = 0
        self.typing_text = ""

    def compose(self) -> ComposeResult:
        yield LogView(id="log")
        yield Static("", id="typing")
        yield StatusBar("", id="status")
        # 直接落地，不再套 Vertical 容器（容器 auto 高度会被 TextArea
        # 的默认 min-height:1fr 撑满剩余空间，导致底部过高）
        yield InputBox(placeholder="输入指令，回车发送…（/clear 清屏 · /abort 中止）",
                       id="input", soft_wrap=True, show_line_numbers=False)

    @property
    def log_view(self) -> LogView:
        return self.query_one("#log", LogView)

    @property
    def input_box(self) -> InputBox:
        return self.query_one("#input", InputBox)

    @property
    def typing_bar(self) -> Static:
        return self.query_one("#typing", Static)

    async def on_mount(self) -> None:
        self.input_box.focus()
        asyncio.create_task(self.ws.run(self._on_event, self._on_status))

    # ── 事件渲染（只渲染，不理解业务含义） ───────────────────────
    async def _on_event(self, ev: dict) -> None:
        kind = ev.get("kind")
        if kind == "session":
            self.session_id = str(ev.get("session_id", ""))
            # 载入历史（有历史则回放；新会话则不请求）
            if not ev.get("is_new") and self.session_id:
                await self.ws.send({"type": "history", "session_id": self.session_id})
        elif kind == "history":
            for m in ev.get("messages", []):
                role = m.get("role")
                content = str(m.get("content", ""))
                if not content:
                    continue
                if role == "user":
                    self.log_view.log_user_block(content)
                else:
                    self.log_view.log_markdown(content)
        elif kind == "user_message":
            self.log_view.log_user_block(str(ev.get("text", "")))
        elif kind == "agent_delta":
            self.typing_text += str(ev.get("chunk", ""))
            self.typing_bar.update(Text(self.typing_text))
            self.typing_bar.display = True
        elif kind == "agent_done":
            self.typing_bar.display = False
            self.typing_text = ""
            model = str(ev.get("model") or "")
            if model:
                self.model = model
            usage = ev.get("usage")
            if isinstance(usage, dict):
                self.tok_in += int(usage.get("prompt") or 0)
                self.tok_out += int(usage.get("completion") or 0)
            self._update_status_bar()
            reply = str(ev.get("reply", "")).strip()
            if reply:
                self.log_view.log_markdown(reply)
        elif kind == "goal_result":
            self.log_view.log_line("―― 目标执行结果 ――", style="cyan")
            self.log_view.log_markdown(str(ev.get("text", "")))
        elif kind == "error":
            self.typing_bar.display = False
            self.typing_text = ""
            self.log_view.log_line(f"✗ {str(ev.get('msg',''))}", style="red")
        elif kind == "status":
            # running/idle 驱动运行态；connected 等连接层状态不覆盖运行态
            st = ev.get("state", "")
            if st in ("running", "idle"):
                self.agent_state = st
                self._update_status_bar()
        elif kind == "pong":
            pass
        else:
            txt = str(ev.get("text", ""))
            if txt:
                self.log_view.log_line(txt, style="dim")

    def _on_status(self, status: str) -> None:
        self.conn_state = status
        self._update_status_bar()

    def _fmt_tok(self, n: int) -> str:
        return f"{n / 1000:.1f}k" if n >= 1000 else str(n)

    def _update_status_bar(self) -> None:
        """两行状态栏（对齐 OpenClaw）:
        行1 连接|运行态；行2 agent | session | 模型 | tokens。"""
        tokens = (f"{self._fmt_tok(self.tok_in)}/{self._fmt_tok(self.tok_out)}"
                  if (self.tok_in or self.tok_out) else "-")
        bar = (f"{self.conn_state} | {self.agent_state}\n"
               f"agent main | session {self.session_id or '-'} | "
               f"{self.model or '-'} | tokens {tokens}")
        self.query_one("#status", StatusBar).update(Text(bar))

    # ── 输入转发（仅转发，不处理业务） ───────────────────────────
    def on_input_box_submitted(self, event: InputBox.Submitted) -> None:
        text = event.box.text.strip()
        if not text:
            return
        self.input_box.text = ""
        lwr = text.lower()
        if lwr == "/clear":
            self.log_view.clear()
            return
        if lwr == "/abort":
            asyncio.create_task(self.ws.send({"type": "abort", "session_id": self.session_id}))
            self.log_view.log_line("⏸ 已请求中止", style="dim")
            return
        asyncio.create_task(self.ws.send(
            {"type": "chat", "text": text, "session_id": self.session_id}))

    # ── 快捷键动作 ───────────────────────────────────────────────
    def action_clear_log(self) -> None:
        self.log_view.clear()

    def action_page_up(self) -> None:
        self.log_view.scroll_page_up()

    def action_page_down(self) -> None:
        self.log_view.scroll_page_down()

    def action_page_home(self) -> None:
        self.log_view.scroll_home()

    def action_page_end(self) -> None:
        self.log_view.scroll_end()


def run(url: str = "ws://127.0.0.1:8900/ws") -> int:
    OcosTuiFrontend(url=url).run()
    return 0


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="OCOS 纯前端 TUI 客户端")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8900)
    args = ap.parse_args()
    raise SystemExit(run(url=f"ws://{args.host}:{args.port}/ws"))