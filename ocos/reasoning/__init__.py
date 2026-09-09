"""OCOS 符号推理层（Symbolic Reasoning）。

不依赖 LLM 的自主思考组件——纯 Belief/Pattern/Episode 数据驱动的
因果预测。让 OCOS 能在简单场景下自己"想清楚再做"，而不是每次都
调 LLM。

Pillar 1: SymbolicReasoner 预测器
Pillar 2: 相似度引擎（bi-gram overlap）
"""
