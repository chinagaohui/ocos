"""LEGACY-ISOLATED (U1.3, 2026-08-19): 本插件为旧嵌入路径（验证用途，S7 决议）。
审计判定：生产代码无运行时加载（capability_registry entry_point 仅描述符字符串，无 importlib/load）；
保留不删（历史项目依赖）；禁止新代码引用本模块。扫描豁免：scan_cross_import cross_system。
"""
"""
D4 OpenTale Plugin — 第一个真实 PluginBase 实现。

将 opentale.AutonomousNovelSystem 包装为标准 OCOS Plugin，
通过 PluginLoader (D3) 发现、加载，在 PluginSandbox (D2) 下执行。

架构定位：
  OpenTalePlugin 是 OpenTale 叙事系统在 OCOS Platform 上的适配层。
  它不修改 AutonomousNovelSystem 的任何内部逻辑，仅做接口适配。
  真实系统的集成测试在 Phase E1 E2E 阶段补充。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from ocos.platform.plugin_base import PluginBase
from ocos.platform.plugin_manifest import PluginManifest

logger = logging.getLogger(__name__)

# ── 配置字段常量 ─────────────────────────────────────────────────────────────

_CONFIG_GENRE = "genre"
_CONFIG_OUTPUT_DIR = "output_dir"

_REQUIRED_CONFIG_FIELDS: tuple[str, ...] = (_CONFIG_GENRE, _CONFIG_OUTPUT_DIR)

# ── Action 常量 ──────────────────────────────────────────────────────────────

ACTION_GENERATE = "generate"
ACTION_RESUME = "resume"
ACTION_REWRITE = "rewrite"
ACTION_STATUS = "status"

_SUPPORTED_ACTIONS: tuple[str, ...] = (
    ACTION_GENERATE,
    ACTION_RESUME,
    ACTION_REWRITE,
    ACTION_STATUS,
)


class OpenTalePlugin(PluginBase):
    """OpenTale 插件——将 AutonomousNovelSystem 包装为 PluginBase。

    支持的 Action:
      - generate:  启动新小说生成（params 包含 GenerationRequest 字段）
      - resume:    从检查点续写（params 包含 ResumeRequest 字段）
      - rewrite:   重写指定章节（params 包含 RewriteRequest 字段）
      - status:    返回当前生成状态快照

    配置字段:
      - genre:      必填，小说类型（如 "sci_fi", "romance"）
      - output_dir: 必填，输出目录路径

    on_load 初始化失败回滚：
      如果 AutonomousNovelSystem 初始化成功但后续配置校验失败，
      立即调用 system.close() 释放已分配资源，再抛出异常。
    """

    def __init__(self, manifest: PluginManifest) -> None:
        super().__init__(manifest)
        self._system: Any = None  # AutonomousNovelSystem 实例
        self._config: dict[str, Any] = {}
        self._generation_state: dict[str, Any] = {}

    # ── 生命周期 ──────────────────────────────────────────────────────────────

    def on_load(self, config: dict[str, Any]) -> None:
        """插件初始化。

        流程：
        1. 校验必需配置字段
        2. 初始化 AutonomousNovelSystem（try 块内）
        3. 若步骤2失败且步骤1已部分写状态，回滚清理

        Args:
            config: Sandbox 传入的插件配置

        Raises:
            ValueError: 配置缺失或无效时抛出
            RuntimeError: 系统初始化失败时抛出
        """
        missing = [f for f in _REQUIRED_CONFIG_FIELDS if f not in config]
        if missing:
            raise ValueError(
                f"OpenTalePlugin 缺少必需配置字段: {missing}"
            )

        genre = config[_CONFIG_GENRE]
        output_dir = config[_CONFIG_OUTPUT_DIR]

        if not isinstance(genre, str) or not genre.strip():
            raise ValueError(f"genre 必须是非空字符串，当前值: {genre!r}")

        if not isinstance(output_dir, str) or not output_dir.strip():
            raise ValueError(
                f"output_dir 必须是非空字符串，当前值: {output_dir!r}"
            )

        self._config = dict(config)

        # 初始化真实系统
        try:
            self._init_system(genre, output_dir)
        except Exception:
            # 回滚：确保任何已分配资源被清理
            self._cleanup_system()
            raise

        logger.info(
            "OpenTalePlugin 已加载 — genre=%s, output_dir=%s",
            genre,
            output_dir,
        )

    def execute(self, action: str, params: dict[str, Any]) -> Any:
        """插件核心执行逻辑。

        Args:
            action: 动作名称（generate / resume / rewrite / status）
            params: 动作参数字典

        Returns:
            执行结果（字典，包含 operation / status / result 等字段）

        Raises:
            ValueError: 不支持的 action
            RuntimeError: 系统未初始化
        """
        if self._system is None:
            raise RuntimeError(
                "OpenTalePlugin 未初始化——请先调用 on_load"
            )

        if action not in _SUPPORTED_ACTIONS:
            raise ValueError(
                f"不支持的 action: '{action}'。"
                f" 支持: {_SUPPORTED_ACTIONS}"
            )

        action_dispatch = {
            ACTION_GENERATE: self._do_generate,
            ACTION_RESUME: self._do_resume,
            ACTION_REWRITE: self._do_rewrite,
            ACTION_STATUS: self._do_status,
        }

        handler = action_dispatch[action]
        return handler(params)

    def on_unload(self) -> None:
        """插件卸载清理。"""
        self._cleanup_system()
        self._config.clear()
        self._generation_state.clear()
        logger.info("OpenTalePlugin 已卸载")

    # ── 内部方法 ──────────────────────────────────────────────────────────────

    def _init_system(self, genre: str, output_dir: str) -> None:
        """初始化 AutonomousNovelSystem。

        提取为单独方法，便于子类重写或测试替换。
        """
        # 延迟导入，避免在测试环境加载真实 LLM 依赖
        from opentale.app.service import AutonomousNovelSystem
        from opentale.app.runtime import build_runtime

        runtime = build_runtime()
        self._system = AutonomousNovelSystem(runtime=runtime)

        output_path = Path(output_dir)
        if not output_path.exists():
            output_path.mkdir(parents=True, exist_ok=True)

        self._generation_state = {
            "genre": genre,
            "output_dir": output_dir,
            "status": "idle",
            "current_operation": None,
            "progress": {},
        }

    def _cleanup_system(self) -> None:
        """清理系统资源，安全地关闭 AutonomousNovelSystem。"""
        if self._system is not None:
            try:
                import asyncio

                try:
                    loop = asyncio.get_running_loop()
                    if loop.is_running():
                        loop.create_task(self._system.close())
                    else:
                        asyncio.run(self._system.close())
                except RuntimeError:
                    # 无 running loop 时
                    asyncio.run(self._system.close())
            except Exception as e:
                logger.warning("关闭 AutonomousNovelSystem 时出错: %s", e)
            finally:
                self._system = None

    def _do_generate(self, params: dict[str, Any]) -> dict[str, Any]:
        """处理 generate action。

        将 params 映射为 GenerationRequest 字段字典。
        """
        from opentale.app.models import GenerationRequest

        content = params.get(
            "content", self._config.get("default_content", "Write a story about ")
        )
        request = GenerationRequest(
            content=content,
            genre=self._config[_CONFIG_GENRE],
            title=params.get("title"),
            chapters=params.get("chapters", 12),
            target_words=params.get("target_words", 36000),
            language=params.get("language", "zh"),
            style=params.get("style", "commercial"),
            constraints=params.get("constraints", []),
            skeleton_only=params.get("skeleton_only", False),
        )

        output_dir = self._config[_CONFIG_OUTPUT_DIR]
        self._generation_state["status"] = "generating"
        self._generation_state["current_operation"] = "generate"

        # 同步包装异步调用
        result = self._run_async(self._system.generate, request)

        self._generation_state["status"] = "completed"
        self._generation_state["progress"] = {"output_dir": output_dir}

        return {
            "operation": "generate",
            "status": "completed",
            "output_dir": output_dir,
            "result": result,
        }

    def _do_resume(self, params: dict[str, Any]) -> dict[str, Any]:
        """处理 resume action。"""
        from opentale.app.routes.generation import ResumeRequest

        if "project_dir" not in params:
            raise ValueError("resume action 需要 'project_dir' 参数")

        request = ResumeRequest(project_dir=params["project_dir"])

        self._generation_state["status"] = "resuming"
        self._generation_state["current_operation"] = "resume"

        result = self._run_async(self._system.resume, params["project_dir"])

        self._generation_state["status"] = "completed"
        self._generation_state["progress"] = {
            "project_dir": params["project_dir"]
        }

        return {
            "operation": "resume",
            "status": "completed",
            "project_dir": params["project_dir"],
            "result": result,
        }

    def _do_rewrite(self, params: dict[str, Any]) -> dict[str, Any]:
        """处理 rewrite action。"""
        from opentale.app.models import RewriteRequest

        if "project_dir" not in params:
            raise ValueError("rewrite action 需要 'project_dir' 参数")
        if "chapter_number" not in params:
            raise ValueError("rewrite action 需要 'chapter_number' 参数")

        request = RewriteRequest(
            project_dir=params["project_dir"],
            chapter_number=params["chapter_number"],
            instruction=params.get("instruction", ""),
        )

        self._generation_state["status"] = "rewriting"
        self._generation_state["current_operation"] = "rewrite"

        result = self._run_async(self._system.rewrite_chapter, request)

        self._generation_state["status"] = "completed"

        return {
            "operation": "rewrite",
            "status": "completed",
            "chapter_number": params["chapter_number"],
            "result": result,
        }

    def _do_status(self, params: dict[str, Any]) -> dict[str, Any]:
        """处理 status action。"""
        _ = params  # status 不需要额外参数
        return {
            "operation": "status",
            "status": self._generation_state.get("status", "unknown"),
            "genre": self._config.get(_CONFIG_GENRE, ""),
            "output_dir": self._config.get(_CONFIG_OUTPUT_DIR, ""),
            "current_operation": self._generation_state.get(
                "current_operation"
            ),
            "progress": self._generation_state.get("progress", {}),
        }

    @staticmethod
    def _run_async(coro_factory: Any, *args: Any) -> Any:
        """同步包装异步调用。

        在同步的 execute() 上下文中执行异步方法。
        也支持普通同步 callable（测试 mock 场景）。
        """
        result = coro_factory(*args)

        import asyncio

        if asyncio.iscoroutine(result):
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    return asyncio.run_coroutine_threadsafe(
                        result, loop
                    ).result()
            except RuntimeError:
                pass
            return asyncio.run(result)

        return result  # 同步 callable，直接返回
