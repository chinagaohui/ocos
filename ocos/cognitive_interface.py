"""OCOS Cognitive Interface — 统一认知交互入口。

4 种交互模式:
    CLI    — ocos <command>          (python3 -m ocos.interaction.cli)
    REPL   — ocos-repl              (python3 -m ocos.interaction.repl)
    API    — ocos-api               (python3 -m ocos.interaction.api)
    Python — CognitiveInterface()   (程序化接口)

这是 `from ocos.cognitive_interface import CognitiveInterface` 的命名空间桥接。
"""

from ocos.interaction.cognitive_interface import CognitiveInterface

__all__ = ["CognitiveInterface"]
