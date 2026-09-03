"""OCOS TUI - 复刻 Hermes Agent chat 界面

布局：
- 左侧：会话列表
- 中间：对话 transcript
- 底部：输入框（composer）

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
from typing import Any

import httpx
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Header, 
    Footer, 
    Static, 
    Input, 
    Button, 
    DataTable,
    Label,
)
from textual.binding import Binding


API_BASE = "http://localhost:8900"


class MessageBlock(Static):
    """单条消息块"""
    
    def __init__(self, text: str, is_user: bool, timestamp: datetime | None = None):
        super().__init__()
        self.text = text
        self.is_user = is_user
        self.timestamp = timestamp or datetime.now()
    
    def compose(self) -> ComposeResult:
        role = "你" if self.is_user else "OCOS"
        time = self.timestamp.strftime("%H:%M:%S")
        content = self.text[:5000]
        
        prefix = "[bold cyan]" if self.is_user else "[bold green]"
        yield Static(f"{prefix}{role}[/bold] {time}\n{content}")


class ChatArea(Container):
    """对话区域"""
    
    def __init__(self):
        super().__init__(classes="chat-area")
        self.messages: list[dict] = []
    
    def add_message(self, text: str, is_user: bool) -> None:
        """添加消息"""
        msg = {"text": text, "is_user": is_user, "timestamp": datetime.now()}
        self.messages.append(msg)
        self.mount(MessageBlock(text, is_user, msg["timestamp"]))
        self.scroll_end()
    
    def clear(self) -> None:
        """清空对话"""
        self.messages.clear()
        self.remove_children()
        self.mount(MessageBlock("对话已清空", False, datetime.now()))
    
    def save(self, path: Path | None = None) -> Path:
        """保存对话历史"""
        if not path:
            path = Path.home() / ".ocos" / f"ocos_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path.parent.mkdir(exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump([
                {"text": m["text"], "is_user": m["is_user"], 
                 "time": m["timestamp"].strftime("%H:%M:%S")}
                for m in self.messages
            ], f, ensure_ascii=False, indent=2)
        return path


class SessionList(DataTable):
    """左侧会话列表"""
    
    def __init__(self):
        super().__init__(id="session-list")
        self.add_columns("会话ID", "标题", "时间")
        self.cursor_type = "row"
        self.fixed_rows = 1
        self.show_cursor = True
    
    def add_session(self, session_id: str, title: str, time: str) -> None:
        """添加会话"""
        self.add_row(session_id[:8], title[:30], time)


class Composer(Container):
    """底部输入框"""
    
    def __init__(self):
        super().__init__(id="composer")
        self._input = Input(
            placeholder="输入消息... (Enter 发送)",
            id="message-input",
        )
        self._send_btn = Button("发送", id="send-btn", variant="primary")
        self._clear_btn = Button("清空", id="clear-btn")
    
    def compose(self) -> ComposeResult:
        yield Label("[bold]输入[/bold]")
        with Horizontal():
            yield self._input
            yield self._send_btn
            yield self._clear_btn


class OcosChatScreen(App):
    """OCOS 聊天界面"""
    
    CSS = """
    Screen {
        layout: vertical;
    }
    
    #left-panel {
        width: 25%;
        height: 1fr;
        border: solid $primary;
        background: $surface-darken-1;
    }
    
    #center-panel {
        width: 50%;
        height: 1fr;
        border: solid $primary;
        background: $surface;
        overflow-y: auto;
    }
    
    #right-panel {
        width: 25%;
        height: 1fr;
        border: solid $primary;
        background: $surface-darken-1;
        overflow-y: auto;
    }
    
    #composer {
        height: 8;
        border: solid $primary;
        background: $surface-darken-2;
        padding: 1;
    }
    
    .message {
        padding: 1 2;
        margin: 1 0;
    }
    
    .user-message {
        text-align: right;
    }
    
    .assistant-message {
        text-align: left;
    }
    
    DataTable {
        width: 100%;
        height: 1fr;
    }
    
    #message-input {
        width: 1fr;
        margin-right: 1;
    }
    
    Label {
        text-align: center;
        height: 3;
        content-align: center middle;
    }
    
    #system-status {
        padding: 1 2;
    }
    
    .panel-title {
        text-align: center;
        height: 3;
        content-align: center middle;
        border-bottom: solid $primary;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "退出"),
        Binding("ctrl+l", "clear", "清空"),
        Binding("ctrl+s", "save", "保存"),
    ]
    
    def __init__(self):
        super().__init__()
        self.chat_area = ChatArea()
        self.session_list = SessionList()
        self.composer = Composer()
        
        # 清除代理环境变量，避免socks代理导致连接失败
        proxy_env_keys = [k for k in os.environ if 'proxy' in k.lower()]
        self._saved_proxies = {k: os.environ.pop(k) for k in proxy_env_keys}
        self.client = httpx.AsyncClient(base_url=API_BASE, timeout=60.0)
        
        self._status = "离线"
        self._episode_count = 0
        self._current_session = "main"
        self._send_task = None
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        # 中间区域：左中右三栏
        with Horizontal():
            # 左侧：会话列表
            with Container(id="left-panel"):
                yield Label("[bold]会话列表[/bold]", classes="panel-title")
                yield self.session_list
            
            # 中间：对话区域
            with Container(id="center-panel"):
                yield self.chat_area
            
            # 右侧：系统状态
            with Container(id="right-panel"):
                yield Label("[bold]系统状态[/bold]", classes="panel-title")
                yield Static(
                    "[bold]连接状态[/bold]\n"
                    f"状态: {self._status}\n"
                    f"Episodes: {self._episode_count}\n"
                    f"模型: agnes-2.5-flash\n"
                    f"端口: 8900\n",
                    id="system-status",
                )
        
        # 底部：输入框
        yield self.composer
    
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
        
        # 更新右侧状态面板
        status_widget = self.query_one("#system-status", Static)
        status_widget.update(
            f"[bold]连接状态[/bold]\n"
            f"状态: {self._status}\n"
            f"Episodes: {self._episode_count}\n"
            f"模型: agnes-2.5-flash\n"
            f"端口: 8900\n"
        )
    
    async def _send_message(self) -> None:
        """发送消息"""
        text = self.composer._input.value.strip()
        if not text:
            return
        
        # 添加用户消息
        self.chat_area.add_message(text, True)
        self.composer._input.value = ""
        
        # 显示加载中
        loading_msg = MessageBlock("思考中...", False, datetime.now())
        self.chat_area.mount(loading_msg)
        self.chat_area.scroll_end()
        
        try:
            async with self.client as client:
                resp = await client.post(
                    "/ocos/converse",
                    json={"message": text},
                )
            
            # 移除加载提示
            self.chat_area.remove_child(loading_msg)
            
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                reply = data.get("reply", "无回复")
                self.chat_area.add_message(reply, False)
                
                # 添加到会话列表（第一条消息时）
                if len(self.chat_area.messages) == 2:
                    self.session_list.add_row(
                        self._current_session,
                        text[:30] + "..." if len(text) > 30 else text,
                        datetime.now().strftime("%H:%M")
                    )
            else:
                self.chat_area.add_message(f"错误: HTTP {resp.status_code}", False)
        except Exception as e:
            self.chat_area.add_message(f"连接失败: {e}", False)
        
        self.composer._input.focus()
    
    def action_clear(self) -> None:
        """清空对话"""
        self.chat_area.clear()
        self.notify("对话已清空", title="操作完成")
    
    def action_save(self) -> None:
        """保存对话"""
        path = self.chat_area.save()
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
        self.set_interval(10.0, self._poll_status)
        await self._poll_status()
        self.composer._input.focus()
        self.notify("OCOS TUI 已启动", title="就绪")
    
    async def on_unmount(self) -> None:
        """退出时清理"""
        if self._send_task and not self._send_task.done():
            self._send_task.cancel()
        await self.client.aclose()
        # 恢复代理环境变量
        os.environ.update(self._saved_proxies)


if __name__ == "__main__":
    app = OcosChatScreen()
    app.run()
