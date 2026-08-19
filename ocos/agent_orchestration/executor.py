"""Phase 28 — AgentExecutor: 真实 Agent 子进程执行器。

用法:
    executor = AgentExecutor(agent_scripts_dir="./agents")
    success, output, error = executor.execute(contract)
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from ocos.agent_orchestration.contract import ExecutionContract


# ── AgentExecutor ──────────────────────────────────────────────────────────


@dataclass
class AgentExecutor:
    """Agent 子进程执行器。

    将 ExecutionContract 序列化为 JSON → 传递给 Agent 脚本 stdin
    → 捕获 stdout/stderr → 解析结果。

    宪法约束:
        - Agent 只执行不决策，输出必须符合 contract.output_spec
        - 超时严格按 contract.timeout_seconds
        - 失败不带状态，由 Supervisor 处理重试/降级
    """

    agent_scripts_dir: str = "./agents"
    _agent_map: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        # 默认 Agent 脚本映射: agent_id → script_name pattern
        if not self._agent_map:
            self._agent_map = {
                "writer": "agent_writer.py",
                "researcher": "agent_researcher.py",
                "reviewer": "agent_reviewer.py",
                "data_processor": "agent_data_processor.py",
            }

    def execute(self, contract: ExecutionContract) -> tuple[bool, str, str | None]:
        """执行单个 Agent 任务。

        Args:
            contract: 执行契约

        Returns:
            (success, stdout_output, error_message_or_None)
        """
        script_name = self._agent_map.get(contract.agent_id)
        if script_name is None:
            # 尝试通用 agent_id → script 解析
            script_name = f"agent_{contract.agent_id}.py"

        script_path = Path(self.agent_scripts_dir) / script_name

        if not script_path.exists():
            return (
                False,
                "",
                f"Agent script not found: {script_path} "
                f"(agent_id={contract.agent_id})",
            )

        # 构建输入 payload
        payload = {
            "contract_id": contract.contract_id,
            "task_id": contract.task_id,
            "agent_id": contract.agent_id,
            "input_spec": contract.input_spec,
            "output_spec": contract.output_spec,
        }

        # 写入临时文件（避免 shell 注入）
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix="agent_input_"
        ) as f:
            json.dump(payload, f, ensure_ascii=False)
            input_path = f.name

        try:
            result = subprocess.run(
                ["python3", str(script_path), "--input", input_path],
                capture_output=True,
                text=True,
                timeout=contract.timeout_seconds,
                cwd=self.agent_scripts_dir,
            )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            if result.returncode == 0:
                return True, stdout, None
            else:
                error = stderr or stdout or f"Agent exited with code {result.returncode}"
                return False, stdout, error

        except subprocess.TimeoutExpired as e:
            return (
                False,
                "",
                f"Agent timed out after {contract.timeout_seconds}s: {e}",
            )
        except FileNotFoundError:
            return (
                False,
                "",
                f"python3 not found — cannot execute agent script {script_path}",
            )
        except Exception as e:
            return False, "", f"Agent execution error: {type(e).__name__}: {e}"
        finally:
            # 清理临时文件
            try:
                Path(input_path).unlink(missing_ok=True)
            except OSError:
                pass

    def register_agent(self, agent_id: str, script_name: str) -> None:
        """注册 Agent 脚本映射。

        Args:
            agent_id: Agent 标识（对应 Registry 中的 agent_id）
            script_name: Python 脚本文件名（相对于 agent_scripts_dir）
        """
        self._agent_map[agent_id] = script_name

    def unregister_agent(self, agent_id: str) -> None:
        """注销 Agent 脚本映射。"""
        self._agent_map.pop(agent_id, None)
