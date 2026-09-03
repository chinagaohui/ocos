"""agent_proxy — OCOS 调用其它智能体的代理层。

设计目标:
    1. OCOS 可以调用其它智能体（CodeAgent, ResearchAgent 等）
    2. OCOS 可以修改其它智能体的配置和能力定义
    3. 统一的调用接口和结果处理

ABI:
    agent_proxy.invoke(agent_name, action, **kwargs) -> dict
    agent_proxy.update_agent(agent_name, config) -> dict
    agent_proxy.list_agents() -> list[dict]
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AgentInstance:
    """已实例化的智能体档案。"""

    name: str
    class_name: str
    module_path: str
    instance: Any = None
    config: dict[str, Any] = field(default_factory=dict)
    state: str = "registered"  # registered | ready | busy | error

    @property
    def is_ready(self) -> bool:
        return self.state == "ready" and self.instance is not None


class AgentRegistry:
    """智能体注册中心。

    功能:
        - register_agent: 注册新智能体类（静态注册）
        - instantiate_agent: 实例化并缓存
        - get_agent: 获取实例
        - update_agent_config: 修改智能体配置
        - call_agent: 统一调用接口
    """

    # ── 内置智能体映射 ──
    _builtin_agents: dict[str, dict[str, Any]] = {
        "code": {
            "class_name": "CodeAgent",
            "module": "ocos.capability.agents.code_agent",
            "description": "本地代码沙箱执行",
            "capabilities": ["execute", "analyze", "lint"],
        },
        "research": {
            "class_name": "ResearchAgent",
            "module": "ocos.capability.agents.research_agent",
            "description": "研究分析代理",
            "capabilities": ["research", "summarize", "analyze"],
        },
        "planner": {
            "class_name": "PlannerAgent",
            "module": "ocos.capability.agents.planner_agent",
            "description": "任务规划代理",
            "capabilities": ["plan", "decompose", "schedule"],
        },
        "selfmod": {
            "class_name": "SelfModificationAgent",
            "module": "ocos.capability.agents.self_modification_agent",
            "description": "OCOS 自我修改代理",
            "capabilities": ["execute", "validate", "preview"],
        },
        "summarizer": {
            "class_name": "SummarizerAgent",
            "module": "ocos.capability.agents.summarizer_agent",
            "description": "文本摘要代理",
            "capabilities": ["summarize", "extract", "condense"],
        },
    }

    def __init__(self, project_root: str | None = None) -> None:
        self._project_root = Path(project_root or "/home/laogao/Documents/trae_projects/ocos")
        self._instances: dict[str, AgentInstance] = {}
        self._init_builtin()

    def _init_builtin(self) -> None:
        """初始化内置智能体（注册但不实例化）。"""
        for name, info in self._builtin_agents.items():
            instance = AgentInstance(
                name=name,
                class_name=info["class_name"],
                module_path=info["module"],
                config={"description": info["description"]},
                state="registered",
            )
            self._instances[name] = instance

    # ── 智能体调用 ──

    def invoke(self, agent_name: str, action: str, **kwargs: Any) -> dict[str, Any]:
        """调用指定智能体的能力。

        Args:
            agent_name: 智能体名称（code, research, planner 等）
            action:     操作名称（execute, analyze 等）
            **kwargs:   传递给智能体的参数

        Returns:
            {
                "success": bool,
                "agent": str,
                "action": str,
                "output": Any,
                "latency_ms": float,
            }
        """
        import time
        start = time.time()

        # 获取或实例化智能体
        agent_inst = self._get_or_instantiate(agent_name)
        if agent_inst is None:
            return {
                "success": False,
                "error": f"Agent not found: {agent_name}",
                "agent": agent_name,
                "action": action,
            }

        # 执行调用
        try:
            agent_inst.state = "busy"
            result = agent_inst.instance.execute(**kwargs)
            agent_inst.state = "ready"

            latency = (time.time() - start) * 1000
            return {
                "success": True,
                "agent": agent_name,
                "action": action,
                "output": result.get("output", result),
                "latency_ms": round(latency, 2),
            }
        except Exception as e:
            agent_inst.state = "error"
            return {
                "success": False,
                "error": str(e),
                "agent": agent_name,
                "action": action,
            }

    def _get_or_instantiate(self, agent_name: str) -> AgentInstance | None:
        """获取或实例化智能体。"""
        inst = self._instances.get(agent_name)
        if inst is None:
            return None

        if inst.instance is None:
            try:
                inst.instance = self._load_and_create(agent_name, inst)
                inst.state = "ready"
            except Exception as e:
                inst.state = "error"
                return None

        return inst

    def _load_and_create(self, name: str, inst: AgentInstance) -> Any:
        """动态加载并创建智能体实例。"""
        import importlib
        import inspect

        module = importlib.import_module(inst.module_path)
        cls = getattr(module, inst.class_name)

        # 过滤无效的配置参数（只传 __init__ 接受的参数）
        sig = inspect.signature(cls.__init__)
        valid_params = set(sig.parameters.keys()) - {"self", "args", "kwargs"}
        # 移除 description（元数据，非构造参数）
        valid_params.discard("description")

        filtered_config = {
            k: v for k, v in inst.config.items()
            if k in valid_params or k == "description"
        }
        # description 不是构造参数，移除它
        filtered_config.pop("description", None)

        return cls(**filtered_config)

    # ── 智能体配置修改 ──

    def update_agent_config(
        self, agent_name: str, config_updates: dict[str, Any]
    ) -> dict[str, Any]:
        """修改智能体配置（影响后续实例化）。"""
        inst = self._instances.get(agent_name)
        if inst is None:
            return {"success": False, "error": f"Agent not found: {agent_name}"}

        # 阻止强制重置实例化状态
        old_instance = inst.instance
        inst.instance = None
        inst.config.update(config_updates)

        return {
            "success": True,
            "message": f"Agent {agent_name} config updated",
            "new_config": dict(inst.config),
            "will_reinstantiate": True,
        }

    def update_agent_capability(
        self, agent_name: str, cap_name: str, cap_config: dict[str, Any]
    ) -> dict[str, Any]:
        """更新智能体的能力定义。"""
        # 此处仅为元数据记录；实际执行逻辑由 Agent 自身处理
        inst = self._instances.get(agent_name)
        if inst is None:
            return {"success": False, "error": f"Agent not found: {agent_name}"}

        existing = inst.config.get("capabilities", {})
        existing[cap_name] = cap_config
        inst.config["capabilities"] = existing

        # 重置以生效
        inst.instance = None
        return {
            "success": True,
            "message": f"Capability '{cap_name}' updated on agent '{agent_name}'",
            "capability": cap_config,
        }

    def list_agents(self) -> list[dict[str, Any]]:
        """列出所有已注册智能体。"""
        result = []
        for name, inst in self._instances.items():
            result.append({
                "name": name,
                "class": inst.class_name,
                "state": inst.state,
                "config": dict(inst.config),
                "builtin": name in self._builtin_agents,
            })
        return result

    def get_agent_info(self, agent_name: str) -> dict[str, Any] | None:
        """获取智能体详细信息。"""
        inst = self._instances.get(agent_name)
        if inst is None:
            return None

        builtin_info = self._builtin_agents.get(agent_name, {})
        return {
            "name": inst.name,
            "class": inst.class_name,
            "module": inst.module_path,
            "state": inst.state,
            "config": dict(inst.config),
            "builtin_capabilities": builtin_info.get("capabilities", []),
            "description": builtin_info.get("description", ""),
            "builtin": agent_name in self._builtin_agents,
        }


# ── 便捷函数 ──

_registry: AgentRegistry | None = None


def get_registry() -> AgentRegistry:
    """获取全局智能体注册表（单例）。"""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


def call_agent(agent_name: str, action: str, **kwargs: Any) -> dict[str, Any]:
    """便捷调用函数。"""
    return get_registry().invoke(agent_name, action, **kwargs)


def list_all_agents() -> list[dict[str, Any]]:
    """列出所有智能体。"""
    return get_registry().list_agents()
