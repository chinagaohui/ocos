"""OCOS TUI - 简洁聊天界面

复刻 openclaw TUI 风格：极简对话界面，无多余面板。
顶部状态栏 + 中间对话区 + 底部输入框。

Usage:
    python -m ocos.interaction.tui
    ocos chat
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

import httpx
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Header, Footer, Static, Input, Button, Markdown
from textual.reactive import reactive


API_BASE = "http://localhost:8900"


class MessageBubble(Static):
    """单条消息气泡"""
    
    def __init__(self, text: str, is_user: bool, timestamp: datetime | None = None):
        super().__init__()
        self.text = text
        self.is_user = is_user
        self.timestamp = timestamp or datetime.now()
    
    def compose(self) -> ComposeResult:
        role = "你" if self.is_user else "OCOS"
        time = self.timestamp.strftime("%H:%M")
        content = self.text[:3000]  # 限制长度
        
        if self.is_user:
            yield Static(
                f"[bold cyan]{role}[/bold cyan] [{time}]\n{content}",
                classes="user-msg",
            )
        else:
            yield Static(
                f"[bold green]{role}[/bold green] [{time}]\n{content}",
                classes="bot-msg",
            )


class OCOSTUI(App):
    """OCOS 终端聊天界面"""
    
    CSS = """
    Screen {
        background: $surface;
        color: $text;
    }
    
    #header {
        height: 3;
        background: $primary;
        color: $text;
        text-align: center;
        content-align: center middle;
        border: solid $primary-lighten-1;
    }
    
    #chat-area {
        height: 1fr;
        overflow-y: auto;
        padding: 1 2;
        border: solid $primary;
        margin: 0 1;
    }
    
    .message-row {
        margin-bottom: 1;
        padding: 1;
        border-left: solid $primary;
    }
    
    .user-msg {
        background: $accent;
        color: $text;
        border-left-color: $success;
    }
    
    .bot-msg {
        background: $surface-darken-1;
        color: $text;
        border-left-color: $warning;
    }
    
    #input-bar {
        height: 4;
        layout: horizontal;
        align: center middle;
        padding: 1;
        border-top: solid $primary;
        background: $surface-darken-2;
        margin: 0 1;
    }
    
    #message-input {
        width: 1fr;
        margin-right: 1;
    }
    
    #send-btn {
        min-width: 8;
        margin-right: 1;
    }
    
    #clear-btn {
        min-width: 8;
    }
    
    .status-online {
        color: $success;
    }
    
    .status-offline {
        color: $error;
    }
    """
    
    BINDINGS = [
        ("ctrl+c", "quit", "退出"),
        ("ctrl+l", "clear", "清空"),
        ("ctrl+s", "save", "保存"),
    ]
    
    def __init__(self):
        super().__init__()
        self.messages: list[dict] = []
        self.client = httpx.AsyncClient(base_url=API_BASE, timeout=60.0)
        self._input = Input(placeholder="输入消息... (Enter发送)", id="message-input")
        self._send_btn = Button("发送", id="send-btn", variant="primary")
        self._clear_btn = Button("清空", id="clear-btn")
        self._status = "离线"
        self._episode_count = 0
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        # 头部状态栏
        yield Static(
            f" OCOS · 数字生命体 [{self._status}] · Episodes: {self._episode_count} ",
            id="header",
        )
        
        # 对话区域
        with Vertical(id="chat-area"):
            # 初始消息
            yield MessageBubble("系统初始化完成。等待神经连接...", is_user=False, 
                              timestamp=datetime.now().replace(hour=0, minute=0, second=0))
            for msg in self.messages:
                yield MessageBubble(msg["text"], msg["is_user"], msg["timestamp"])
        
        # 底部输入栏
        with Container(id="input-bar"):
            yield self._input
            yield self._send_btn
            yield self._clear_btn
        
        yield Footer()
    
    async def _poll_status(self) -> None:
        """轮询系统状态"""
        try:
            async with self.client as client:
                resp = await client.get("/ocos/introspect")
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    ms = data.get("memory_stats", {})
                    self._episode_count = ms.get("episode_count", 0)
                    self._status = "在线"
        except Exception:
            self._status = "离线"
    
    async def _send_message(self) -> None:
        """发送消息到 API"""
        text = self._input.value.strip()
        if not text:
            return
        
        # 添加用户消息
        user_msg = {"text": text, "is_user": True, "timestamp": datetime.now()}
        self.messages.append(user_msg)
        self._input.value = ""
        self.refresh()
        
        # 显示加载中
        loading_msg = MessageBubble("思考中...", is_user=False, timestamp=datetime.now())
        self.query_one("#chat-area", Vertical).mount(loading_msg)
        self.query_one("#chat-area", Vertical).scroll_end()
        
        try:
            async with self.client as client:
                resp = await client.post(
                    "/ocos/converse",
                    json={"message": text},
                )
            
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                reply = data.get("reply", "无回复")
                bot_msg = {"text": reply, "is_user": False, "timestamp": datetime.now()}
                self.messages.append(bot_msg)
                self.query_one("#chat-area", Vertical).remove_children()
                for msg in self.messages[-50:]:  # 显示最近50条
                    self.query_one("#chat-area", Vertical).mount(
                        MessageBubble(msg["text"], msg["is_user"], msg["timestamp"])
                    )
            else:
                error_msg = {"text": f"错误: HTTP {resp.status_code}", "is_user": False, 
                           "timestamp": datetime.now()}
                self.messages.append(error_msg)
                self.refresh()
        except Exception as e:
            error_msg = {"text": f"连接失败: {e}", "is_user": False, "timestamp": datetime.now()}
            self.messages.append(error_msg)
            self.refresh()
        
        self.query_one("#chat-area", Vertical).scroll_end()
        self._input.focus()
    
    def action_clear(self) -> None:
        """清空对话"""
        self.messages.clear()
        self.query_one("#chat-area", Vertical).remove_children()
        self.query_one("#chat-area", Vertical).mount(
            MessageBubble("对话已清空", is_user=False, timestamp=datetime.now())
        )
        self.notify("对话已清空", title="操作完成")
    
    def action_save(self) -> None:
        """保存对话历史"""
        from pathlib import Path
        filename = f"ocos_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path = Path.home() / ".ocos" / filename
        path.parent.mkdir(exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump([
                {"text": m["text"], "is_user": m["is_user"], 
                 "time": m["timestamp"].strftime("%H:%M:%S")}
                for m in self.messages
            ], f, ensure_ascii=False, indent=2)
        self.notify(f"已保存到 {path}", title="保存成功")
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """回车发送"""
        asyncio.create_task(self._send_message())
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """按钮点击"""
        if event.button.id == "send-btn":
            asyncio.create_task(self._send_message())
        elif event.button.id == "clear-btn":
            self.action_clear()
    
    def on_mount(self) -> None:
        """启动时初始化"""
        self.set_interval(10.0, self._poll_status)
        asyncio.create_task(self._poll_status())
        self._input.focus()
        self.notify("OCOS TUI 已启动", title="就绪")


if __name__ == "__main__":
    app = OCOSTUI()
    app.run()
