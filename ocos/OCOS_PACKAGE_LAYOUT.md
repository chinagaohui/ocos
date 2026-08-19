# OCOS Package Layout (Frozen)

**版本**: v1.0
**状态**: Frozen
**冻结日期**: 2026-07-22

## 目录树

```
ocos/
├── __init__.py
├── OCOS_NAMING_CONVENTION.md
├── OCOS_DEPENDENCY_MATRIX.md
├── OCOS_PACKAGE_LAYOUT.md
├── kernel/
│   ├── __init__.py
│   ├── constitution.py         # 宪法硬编码规则 + 运行时约束检查
│   ├── abi.py                  # 核心 dataclass + Event 类型枚举 + schema_version
│   ├── event_schema.py         # Event 定义 + JSON 序列化
│   └── time_manager.py         # 逻辑时钟 + 物理时钟统一源
├── runtime/
│   ├── __init__.py
│   ├── context_manager.py      # B1: Context 数据结构（目标/任务/偏好）
│   ├── scheduler.py            # B3: 优先级调度器
│   ├── policy_engine.py        # B4: 策略求值
│   ├── resource_manager.py     # B5: CPU/内存/GPU 监控
│   └── adaptive_control.py     # B6: 动态参数调节
├── engines/
│   ├── __init__.py
│   ├── reasoning.py            # 推理解释引擎
│   ├── attention.py            # B2: 注意力引擎
│   ├── simulation.py           # 模拟引擎
│   └── learning.py             # 学习引擎
├── plugins/
│   ├── __init__.py
│   ├── sandbox.py              # D2: Plugin 沙箱
│   ├── loader.py               # D3: Plugin 加载器
│   └── opentale/
│       ├── __init__.py
│       ├── adapter.py          # D4: OpenTale 适配器
│       └── manifest.yaml       # 插件声明文件
├── events/
│   ├── __init__.py
│   ├── event_bus.py            # A3: Event Bus 实现
│   ├── event_store.py          # Event 持久化存储
│   └── dead_letter_queue.py    # 死信队列
├── models/
│   ├── __init__.py
│   └── model_client.py         # 模型接入层
└── tests/
    ├── __init__.py
    ├── test_import_rules.py    # AST import 检查
    ├── test_constitution.py    # 宪法规则验证
    └── test_object_model.py    # 核心对象校验
```
