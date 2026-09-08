"""ocos.tui.widgets — 纯前端 UI 组件（无业务逻辑）。

仅做容器与渲染结构：日志面板、底部状态栏、输入框。
渲染风格对齐 OpenClaw：助手回复走 Markdown（表格/列表/加粗），
用户消息渲染为全宽暗色块。
"""

from __future__ import annotations

from rich.cells import cell_len
from rich.markdown import Markdown
from rich.text import Text
from textual.binding import Binding
from textual.message import Message
from textual.widgets import RichLog, Static, TextArea


class LogView(RichLog):
    """滚动日志面板 — 渲染 Gateway 推送的事件文本。"""

    def __init__(self, **kwargs) -> None:
        super().__init__(wrap=True, markup=False, highlight=False, **kwargs)

    def _sep(self) -> None:
        """消息块之间的空行间隔（首条消息前不加）。"""
        if self.lines:
            self.write("")

    def _content_width(self) -> int:
        w = self.size.width
        return max(20, w - 2) if w > 6 else 60

    def log_line(self, text: str, style: str = "") -> None:
        self.write(Text(text, style=style) if style else text)

    def log_markdown(self, text: str) -> None:
        """助手回复 — Markdown 渲染（表格/列表/加粗，对齐 OpenClaw）。"""
        self._sep()
        self.write(Markdown(text))

    def log_user_block(self, text: str) -> None:
        """用户消息 — 全宽暗色块（OpenClaw 样式，中文宽度安全）。"""
        self._sep()
        width = self._content_width()
        for ln in text.split("\n") or [""]:
            t = Text(ln, style="#b8bec8 on #262b34")
            pad = width - cell_len(ln)
            if pad > 0:
                t.pad_right(pad)
            self.write(t)


class StatusBar(Static):
    """底部状态栏 — 两行（对齐 OpenClaw）：

    行1: 连接态 | 运行态    行2: agent | session | 模型 | tokens（全部来自事件）。
    """


class InputBox(TextArea):
    """底部多行输入框 — Enter 发送 / Shift+Enter 换行。

    注: TextArea 默认回车是插入换行且无 Submitted 消息（那是单行
    TextInput 的），故自行绑定 enter→submit 并 post 自定义消息。
    """

    BINDINGS = [
        Binding("enter", "submit", "发送", priority=True),
        Binding("shift+enter", "newline", "换行", show=False),
    ]

    class Submitted(Message):
        """回车提交输入框内容（冒泡给 App 处理）。"""

        def __init__(self, box: "InputBox") -> None:
            self.box = box
            super().__init__()

        @property
        def control(self) -> "InputBox":
            return self.box

    def action_submit(self) -> None:
        self.post_message(self.Submitted(self))

    def action_newline(self) -> None:
        self.insert("\n")
