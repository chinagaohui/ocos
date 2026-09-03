"""OCOS TUI - 简洁对话界面

纯对话布局：消息区域 + 底部输入框

Usage:
    python -m ocos.interaction.tui
    ocos chat
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
from textual.widgets import Static, Input, Button, Footer
from textual.binding import Binding


API_BASE = "http://localhost:8900"


class MessageBlock(Static):
    """消息气泡"""
    
    def __init__(self, text: str, is_user: bool):
        super().__init__()
        self.text = text
        self.is_user = is_user
        self.timestamp = datetime.now()
    
    def compose(self) -> ComposeResult:
        role = "你" if self.is_user else "OCOS"
        time = self.timestamp.strftime("%H:%M:%S")
        content = self.text[:5000]
        
        if self.is_user:
            yield Static(f"[bold cyan]{role}[/bold cyan] {time}\n{content}", classes="user-msg")
        else:
            yield Static(f"[bold green]{role}[/bold green] {time}\n{content}", classes="bot-msg")


class ChatScreen(App):
    """简洁对话界面"""
    
    CSS = """
    Screen {
        layout: vertical;
        background: $surface;
    }
    
    #chat-area {
        height: 1fr;
        overflow-y: auto;
        padding: 1 2;
    }
    
    .message {
        margin-bottom: 1;
        padding: 1 2;
    }
    
    .user-msg {
        text-align: right;
        border-right: thick $success;
    }
    
    .bot-msg {
        text-align: left;
        border-left: thick $warning;
    }
    
    #input-bar {
        height: 4;
        layout: horizontal;
        align: center middle;
        padding: 1;
        border-top: solid $primary;
        background: $surface-darken-2;
    }
    
    #message-input {
        width: 1fr;
        margin-right: 1;
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
        self.chat_area = Vertical(id="chat-area")
        self._input = Input(placeholder="输入消息... (Enter 发送)", id="message-input")
        self._send_btn = Button("发送", id="send-btn", variant="primary")
        self._clear_btn = Button("清空", id="clear-btn")
        
        # 清除代理环境变量
        proxy_env_keys = [k for k in os.environ if 'proxy' in k.lower()]
        self._saved_proxies = {k: os.environ.pop(k) for k in proxy_env_keys}
        self.client = httpx.AsyncClient(base_url=API_BASE, timeout=60.0)
        
        self._send_task = None
    
    def compose(self) -> ComposeResult:
        yield self.chat_area
        
        with Container(id="input-bar"):
            yield self._input
            yield self._send_btn
            yield self._clear_btn
        
        yield Footer()
    
    def on_mount(self) -> None:
        """挂载后添加初始消息"""
        self.chat_area.mount(MessageBlock("OCOS 已就绪。开始对话...", False))
    
    async def _send_message(self) -> None:
        """发送消息"""
        text = self._input.value.strip()
        if not text:
            return
        
        # 添加用户消息
        self.messages.append({"text": text, "is_user": True, "timestamp": datetime.now()})
        self.chat_area.mount(MessageBlock(text, True))
        self._input.value = ""
        self.chat_area.scroll_end()
        
        # 显示加载中
        loading = MessageBlock("思考中...", False)
        self.chat_area.mount(loading)
        self.chat_area.scroll_end()
        
        try:
            async with self.client as client:
                resp = await client.post("/ocos/converse", json={"message": text})
            
            # 移除加载提示
            self.chat_area.remove_child(loading)
            
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                reply = data.get("reply", "无回复")
                self.messages.append({"text": reply, "is_user": False, "timestamp": datetime.now()})
                self.chat_area.mount(MessageBlock(reply, False))
            else:
                self.chat_area.mount(MessageBlock(f"错误: HTTP {resp.status_code}", False))
        except Exception as e:
            self.chat_area.mount(MessageBlock(f"连接失败: {e}", False))
        
        self.chat_area.scroll_end()
        self._input.focus()
    
    def action_clear(self) -> None:
        """清空对话"""
        self.messages.clear()
        self.chat_area.remove_children()
        self.chat_area.mount(MessageBlock("对话已清空", False))
        self.notify("对话已清空", title="操作完成")
    
    def action_save(self) -> None:
        """保存对话"""
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
        """回车发送"""
        if self._send_task and not self._send_task.done():
            return
        self._send_task = asyncio.create_task(self._send_message())
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """按钮点击"""
        if event.button.id == "send-btn":
            if not (self._send_task and self._send_task.done()):
                self._send_task = asyncio.create_task(self._send_message())
        elif event.button.id == "clear-btn":
            self.action_clear()
    
    async def on_mount(self) -> None:
        """启动时初始化"""
        self._input.focus()
        self.notify("OCOS TUI 已启动", title="就绪")
    
    async def on_unmount(self) -> None:
        """退出时清理"""
        if self._send_task and not self._send_task.done():
            self._send_task.cancel()
        await self.client.aclose()
        os.environ.update(self._saved_proxies)


if __name__ == "__main__":
    app = ChatScreen()
    app.run()
