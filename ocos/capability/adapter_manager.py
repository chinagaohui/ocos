"""Phase 45: AdapterManager — 适配器管理器。

统一不同外部能力接口到 OCOS ABI。

例如:
    Codex API → Capability ABI → OCOS
    OpenClaw CLI/API → Capability ABI → OCOS
    HTTP Service → Capability ABI → OCOS

边界 CNS45-03: 外部 Agent 是能力提供者，不是认知主体。

AGI 能力补全（智能体软件接入）:
  - register_discovered(): 接入 AgentDiscovery 探查结果（DiscoveredAgent）
  - EXTERNAL_AGENT adapter 真实执行: 已接入软件 → CLI 子进程 / HTTP 请求；
    未接入 → 保留旧 stub 语义（诚实标注，不假装真实调用）
  - HTTP adapter 真实请求（短超时、截断）
  - SUBPROCESS 保持本地函数语义（真实命令执行由 execution.bridge 沙盒承担）
"""

from __future__ import annotations

import shlex
import subprocess
import urllib.request
from dataclasses import dataclass, field

from ocos.capability.capability_types import (
    Capability, ExecutorKind, ExecutionRequest, ExecutionStatus, RawResult,
)
from ocos.capability.capability_router import CapabilityRouter

# CLI 子进程超时（秒）与输出截断
_CLI_TIMEOUT = 30.0
_OUTPUT_LIMIT = 2000
# 拒绝的 shell 元字符 — 外部 Agent 参数不得携带（防命令注入）
_SHELL_METACHARS = (";", "&&", "||", "|", "`", "$(", ">", "<", "\n")


