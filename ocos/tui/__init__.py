"""OCOS-TUI 纯前端终端客户端包。

严格约束：本目录代码只做交互渲染（布局、输入、滚动、复制粘贴、状态展示），
通过 WebSocket 收发 JSON 事件；【禁止】导入任何 ocos 内核/业务模块。
业务全部由常驻 Gateway 承载（ocos-server + ocos-daemon）。
"""