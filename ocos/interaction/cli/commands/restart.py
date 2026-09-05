"""OCOS CLI — restart 命令（整合重启 OCOS 系统 + 网关，含操作日志）。

组件与重启顺序（固定）:
    server  → ocos-server.service   （API/TUI 交互入口, 端口 8900）
    daemon  → ocos-daemon.service   （认知 daemon）
    gateway → hermes-gateway.service（消息平台网关, 最后重启以重连新 API）

环境语义（--env）:
    dev   : 默认重启 server + daemon（网关不默认动, 避免打断外部消息集成）
    test  : server + daemon + gateway
    prod  : server + daemon + gateway
    --only <name> 可显式覆盖默认组件集。

操作日志: ~/.ocos/ops/restart.log （JSONL — 时间/执行人/环境/各组件结果）
"""

from __future__ import annotations

import getpass
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from ocos.interaction.base import InteractionSession

# 组件 → systemd --user 单元（顺序即重启顺序）
COMPONENT_UNITS = [
    ("server", "ocos-server.service"),
    ("daemon", "ocos-daemon.service"),
    ("gateway", "hermes-gateway.service"),
]

ENV_DEFAULTS = {
    "dev": ["server", "daemon"],
    "test": ["server", "daemon", "gateway"],
    "prod": ["server", "daemon", "gateway"],
}

SERVER_PORT = int(os.environ.get("OCOS_API_PORT", "8900"))
ACTIVATE_TIMEOUT = 15.0   # 单元 is-active 等待秒数
PORT_TIMEOUT = 15.0       # server 端口就绪等待秒数

LOG_PATH = Path.home() / ".ocos" / "ops" / "restart.log"

_UNIT_HINT = (
    "提示: 单元文件应位于 ~/.config/systemd/user/；"
    "安装后需执行 systemctl --user daemon-reload"
)


# ── systemd 底层封装 ────────────────────────────────────────────

def _systemctl(*args: str) -> tuple[int, str]:
    """执行 systemctl --user，返回 (returncode, 合并输出)。"""
    try:
        proc = subprocess.run(
            ["systemctl", "--user", *args],
            capture_output=True, text=True, timeout=30,
        )
        return proc.returncode, (proc.stdout + proc.stderr).strip()
    except FileNotFoundError:
        return 127, "systemctl 不可用: 未找到 systemd（当前环境非 Linux 桌面会话?）"
    except subprocess.TimeoutExpired:
        return 124, f"systemctl {' '.join(args)} 超时(30s)"


def _unit_exists(unit: str) -> tuple[bool, str]:
    code, out = _systemctl("cat", unit)
    return code == 0, out


def _wait_active(unit: str, timeout: float) -> tuple[bool, str]:
    """轮询等待单元 active，返回 (是否成功, 最后状态)。"""
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        code, last = _systemctl("is-active", unit)
        if code == 0 and last == "active":
            return True, "active"
        time.sleep(0.5)
    return False, last or "unknown"