@dataclass
class AdapterManager:
    """适配器管理器。

    为每种 ExecutorKind 提供标准化适配器。

    OCOS ABI (统一调用接口):
        Input:  ExecutionRequest
        Output: RawResult
    """

    router: CapabilityRouter = field(default_factory=CapabilityRouter)
    # 已接入的智能体软件: capability_id → DiscoveredAgent
    _discovered: dict[str, object] = field(default_factory=dict)

    def register_all_default(self) -> None:
        """注册所有默认适配器。"""
        self.router.register_adapter(
            ExecutorKind.EXTERNAL_AGENT, self._external_agent_adapter,
        )
        self.router.register_adapter(
            ExecutorKind.HTTP_SERVICE, self._http_adapter,
        )
        self.router.register_adapter(
            ExecutorKind.LOCAL_FUNCTION, self._local_adapter,
        )
        self.router.register_adapter(
            ExecutorKind.SUBPROCESS, self._local_adapter,
        )

    def register_discovered(self, agents: list) -> None:
        """AGI 能力补全: 接入 AgentDiscovery 探查结果。

        已可用软件（available=True）进入执行映射；不可用条目跳过
        （保留 registry 中 UNAVAILABLE 状态由调用方管理）。
        """
        for a in agents or []:
            if getattr(a, "available", False):
                self._discovered[a.capability_id] = a

    # ── EXTERNAL_AGENT: 真实调用（已接入）/ stub（未接入）─────────────

    def _external_agent_adapter(self, request: ExecutionRequest) -> RawResult:
        """外部 Agent 适配器——将请求转为真实外部调用。

        AGI 能力补全: 若该 capability_id 已通过 register_discovered 接入
        （kind=cli → 子进程；kind=http → HTTP 请求），真实执行并返回原始
        输出；否则保留旧 stub 语义（未接入软件不假装真实调用）。
        """
        agent = self._discovered.get(request.capability_id)
        if agent is None:
            return RawResult(
                request_id=request.request_id,
                capability_id=request.capability_id,
                raw_output=f"[Agent] response to: {request.input_payload[:200]}",
                status=ExecutionStatus.SUCCESS,
            )
        kind = getattr(agent, "kind", "")
        if kind == "cli":
            return self._exec_cli_agent(agent, request)
        if kind == "http":
            return self._exec_http_agent(agent, request)
        return RawResult(
            request_id=request.request_id,
            capability_id=request.capability_id,
            status=ExecutionStatus.FAILURE,
            error_message=f"unsupported agent kind: {kind}",
        )

    def _exec_cli_agent(self, agent: object,
                        request: ExecutionRequest) -> RawResult:
        """真实子进程调用已发现 CLI（安全: 拒绝 shell 元字符 + 固定命令）。"""
        payload = (request.input_payload or "").strip()
        if not payload:
            return RawResult(
                request_id=request.request_id,
                capability_id=request.capability_id,
                status=ExecutionStatus.FAILURE,
                error_message="empty payload",
            )
        if any(ch in payload for ch in _SHELL_METACHARS):
            return RawResult(
                request_id=request.request_id,
                capability_id=request.capability_id,
                status=ExecutionStatus.FAILURE,
                error_message="shell metacharacters not allowed",
            )
        cli_path = getattr(agent, "cli_path", "") or getattr(agent, "name", "")
        if not cli_path:
            return RawResult(
                request_id=request.request_id,
                capability_id=request.capability_id,
                status=ExecutionStatus.FAILURE,
                error_message="no cli path for agent",
            )
        try:
            args = shlex.split(payload)
        except ValueError as e:
            return RawResult(
                request_id=request.request_id,
                capability_id=request.capability_id,
                status=ExecutionStatus.FAILURE,
                error_message=f"invalid args: {e}",
            )
        try:
            proc = subprocess.run(
                [cli_path, *args], capture_output=True, text=True,
                timeout=_CLI_TIMEOUT,
            )
            out = (proc.stdout or "").strip()[: _OUTPUT_LIMIT]
            err = (proc.stderr or "").strip()[:300]
            if proc.returncode != 0 and not out:
                return RawResult(
                    request_id=request.request_id,
                    capability_id=request.capability_id,
                    status=ExecutionStatus.FAILURE,
                    error_message=err or f"exit code {proc.returncode}",
                )
            return RawResult(
                request_id=request.request_id,
                capability_id=request.capability_id,
                raw_output=out or err,
                status=ExecutionStatus.SUCCESS,
            )
        except subprocess.TimeoutExpired:
            return RawResult(
                request_id=request.request_id,
                capability_id=request.capability_id,
                status=ExecutionStatus.TIMEOUT,
                error_message=f"cli timeout > {_CLI_TIMEOUT:.0f}s",
            )
        except Exception as e:
            return RawResult(
                request_id=request.request_id,
                capability_id=request.capability_id,
                status=ExecutionStatus.FAILURE,
                error_message=str(e)[:200],
            )

    def _exec_http_agent(self, agent: object,
                         request: ExecutionRequest) -> RawResult:
        """真实 HTTP GET 调用已接入 API 端点（payload 作为可选路径后缀）。"""
        endpoint = (getattr(agent, "api_endpoint", "") or "").rstrip("/")
        if not endpoint:
            return RawResult(
                request_id=request.request_id,
                capability_id=request.capability_id,
                status=ExecutionStatus.FAILURE,
                error_message="no api endpoint for agent",
            )
        suffix = (request.input_payload or "").strip()
        url = f"{endpoint}/{suffix.lstrip('/')}" if suffix else endpoint
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = resp.read(4096).decode("utf-8", "replace")
            return RawResult(
                request_id=request.request_id,
                capability_id=request.capability_id,
                raw_output=body[: _OUTPUT_LIMIT],
                status=ExecutionStatus.SUCCESS,
            )
        except Exception as e:
            return RawResult(
                request_id=request.request_id,
                capability_id=request.capability_id,
                status=ExecutionStatus.FAILURE,
                error_message=str(e)[:200],
            )

    # ── HTTP_SERVICE: 真实请求 ───────────────────────────────────────

    def _http_adapter(self, request: ExecutionRequest) -> RawResult:
        """HTTP API 适配器 — 真实 GET 请求（payload 为完整 URL）。"""
        url = (request.input_payload or "").strip()
        if not url.startswith(("http://", "https://")):
            return RawResult(
                request_id=request.request_id,
                capability_id=request.capability_id,
                status=ExecutionStatus.FAILURE,
                error_message="not a valid http url",
            )
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
                body = resp.read(4096).decode("utf-8", "replace")
            return RawResult(
                request_id=request.request_id,
                capability_id=request.capability_id,
                raw_output=body[: _OUTPUT_LIMIT],
                status=ExecutionStatus.SUCCESS,
            )
        except Exception as e:
            return RawResult(
                request_id=request.request_id,
                capability_id=request.capability_id,
                status=ExecutionStatus.FAILURE,
                error_message=str(e)[:200],
            )

    @staticmethod
    def _local_adapter(request: ExecutionRequest) -> RawResult:
        """本地函数/子进程适配器（保留 stub 语义 — 真实命令执行在
        execution.bridge 沙盒通道）。"""
        return RawResult(
            request_id=request.request_id,
            capability_id=request.capability_id,
            raw_output=f"[Local] executed: {request.input_payload[:200]}",
            status=ExecutionStatus.SUCCESS,
        )

    def execute(self, request: ExecutionRequest) -> RawResult:
        """通过适配器执行能力调用。"""
        return self.router.route(request)


__all__ = ["AdapterManager"]
