"""OCOS TUI - 终端交互界面

基于Textual构建的终端用户界面，复刻openclaw的TUI风格。
连接OCOS API (localhost:8900) 提供对话和状态监控。

Usage:
    python -m ocos.interaction.tui
"""

from __future__ import annotations

import asyncio
import json
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
    DataTable,
    TextArea,
    Button,
    Input,
    LoadingIndicator,
    ListView,
    ListItem,
    SelectionList,
    TabbedContent,
    TabPane,
)
from textual.reactive import reactive
from textual.message import Message


# ── 配置 ──────────────────────────────────────────────────────
API_BASE = "http://localhost:8900"
DEFAULT_SESSION = "ocos-tui"


# ── 消息数据类 ────────────────────────────────────────────────
class ChatMessage:
    """对话消息"""
    def __init__(self, text: str, is_user: bool, timestamp: datetime | None = None):
        self.text = text
        self.is_user = is_user
        self.timestamp = timestamp or datetime.now()
    
    @property
    def display_time(self) -> str:
        return self.timestamp.strftime("%H:%M:%S")


class OCOSStatus:
    """OCOS系统状态"""
    def __init__(self):
        self.episodes: int = 0
        self.beliefs: int = 0
        self.patterns: int = 0
        self.engines: dict[str, str] = {}
        self.goals: list[dict] = []
        self.is_online: bool = False


# ── TUI组件 ───────────────────────────────────────────────────

class MessageBubble(Static):
    """消息气泡组件"""
    
    def __init__(self, message: ChatMessage):
        super().__init__()
        self.message = message
    
    def compose(self) -> ComposeResult:
        content = self.message.text
        if not self.message.is_user:
            # 解析JSON内容（如果是结构化数据）
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    content = data.get("reply", content)
            except (json.JSONDecodeError, KeyError):
                pass
        
        yield Static(
            f"[bold cyan]{self.message.display_time}[/bold cyan] "
            f"{'[bold green]YOU[/bold green]' if self.message.is_user else '[bold blue]OCOS[/bold blue]'}:\n"
            f"[dim]{content}[/dim]",
            classes="message" if self.message.is_user else "response",
        )


class StatusPanel(Static):
    """左侧状态面板"""
    
    def __init__(self, status: OCOSStatus):
        super().__init__()
        self.status = status
    
    def compose(self) -> ComposeResult:
        yield Static("[bold]系统状态[/bold]", classes="panel-title")
        yield Static(
            f"[bold]记忆容量:[/bold] {self.status.episodes} episodes\n"
            f"[bold]Beliefs:[/bold] {self.status.beliefs}\n"
            f"[bold]Patterns:[/bold] {self.status.patterns}\n"
            f"[bold]状态:[/bold] {'[green]在线[/green]' if self.status.is_online else '[red]离线[/red]'}",
            classes="status-info",
        )


class ChatPanel(Static):
    """对话面板"""
    
    def __init__(self):
        super().__init__()
        self.messages: list[ChatMessage] = []
    
    def compose(self) -> ComposeResult:
        yield Static("[bold]神经对话[/bold]", classes="panel-title")
        # 消息列表
        for msg in self.messages[-50:]:  # 最多显示50条
            yield MessageBubble(msg)
    
    def add_message(self, text: str, is_user: bool):
        """添加消息"""
        msg = ChatMessage(text, is_user)
        self.messages.append(msg)
        self.refresh()
    
    def clear_messages(self):
        """清空消息"""
        self.messages.clear()
        self.refresh()


class TaskList(Static):
    """任务列表面板"""
    
    def __init__(self):
        super().__init__()
        self.tasks: list[dict] = []
    
    def compose(self) -> ComposeResult:
        yield Static("[bold]活跃目标[/bold]", classes="panel-title")
        if not self.tasks:
            yield Static("[dim]无活跃目标[/dim]")
        else:
            for task in self.tasks[-10:]:
                status = task.get("status", "unknown")
                title = task.get("title", "Untitled")
                color = "green" if status == "completed" else "yellow" if status == "pending" else "red"
                yield Static(f"[{color}]●[/{color}] {title} [{status}]")


