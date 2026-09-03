"""OCOS TUI - 复刻 Hermes Agent 对话界面

设计参考: ~/.hermes/hermes-agent/apps/desktop/src/components/assistant-ui/
- 用户消息: 右对齐，无标签
- 助手消息: 左对齐，无标签
- 输入框: > 提示符
- 状态栏: 橙色高亮
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import httpx
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Static, Input, Log
from textual.binding import Binding


API_BASE = "http://localhost:8900"


class ChatScreen(App):
    CSS = """
    Screen {
        layout: vertical;
        background: #1a1a1a;
    }
    
    #header {
        height: 5;
        background: #252525;
        border-bottom: solid #3e3e42;
    }
    
    #menu {
        height: 3;
        content-align: center middle;
        color: #858585;
    }
    
    #title {
        height: 2;
        content-align: left middle;
        padding-left: 3;
        color: #d4d4d4;
        text-style: bold;
    }
    
    #chat {
        height: 1fr;
        padding: 1 2;
        overflow-y: auto;
    }
    
    .user-msg {
        text-align: right;
        margin-bottom: 0.5;
        color: #d4d4d4;
    }
    
    .bot-msg {
        text-align: left;
        margin-bottom: 0.5;
        color: #b5cea8;
    }
    
    #input-area {
        height: 4;
        border-top: solid #3e3e42;
        background: #252525;
    }
    
    #input-container {
        height: 2;
        content-align: left middle;
        padding-left: 2;
    }
    
    #input-prompt {
        color: #ce9178;
        text-style: bold;
    }
    
    #input {
        height: 2;
        background: transparent;
        color: #d4d4d4;
        border: none;
        padding: 0;
        margin: 0;
    }
    
    #input-hint {
        height: 2;
        content-align: right middle;
        padding-right: 2;
        color: #6a6a6a;
        text-style: italic;
    }
    
    #status {
        height: 3;
        background: #ce9178;
        color: #1a1a1a;
        content-align: left middle;
        padding-left: 2;
        text-style: bold;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "退出"),
        Binding("ctrl+l", "clear", "清空"),
        Binding("ctrl+s", "save", "保存"),
    ]
    
    def __init__(self):
        super().__init__()
        self.messages: list[dict] = []
        proxy_env_keys = [k for k in os.environ if 'proxy' in k.lower()]
        self._saved_proxies = {k: os.environ.pop(k) for k in proxy_env_keys}
        self._send_task = None
    
    def compose(self) -> ComposeResult:
        with Container(id="header"):
            yield Static("文件(F)  编辑(E)  查看(V)  搜索(S)  终端(T)  帮助(H)", id="menu")
            yield Static("ocos chat", id="title")
        yield Log(id="chat")
        with Vertical(id="input-area"):
            with Container(id="input-container"):
                yield Static(">", id="input-prompt")
                yield Input(placeholder="", id="input")
            yield Static("Enter 发送 · Ctrl+L 清空 · Ctrl+S 保存", id="input-hint")
        yield Static("", id="status")
    
    def on_mount(self) -> None:
        self._add_message("OCOS 已就绪。开始对话...", False)
        self.set_interval(15.0, self._update_status)
        asyncio.create_task(self._update_status())
        self.query_one("#input", Input).focus()
    
    async def _update_status(self) -> None:
        status_el = self.query_one("#status", Static)
        try:
            async with httpx.AsyncClient(base_url=API_BASE, timeout=5.0) as client:
                resp = await client.get("/ocos/introspect")
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    ms = data.get("memory_stats", {})
                    episodes = ms.get("episode_count", 0)
                    beliefs = ms.get("belief_count", 0)
                    patterns = ms.get("pattern_count", 0)
                    pct = min(100, int(episodes / 50))
                    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                    status_el.update(f" agnes-2.5-flash │ {episodes}e/{beliefs}b/{patterns}p │ [{bar}] {pct}% │ 在线 ─ 读取上个会话")
                    return
        except Exception:
            pass
        status_el.update(" OCOS │ 离线 │ 请检查服务 ")
    
    def _add_message(self, text: str, is_user: bool) -> None:
        msg = {"text": text, "is_user": is_user, "timestamp": datetime.now()}
        self.messages.append(msg)
        time = msg["timestamp"].strftime("%H:%M:%S")
        cls = "user-msg" if is_user else "bot-msg"
        # 不显示角色标签，直接显示消息内容
        self.query_one("#chat", Log).write_line(f"[{cls}]{time} ", style=f"{cls} ")
        self.query_one("#chat", Log).write_line(f"[{cls}]{text}[/{cls}]")
    
    async def _send_message(self) -> None:
        inp = self.query_one("#input", Input)
        hint = self.query_one("#input-hint", Static)
        text = inp.value.strip()
        if not text:
            return
        
        self._add_message(text, True)
        inp.value = ""
        hint.display = False
        
        try:
            async with httpx.AsyncClient(base_url=API_BASE, timeout=60.0) as client:
                resp = await client.post("/ocos/converse", json={"message": text})
            
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                reply = data.get("reply", "无回复")
                self._add_message(reply, False)
            else:
                self._add_message(f"错误: HTTP {resp.status_code}", False)
        except Exception as e:
            self._add_message(f"连接失败: {e}", False)
        
        inp.focus()
        hint.display = True
    
    def action_clear(self) -> None:
        self.messages.clear()
        self.query_one("#chat", Log).clear()
        self._add_message("对话已清空", False)
        self.notify("对话已清空", title="操作完成")
    
    def action_save(self) -> None:
        path = Path.home() / ".ocos" / f"ocos_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path.parent.mkdir(exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump([
                {"text": m["text"], "is_user": m["is_user"],
                 "time": m["timestamp"].strftime("%H:%M:%S")}
                for m in self.messages
            ], f, ensure_ascii=False, indent=2)
        self.notify(f"已保存到 {path}", title="保存成功")
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self._send_task and not self._send_task.done():
            return
        self._send_task = asyncio.create_task(self._send_message())


if __name__ == "__main__":
    app = ChatScreen()
    app.run()