def _port_ready(port: int, timeout: float) -> bool:
    """轮询 TCP 端口就绪。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.5)
    return False


# ── 日志 ────────────────────────────────────────────────────────

def _append_log(entry: dict) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:   # 日志失败不阻断主流程
        print(f"[warn] 操作日志写入失败: {exc}", file=sys.stderr)


# ── 核心重启流程 ────────────────────────────────────────────────

def _resolve_components(env: str, only: list[str] | None) -> tuple[list[str], str | None]:
    """解析要重启的组件（保持固定顺序）。返回 (组件列表, 错误信息)。"""
    names = [n for n, _ in COMPONENT_UNITS]
    if only:
        bad = [c for c in only if c not in names]
        if bad:
            return [], f"未知组件: {', '.join(bad)}（可选: {', '.join(names)}）"
        selected = [n for n in names if n in only]
    else:
        if env not in ENV_DEFAULTS:
            return [], f"未知环境: {env}（可选: dev / test / prod）"
        selected = [n for n in names if n in ENV_DEFAULTS[env]]
    return selected, None


def _do_restart(components: list[str], env: str) -> int:
    """对给定组件执行重启 + 健康验证 + 日志。返回退出码。"""
    user = getpass.getuser()
    started = time.monotonic()
    results: dict[str, dict] = {}

    # 前置检查: systemctl 可用 + 单元存在
    code, out = _systemctl("is-system-running")
    if code not in (0, 1) and "degraded" not in out:   # degraded 仍可操作
        print(f"[error] systemctl --user 不可用: {out or 'systemd user 会话未运行'}")
        return 1

    for name in components:
        unit = dict(COMPONENT_UNITS)[name]
        exists, hint_out = _unit_exists(unit)
        if not exists:
            results[name] = {"ok": False, "unit": unit,
                             "error": f"单元不存在: {unit}。{_UNIT_HINT}"}
            continue

        rcode, rerr = _systemctl("restart", unit)
        if rcode != 0:
            results[name] = {"ok": False, "error": f"restart 失败(rc={rcode}): {rerr}"}
            continue

        active, state = _wait_active(unit, ACTIVATE_TIMEOUT)
        detail: dict = {"unit": unit, "state": state}
        if not active:
            detail["ok"] = False
            detail["error"] = f"重启后 {ACTIVATE_TIMEOUT:.0f}s 内未进入 active（最后状态: {state}）—— 查看日志: journalctl --user -u {unit} -n 50"
            results[name] = detail
            continue

        # server 额外验证端口就绪
        if name == "server":
            if not _port_ready(SERVER_PORT, PORT_TIMEOUT):
                detail["ok"] = False
                detail["error"] = (
                    f"单元已 active 但端口 {SERVER_PORT} {PORT_TIMEOUT:.0f}s 内未就绪 "
                    "—— 端口被占用或启动期异常, 请检查 journalctl --user -u ocos-server.service"
                )
                results[name] = detail
                continue
            detail["port"] = SERVER_PORT
        detail["ok"] = True
        results[name] = detail

    all_ok = all(r.get("ok") for r in results.values()) and bool(results)
    duration_ms = int((time.monotonic() - started) * 1000)

    # 输出摘要
    label = {"server": "API 服务", "daemon": "认知 daemon", "gateway": "消息网关"}
    print("OCOS Restart" + (f" (env={env})" if env else ""))
    print("=" * 52)
    for name in components:
        r = results.get(name, {"ok": False, "error": "未执行（前置检查中止）"})
        if r.get("ok"):
            extra = f", 端口 {r['port']} 就绪" if "port" in r else ""
            print(f"  [OK]   {name:<8} {label.get(name, name):<10} {r.get('unit', '')} ({r.get('state', '')}{extra})")
        else:
            print(f"  [FAIL] {name:<8} {label.get(name, name):<10} {r.get('unit', '')}")
            print(f"         {r.get('error', '未知错误')}")
    print(f"  总耗时: {duration_ms}ms  →  {'全部成功' if all_ok else '存在失败组件'}")
    print(f"  操作日志: {LOG_PATH}")

    _append_log({
        "ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "user": user,
        "env": env,
        "components": {n: {"ok": r.get("ok", False),
                           "unit": r.get("unit"),
                           "state": r.get("state"),
                           "error": r.get("error")}
                       for n, r in results.items()},
        "ok": all_ok,
        "duration_ms": duration_ms,
    })
    return 0 if all_ok else 1


# ── 命令入口 ────────────────────────────────────────────────────

def cmd_restart(args, session: InteractionSession) -> int:
    """ocos restart — 整合重启 OCOS 系统（server/daemon/gateway）。"""
    only = list(getattr(args, "only", None) or [])
    components, err = _resolve_components(args.env, only)
    if err:
        print(f"[error] {err}")
        return 1
    return _do_restart(components, args.env)


def cmd_gateway(args, session: InteractionSession) -> int:
    """ocos gateway restart — 仅重启消息网关。"""
    action = getattr(args, "gateway_action", None)
    if action != "restart":
        print("用法: ocos gateway restart [--env dev|test|prod]")
        return 1
    env = getattr(args, "env", "prod") or "prod"
    return _do_restart(["gateway"], env)
