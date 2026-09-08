"""OCOS CLI — stop 命令实现（L0-5: 制动开关 STOP 神经）。

用法:
    ocos stop --soft            # 软制动: SIGUSR2 → 完成当前 tick 后挂起
                                # 自主活动，对话仍响应
    ocos stop --soft --resume   # 解除软制动
    ocos stop                   # 硬停: systemctl --user stop ocos-daemon

软制动通过 daemon 心跳文件（~/.ocos/daemon_heartbeat.json）定位 pid，
发送 SIGUSR2 切换制动状态（brake ↔ resume 幂等切换）。
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def heartbeat_path() -> Path:
    """心跳文件路径（OCOS_HEARTBEAT_PATH 可覆写 — 测试/多实例隔离）。"""
    return Path(os.environ.get(
        "OCOS_HEARTBEAT_PATH",
        str(Path.home() / ".ocos" / "daemon_heartbeat.json")))


def resolve_daemon_pid(path_override: Path | None = None) -> int | None:
    """从心跳文件解析 daemon pid；进程不存在时返回 None。

    心跳由 daemon 每 5 tick 刷新 — 有心跳即近期存活。
    """
    path = path_override or heartbeat_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        pid = int(data.get("pid", 0))
    except Exception:
        return None
    if pid <= 0:
        return None
    try:
        os.kill(pid, 0)   # 存活探针（不真正发送）
    except ProcessLookupError:
        return None
    except PermissionError:
        return pid        # 进程存在但非本用户（保守返回）
    return pid


def cmd_stop(args, session) -> int:
    """ocos stop [--soft] [--resume]"""
    if not args.soft:
        # 硬停 — systemd 托管走 unit 停止（含自动重启语义的显式覆盖）
        try:
            subprocess.run(
                ["systemctl", "--user", "stop", "ocos-daemon.service"],
                check=True, timeout=30)
            print("ocos-daemon.service 已停止（systemd）")
            return 0
        except FileNotFoundError:
            print("systemctl 不可用 — 非 systemd 环境；硬停请直接 "
                  "kill <pid>（pid 见 ~/.ocos/daemon_heartbeat.json）")
            return 1
        except subprocess.CalledProcessError as e:
            print(f"systemctl stop 失败: {e}")
            return 1

    pid = resolve_daemon_pid()
    if pid is None:
        print("未发现存活的 ocos daemon（心跳缺失或进程已退出）— "
              "无需制动")
        return 1

    resume = bool(getattr(args, "resume", False))
    # SIGUSR2 = 制动切换；CLI 先读心跳 braked 态决定是否发送 —
    # 保证 brake/resume 各自幂等（不会因重复执行而误切回）。
    try:
        braked = bool(json.loads(
            heartbeat_path().read_text(encoding="utf-8")).get("braked"))
    except Exception:
        braked = False
    if resume:
        if not braked:
            print(f"daemon(pid={pid}) 未处于制动状态 — 无需恢复")
            return 0
    elif braked:
        print(f"daemon(pid={pid}) 已处于制动状态 — 无需重复制动")
        return 0

    try:
        os.kill(pid, signal.SIGUSR2)
    except OSError as e:
        print(f"SIGUSR2 发送失败: {e}")
        return 1
    action = "恢复指令已送达" if resume else "制动指令已送达"
    print(f"{action}: daemon pid={pid}")
    print("  制动 = 完成当前 tick 后挂起自主活动；对话仍响应")
    print(f"  状态确认: cat {heartbeat_path()} （braked 字段，每 5 tick 刷新）")
    return 0
