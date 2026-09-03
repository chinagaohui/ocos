"""OCOS TUI - 简洁对话界面"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import httpx
from textual.app import App, ComposeResult
from textual.widgets import Static, Input, Log
from textual.binding import Binding


API_BASE = "http://localhost:8900"


class ChatScreen(App):
    CSS = """
    Screen {
        layout: vertical;
        background: #1e1e1e;
    }
    
    #title {
        height: 2;
        content-align: left middle;
        padding-left: 2;
        color: #d4c99a;
        text-style: bold;
        border-bottom: solid #d4c99a;
    }
    
    #messages {
        height: 1fr;
        padding: 1 2;
        overflow-y: auto;
    }
    
    #input-bar {
        height: 3;
        border-top: solid #d4c99a;
        background: #2d2d2d;
    }
    
    #input {
        background: #2d2d2d;
        color: white;
        border: none;
    }
    
    #status-bar {
        height: 3;
        background: #000000;
        color: #cccccc;
        content-align: left middle;
        padding-left: 2;
        border-top: solid #555;
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
        yield Static("ocos chat", id="title")
        yield Log(id="messages")
        yield Input(placeholder="输入消息... (Enter 发送)", id="input")
        yield Static("", id="status-bar")
    
    def on_mount(self) -> None:
        self._add_message("OCOS 已就绪。开始对话...", False)
        self.set_interval(15.0, self._update_status)
        asyncio.create_task(self._update_status())
        self.query_one("#input", Input).focus()
    
    async def _update_status(self) -> None:
        status_el = self.query_one("#status-bar", Static)
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
        role = "你" if is_user else "OCOS"
        time = msg["timestamp"].strftime("%H:%M:%S")
        cls = "[cyan]" if is_user else "[bold green]"
        self.query_one("#messages", Log).write_line(f"{cls}{role}[/{cls.replace('[', '').replace(']', '')}] {time}\n{text}")
    
    async def _send_message(self) -> None:
        inp = self.query_one("#input", Input)
        text = inp.value.strip()
        if not text:
            return
        
        self._add_message(text, True)
        inp.value = ""
        
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
    
    def action_clear(self) -> None:
        self.messages.clear()
        self.query_one("#messages", Log).clear()
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