class InputBar(Container):
    """底部输入栏"""
    
    def __init__(self):
        super().__init__()
        self._input = Input(
            placeholder="输入神经脉冲... (Enter发送, /clear清空)",
            id="chat-input",
        )
        self._send_btn = Button("发送", id="send-btn", variant="primary")
        self._clear_btn = Button("清空", id="clear-btn")
        self._loading = LoadingIndicator(id="loading")
        self._loading.display = False
    
    def compose(self) -> ComposeResult:
        yield self._input
        yield self._loading
        yield self._send_btn
        yield self._clear_btn
    
    @property
    def input_value(self) -> str:
        return self._input.value
    
    @input_value.setter
    def input_value(self, value: str):
        self._input.value = value
    
    @property
    def is_loading(self) -> bool:
        return self._loading.display
    
    @is_loading.setter
    def is_loading(self, value: bool):
        self._loading.display = value
        self._send_btn.disabled = value


class OCOSTUI(App):
    """OCOS TUI主应用"""
    
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
    
    .main-container {
        height: 100%;
        layout: grid;
        grid-size: 3;
        grid-gaps: 1;
    }
    
    .left-panel {
        width: 25;
        height: 100%;
        border-right: solid $primary;
        padding: 1;
    }
    
    .center-panel {
        width: 1fr;
        height: 100%;
        overflow-y: auto;
        padding: 1;
    }
    
    .right-panel {
        width: 25;
        height: 100%;
        border-left: solid $primary;
        padding: 1;
    }
    
    .panel-title {
        text-align: center;
        background: $primary-darken-1;
        color: $text;
        padding: 1 2;
        margin-bottom: 1;
    }
    
    .status-info {
        padding: 1;
        margin-bottom: 1;
    }
    
    .message {
        padding: 1 2;
        margin-bottom: 1;
        border-left: solid $primary;
        background: $surface-darken-1;
    }
    
    .response {
        padding: 1 2;
        margin-bottom: 1;
        border-left: solid $success;
        background: $success-darken-2;
    }
    
    #input-bar {
        height: 4;
        layout: horizontal;
        align: center middle;
        padding: 1;
        border-top: solid $primary;
        background: $surface-darken-2;
    }
    
    #chat-input {
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
    
    #loading {
        margin: 0 1;
    }
    """
    
    BINDINGS = [
        ("ctrl+c", "quit", "退出"),
        ("ctrl+l", "clear", "清空"),
        ("ctrl+s", "save", "保存"),
        ("escape", "cancel", "取消"),
    ]
    
    def __init__(self):
        super().__init__()
        self.status = OCOSStatus()
        self.chat_panel = ChatPanel()
        self.task_list = TaskList()
        self.client = httpx.AsyncClient(base_url=API_BASE, timeout=30.0)
        self._input_bar = InputBar()
        self._poll_task: asyncio.Task | None = None
        self._send_task: asyncio.Task | None = None
    
    def on_mount(self) -> None:
        """应用启动时初始化"""
        self.set_interval(5.0, self._poll_status)
        self._input_bar.input.focus()
        self.notify("OCOS TUI 已启动，连接到 localhost:8900", title="就绪")
    
    async def _poll_status(self) -> None:
        """轮询系统状态"""
        try:
            async with self.client as client:
                resp = await client.get("/ocos/introspect")
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    ms = data.get("memory_stats", {})
                    self.status.episodes = ms.get("episode_count", 0)
                    self.status.beliefs = ms.get("belief_count", 0)
                    self.status.patterns = ms.get("pattern_count", 0)
                    self.status.is_online = True
                    # 更新UI
                    self.query_one("#status-episodes", Static).update(
                        f"[bold]记忆容量:[/bold] {self.status.episodes} episodes"
                    )
                    self.query_one("#status-beliefs", Static).update(
                        f"[bold]Beliefs:[/bold] {self.status.beliefs}"
                    )
                    self.query_one("#status-patterns", Static).update(
                        f"[bold]Patterns:[/bold] {self.status.patterns}"
                    )
                    self.query_one("#status-online", Static).update(
                        f"[bold]状态:[/bold] [green]在线[/green]"
                    )
        except Exception as e:
            self.status.is_online = False
            self.query_one("#status-online", Static).update(
                f"[bold]状态:[/bold] [red]离线 ({e})[/red]"
            )
    
    async def _send_message(self) -> None:
        """发送消息"""
        text = self._input_bar.input_value.strip()
        if not text:
            return
        
        # 清除输入
        self._input_bar.input_value = ""
        
        # 显示用户消息
        self.chat_panel.add_message(text, is_user=True)
        self._input_bar.is_loading = True
        
        # 发送请求
        try:
            async with self.client as client:
                resp = await client.post(
                    "/ocos/converse",
                    json={"message": text},
                )
            
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                reply = data.get("reply", "无回复")
                self.chat_panel.add_message(reply, is_user=False)
            else:
                self.chat_panel.add_message(f"错误: HTTP {resp.status_code}", is_user=False)
                
        except httpx.HTTPError as e:
            self.chat_panel.add_message(f"连接失败: {e}", is_user=False)
        except Exception as e:
            self.chat_panel.add_message(f"未知错误: {e}", is_user=False)
        finally:
            self._input_bar.is_loading = False
            self._input_bar.input.focus()
    
    def action_clear(self) -> None:
        """清空对话"""
        self.chat_panel.clear_messages()
        self.notify("对话已清空", title="操作完成")
    
    def action_save(self) -> None:
        """保存对话历史"""
        filename = f"ocos_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path = Path.home() / ".ocos" / filename
        path.parent.mkdir(exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                [{"text": m.text, "is_user": m.is_user, "time": m.display_time} 
                 for m in self.chat_panel.messages],
                f,
                ensure_ascii=False,
                indent=2,
            )
        self.notify(f"已保存到 {path}", title="保存成功")
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """回车发送"""
        self._send_task = asyncio.create_task(self._send_message())
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """按钮点击"""
        if event.button.id == "send-btn":
            self._send_task = asyncio.create_task(self._send_message())
        elif event.button.id == "clear-btn":
            self.action_clear()
    
    def compose(self) -> ComposeResult:
        """构建UI"""
        yield Header()
        
        # 主容器
        with Container(id="main-container"):
            # 左侧面板 - 状态
            with Vertical(classes="left-panel"):
                yield Static("[bold]系统状态[/bold]", classes="panel-title")
                yield Static(f"[bold]记忆容量:[/bold] {self.status.episodes} episodes", id="status-episodes")
                yield Static(f"[bold]Beliefs:[/bold] {self.status.beliefs}", id="status-beliefs")
                yield Static(f"[bold]Patterns:[/bold] {self.status.patterns}", id="status-patterns")
                yield Static(f"[bold]状态:[/bold] {'[green]在线[/green]' if self.status.is_online else '[red]离线[/red]'}", id="status-online")
                
                yield Static("\n[bold]最近活动[/bold]", classes="panel-title")
                yield Static("[dim]等待数据...\n", id="recent-activity")
            
            # 中间面板 - 对话
            with Vertical(classes="center-panel"):
                yield Static("[bold]神经对话[/bold]", classes="panel-title")
                yield from self.chat_panel.compose()
            
            # 右侧面板 - 任务
            with Vertical(classes="right-panel"):
                yield Static("[bold]活跃目标[/bold]", classes="panel-title")
                yield from self.task_list.compose()
        
        # 底部输入栏
        yield self._input_bar
        yield Footer()
    
    def on_mount(self) -> None:
        """应用启动时初始化"""
        self.set_interval(5.0, self._poll_status)
        self._input_bar.input.focus()
        self.notify("OCOS TUI 已启动，连接到 localhost:8900", title="就绪")
        
        # 立即获取一次状态
        asyncio.create_task(self._poll_status())
    
    async def on_unmount(self) -> None:
        """退出时清理"""
        if self._send_task and not self._send_task.done():
            self._send_task.cancel()
        await self.client.aclose()


if __name__ == "__main__":
    app = OCOSTUI()
    app.run()
