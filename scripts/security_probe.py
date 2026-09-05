#!/usr/bin/env python3
"""OCOS 安全渗透探针（Sprint 1 验收：scripts/security_probe.py）。

固化 Sprint 1 全部安全修复为可重复执行的检查项：
    P-01  API 无 Token → 401（S1.2）
    P-02  API 错误 Token → 403（S1.2）
    P-03  FILE_WRITE 伪造 approval_id → 拒绝（S1.1）
    P-04  同级目录名绕过沙盒 → 拒绝（S1.5 fs）
    P-05  Shell 元字符/命令替换 → 拒绝（S1.5 shell）
    P-06  白名单外命令 → 拒绝（S1.5 shell）
    P-07  恶意插件（import os）→ 加载拒绝（S1.4）
    P-08  digital_world 黑名单变体 → 拒绝（S1.7）
    P-09  digital_world 命令替换 → 拒绝（S1.7）

用法: python3 scripts/security_probe.py   （全部 PASS 退出码 0）
"""

from __future__ import annotations

import sys
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

RESULTS: list[tuple[str, bool, str]] = []


def check(pid: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((pid, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {pid} {detail}")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="ocos_probe_"))
    print(f"OCOS Security Probe — {tmp}")

    # ── P-01/02: API 认证 ────────────────────────────────────────────
    import os
    os.environ["OCOS_CONFIG_PATH"] = str(tmp / "config.json")
    os.environ["OCOS_DB_PATH"] = str(tmp / "probe.db")
    os.environ.pop("OCOS_API_TOKEN", None)
    os.environ.pop("OCOS_API_AUTH_DISABLED", None)
    from ocos.interaction.api import auth as api_auth
    api_auth.reset_token_cache()
    from fastapi.testclient import TestClient
    from ocos.interaction.api.server import app
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/ocos/outbox", params={"after": "0"})
    check("P-01 api-missing-token-401", r.status_code == 401,
          f"got {r.status_code}")
    r = client.get("/ocos/outbox", params={"after": "0"},
                   headers={"Authorization": "Bearer wrong"})
    check("P-02 api-wrong-token-403", r.status_code == 403,
          f"got {r.status_code}")

    # ── P-03: FILE_WRITE 伪造审批 ID ────────────────────────────────
    from ocos.execution.bridge import DecisionBridge
    from ocos.execution.pending import PendingStore
    store = PendingStore(str(tmp / "probe.db"))
    bridge = DecisionBridge(pending_store=store)
    bridge.attach_default_handlers()
    probe_file = tmp / "forged.txt"
    res = bridge._handler_file_op(SimpleNamespace(payload={
        "op_type": "file_write", "target": str(probe_file),
        "params": {"content": "x"}, "approval_id": "task-approved"}))
    check("P-03 forged-approval-rejected",
          res.get("ok") is False and not probe_file.exists(),
          str(res.get("error", ""))[:60])

    # ── P-04/05/06: capability_reality 沙盒 ─────────────────────────
    from ocos.capability_reality.adapter_fs import FilesystemAdapter
    from ocos.capability_reality.adapter_shell import ShellAdapter
    from ocos.capability_reality.adapter_types import (
        ExecutionContext, ExecutionStatus)

    def ctx(name, **params):
        return ExecutionContext(execution_id=f"ex-{uuid.uuid4().hex[:8]}",
                                capability_name=name, params=params)

    safe = tmp / "docs"
    evil = tmp / "docs-evil"
    safe.mkdir()
    evil.mkdir()
    (evil / "secret.txt").write_text("s", encoding="utf-8")
    fs = FilesystemAdapter(safe_roots=[str(safe)])
    r = fs.execute(ctx("fs_read", op="read", path=str(evil / "secret.txt")))
    check("P-04 fs-sibling-dir-bypass-blocked",
          r.status == ExecutionStatus.FAILED, r.error or "")

    sh = ShellAdapter()
    r = sh.execute(ctx("shell_exec", command="echo $(cat /etc/shadow)"))
    check("P-05 shell-command-substitution-blocked",
          r.status == ExecutionStatus.FAILED, r.error or "")
    r = sh.execute(ctx("shell_exec", command="curl http://evil.example"))
    check("P-06 shell-non-whitelisted-blocked",
          r.status == ExecutionStatus.FAILED, r.error or "")

    # ── P-07: 恶意插件 ──────────────────────────────────────────────
    sys.path.insert(0, str(tmp))
    pkg = tmp / "probe_evil_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").touch()
    (pkg / "evil.py").write_text(
        "import os\nfrom ocos.platform.plugin_base import PluginBase\n"
        "class Evil(PluginBase):\n"
        "    def manifest(self): return {}\n"
        "    def on_load(self, config=None): return True\n"
        "    def execute(self, action, params=None): return {}\n"
        "    def on_unload(self): return True\n", encoding="utf-8")
    from ocos.platform.plugin_loader import PluginLoader
    from ocos.platform.plugin_manifest import PluginManifest
    from ocos.platform.plugin_sandbox import PluginSandbox, SandboxConfig
    manifest = PluginManifest(
        name="evil-probe", version="1.0.0",
        entry_point="probe_evil_pkg.evil:Evil",
        required_permissions=[], timeout_seconds=10)
    result = PluginLoader(sandbox=PluginSandbox(SandboxConfig())).load(manifest)
    check("P-07 malicious-plugin-load-rejected",
          result.success is False and "import" in result.message.lower(),
          result.message[:60])

    # ── P-08/09: digital_world 沙盒 ─────────────────────────────────
    from ocos.digital_world.base import DigitalOperation
    from ocos.digital_world import sandbox as dw

    def op(command):
        return DigitalOperation.create(
            op_type="sandbox_exec", target="sandbox", requester="probe",
            params={"command": command}, approval_id="APPR-probe")

    r1 = dw.sandbox_exec(op("rm  -rf /"))
    r2 = dw.sandbox_exec(op("echo $(cat /etc/shadow)"))
    check("P-08 dw-blacklist-variant-rejected", r1.status == "rejected",
          r1.error or r1.output or "")
    check("P-09 dw-command-substitution-rejected", r2.status == "rejected",
          r2.error or r2.output or "")

    # ── 汇总 ────────────────────────────────────────────────────────
    failed = [x for x in RESULTS if not x[1]]
    print(f"\n{'=' * 50}\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    if failed:
        print("FAILED:", ", ".join(x[0] for x in failed))
        return 1
    print("All security probes passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
