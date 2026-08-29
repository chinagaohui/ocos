"""P2-D: 主动输出模板池 — 全确定性模板，无 LLM。

三类模板（问候 / 观察 / 提问），按审计计数轮换选择。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProactiveTemplate:
    """一条主动输出模板。

    Attributes:
        kind: 模板类别（greeting / observation / question）
        text: 模板文案；{topic} 占位符由引擎以确定性方式填充
    """

    kind: str
    text: str


TEMPLATE_POOL: tuple[ProactiveTemplate, ...] = (
    ProactiveTemplate(kind="greeting", text="今天有什么想聊聊的吗？我一直在。"),
    ProactiveTemplate(kind="observation", text="注意到你最近常关注「{topic}」，需要我一起看看吗？"),
    ProactiveTemplate(kind="question", text="有一个小问题想请教你：你最近在做的事情里，最有趣的部分是什么？"),
)


def select_template(index: int, topic: str = "") -> ProactiveTemplate:
    """确定性轮换选择模板（index = 已输出次数，取模轮换）。

    {topic} 占位符为空时回退为通用问候（避免空占位输出）。
    """
    template = TEMPLATE_POOL[index % len(TEMPLATE_POOL)]
    if "{topic}" in template.text:
        if not topic:
            template = TEMPLATE_POOL[0]  # 无主题 → 回退问候
        else:
            text = template.text.format(topic=topic)
            return ProactiveTemplate(kind=template.kind, text=text)
    return template
