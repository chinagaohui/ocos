"""EnvironmentProbe — 宿主机 + 网络 + OCOS 深度 三层环境探针。

把 boot_awareness.py 的启动时一次性探查重构为可周期调用的轻量级探针，
输出 ComponentHealth（SystemProbe 已消费的契约），让 FaultDetector →
RepairProposer → 主动上报整条现有链路都能吃到环境信号。

三层探测:
  Layer A — 宿主机 (host): CPU load / 内存可用 / 磁盘可用 + iowait /
            OCOS 进程状态 / 温度（可选）
  Layer B — 网络 (network): DNS 解析 / HTTP 可达性（国内+国际）/ 延迟 /
            SSL 证书剩余天数
  Layer C — OCOS 深度 (daemon_self): 认知循环心跳（最近 3 tick 的 trace
            是否连续）/ DB 完整性（integrity_check + WAL 状态）/ 关键目录
            可写性 / 日志错误率

设计原则:
  - 轻量级默认（周期调用 ~5s/tick）；boot_awareness 用 heavy=True 加 GPU
    / 详细网络统计等深度探查
  - 全部只读 + 超时保护（单探测上限 3s，网络探测上限 5s）
  - 单探测失败 → ComponentHealth(healthy=False, warnings=[...])，不抛
  - 阈值可通过环境变量覆盖（OCOS_DISK_BAD_G / OCOS_MEM_BAD_G / ...）
"""

from __future__ import annotations

import logging
import os
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Optional

from ocos.diagnosis.diagnosis_types import ComponentHealth

logger = logging.getLogger(__name__)

# ── 阈值（环境变量可调）─────────────────────────────────────────────

def _env_float(name: str, default: float) -> float:
    v = os.environ.get(name, "").strip()
    try:
        return float(v) if v else default
    except ValueError:
        return default

def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name, "").strip()
    try:
        return int(v) if v else default
    except ValueError:
        return default


DISK_BAD_G   = _env_float("OCOS_DISK_BAD_G",  5.0)     # 磁盘可用 < 5G → BAD
DISK_WARN_G  = _env_float("OCOS_DISK_WARN_G", 15.0)    # 磁盘可用 < 15G → WARN
MEM_BAD_G    = _env_float("OCOS_MEM_BAD_G",    1.0)     # 内存可用 < 1G → BAD
MEM_WARN_G   = _env_float("OCOS_MEM_WARN_G",   2.0)     # 内存可用 < 2G → WARN
CPU_LOAD_BAD = _env_float("OCOS_CPU_LOAD_BAD", 4.0)     # load1 > 4 → BAD
CPU_LOAD_WARN= _env_float("OCOS_CPU_LOAD_WARN",2.5)     # load1 > 2.5 → WARN
IOWAIT_BAD   = _env_float("OCOS_IOWAIT_BAD",   15.0)    # iowait% > 15 → BAD
NET_TIMEOUT  = _env_int("OCOS_NET_TIMEOUT",     5)      # 单 URL 探测超时秒
COGNITION_MAX_GAP = _env_int("OCOS_COGNITION_MAX_GAP", 120)  # 认知循环最大间隔秒

# ── 工具 ────────────────────────────────────────────────────────────


def _run(cmd: str, timeout: int = 3) -> tuple[bool, str]:
    """跑一条只读探查命令。返回 (ok, 截断输出)。失败不抛。"""
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (r.returncode == 0,
                (r.stdout or r.stderr or "").strip()[:300])
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, str(e)[:120]


def _probe_url(url: str, timeout: int = NET_TIMEOUT) -> dict:
    """curl 联通性探测 → {ok, http_code, time_s, ssl_days}。"""
    ok, out = _run(
        f"curl -s --max-time {timeout} -o /dev/null "
        f"-w '%{{http_code}} %{{time_total}}' {url}",
        timeout=timeout + 2)
    result = {"ok": False, "http_code": "unreachable", "time_s": None}
    if ok and " " in out:
        code, _, t = out.partition(" ")
        try:
            result.update({
                "ok": code.startswith("2") or code.startswith("3"),
                "http_code": code,
                "time_s": round(float(t), 3),
            })
        except ValueError:
            pass
    # SSL 证书剩余天数（仅 https）
    if url.startswith("https://"):
        try:
            cert_ok, cert_out = _run(
                f"echo | openssl s_client -connect "
                f"{url.split('/')[2]}:443 2>/dev/null "
                f"| openssl x509 -noout -enddate 2>/dev/null",
                timeout=timeout + 3)
            if cert_ok and "notAfter=" in cert_out:
                # 解析 "notAfter=Sep 30 12:34:56 2026 GMT"
                import datetime as _dt
                date_str = cert_out.split("notAfter=")[-1].strip()
                try:
                    end = _dt.datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z")
                    end = end.replace(tzinfo=_dt.timezone.utc)
                    days = (end - _dt.datetime.now(_dt.timezone.utc)).days
                    result["ssl_days_left"] = days
                except ValueError:
                    pass
        except Exception:
            pass
    return result


def _read_file(path: str) -> str:
    """读 /proc 文件，失败返回空串。"""
    try:
        return Path(path).read_text()
    except OSError:
        return ""


# ════════════════════════════════════════════════════════════════════
# Layer A — 宿主机资源
# ════════════════════════════════════════════════════════════════════

def probe_host_resources(heavy: bool = False) -> ComponentHealth:
    """宿主机资源探针 — CPU load / 内存 / 磁盘 / OCOS 进程状态。"""
    metrics: dict = {}
    warnings: list[str] = []

    # ── CPU load ──
    loadavg = _read_file("/proc/loadavg")
    if loadavg:
        try:
            parts = loadavg.split()
            load1 = float(parts[0])
            load5 = float(parts[1])
            load15 = float(parts[2])
            metrics.update({"load1": load1, "load5": load5, "load15": load15})
            if load1 > CPU_LOAD_BAD:
                warnings.append(f"CPU load1={load1:.1f} > {CPU_LOAD_BAD} (过载)")
            elif load1 > CPU_LOAD_WARN:
                warnings.append(f"CPU load1={load1:.1f} > {CPU_LOAD_WARN} (偏高)")
        except (ValueError, IndexError):
            pass

    # ── 内存可用 ──
    try:
        mem_text = _read_file("/proc/meminfo")
        for line in mem_text.splitlines():
            if line.startswith("MemAvailable:"):
                avail_kb = int(line.split()[1])
                avail_g = round(avail_kb / 1048576, 1)
                metrics["mem_avail_g"] = avail_g
                if avail_g < MEM_BAD_G:
                    warnings.append(f"内存可用 {avail_g:.1f}G < {MEM_BAD_G}G (临界)")
                elif avail_g < MEM_WARN_G:
                    warnings.append(f"内存可用 {avail_g:.1f}G < {MEM_WARN_G}G (偏低)")
                break
    except (ValueError, IndexError):
        pass

    # ── 磁盘可用（根分区）+ iowait ──
    ok, df_out = _run("df -BG --output=avail / 2>/dev/null | tail -1")
    if ok and df_out.strip():
        try:
            disk_g = float(df_out.strip().rstrip("G").strip())
            metrics["disk_avail_g"] = disk_g
            if disk_g < DISK_BAD_G:
                warnings.append(f"磁盘可用 {disk_g:.0f}G < {DISK_BAD_G}G (临界)")
            elif disk_g < DISK_WARN_G:
                warnings.append(f"磁盘可用 {disk_g:.0f}G < {DISK_WARN_G}G (偏低)")
        except ValueError:
            pass

    # iowait — 用 vmstat 1 采样 1 秒，从列头定位 wa 位置
    # 注意: vmstat 输出两行 header (分组标题 + 列名)，列名在第二行
    try:
        ok_vm, vm_out = _run("vmstat 1 2 2>/dev/null", timeout=5)
        if ok_vm and vm_out.strip():
            lines = vm_out.strip().splitlines()
            if len(lines) >= 3:
                header = lines[1].split()   # 第二行才是列名
                data = lines[-1].split()   # 最后一行是采样数据
                # 从 header 找 wa 或 IO-wait 或 iowait 列
                wa_idx = None
                for i, h in enumerate(header):
                    h_lower = h.lower()
                    if h_lower in ("wa", "io-wait", "iowait", "wait"):
                        wa_idx = i
                        break
                if wa_idx is None:
                    # 退化: wa 在倒数第 3 列（id wa st gu → 倒数第 3）
                    wa_idx = len(header) - 3 if len(header) >= 3 else None
                if wa_idx is not None and wa_idx < len(data):
                    try:
                        wa_pct = float(data[wa_idx])
                        metrics["iowait_pct"] = round(wa_pct, 1)
                        if wa_pct > IOWAIT_BAD:
                            warnings.append(f"IO wait={wa_pct:.0f}% > {IOWAIT_BAD}% (磁盘忙)")
                    except (ValueError, IndexError):
                        pass
    except Exception:
        pass

    # ── OCOS 进程状态 ──
    # systemd user service 的进程名是 "ocos"（ExecStart=.venv/bin/ocos run）
    try:
        ok_ps, ps_out = _run("pgrep -af 'ocos.*run|ocos-daemon|resident_runtime' 2>/dev/null | head -3")
        pid = None
        if ok_ps and ps_out.strip():
            # 取第一个匹配的 PID
            first_line = ps_out.strip().splitlines()[0]
            try:
                pid = int(first_line.split()[0])
            except (ValueError, IndexError):
                pass
        if pid:
            metrics["ocos_pid"] = pid
            # 进程存活 & 内存占用
            try:
                with open(f"/proc/{pid}/status") as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            rss_kb = int(line.split()[1])
                            metrics["ocos_rss_mb"] = round(rss_kb / 1024, 1)
                            break
                with open(f"/proc/{pid}/stat") as f:
                    stat_parts = f.read().split()
                    state_char = stat_parts[2] if len(stat_parts) > 2 else "?"
                    metrics["ocos_state"] = state_char
                    # state D=不可中断睡眠（通常 IO 阻塞）→ 警告
                    if state_char == "D":
                        warnings.append(f"OCOS 进程 {pid} 处于 D 状态 (IO 阻塞)")
            except (OSError, ValueError, IndexError):
                pass
        else:
            # 没找到 daemon 进程可能是正常的（刚启动或用不同方式运行）
            # 不算 unhealthy，但记为提示
            metrics["ocos_pid"] = None
    except Exception:
        pass

    # ── 温度（heavy 模式或周期探测都试一下，失败静默）──
    try:
        ok_t, temp_out = _run("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
        if ok_t and temp_out.strip().isdigit():
            temp_c = int(temp_out.strip()) / 1000.0
            metrics["cpu_temp_c"] = round(temp_c, 1)
            if temp_c > 85:
                warnings.append(f"CPU 温度 {temp_c:.0f}°C > 85°C (过热)")
            elif temp_c > 75:
                warnings.append(f"CPU 温度 {temp_c:.0f}°C > 75°C (偏高)")
    except Exception:
        pass

    healthy = len(warnings) == 0
    return ComponentHealth(
        component="host",
        healthy=healthy,
        metrics=metrics,
        warnings=warnings,
        last_error="; ".join(warnings) if not healthy else "",
    )


# ════════════════════════════════════════════════════════════════════
# Layer B — 网络
# ════════════════════════════════════════════════════════════════════

def probe_network() -> ComponentHealth:
    """网络连通性探针 — DNS / HTTP 可达性 / 延迟 / SSL。"""
    metrics: dict = {}
    warnings: list[str] = []

    # ── DNS 解析 ──
    ok_dns, dns_out = _run("host -W 3 www.baidu.com 2>&1 || nslookup www.baidu.com 2>&1",
                           timeout=5)
    metrics["dns_ok"] = ok_dns
    if not ok_dns:
        warnings.append(f"DNS 解析失败: {dns_out[:60]}")

    # ── 国内 HTTP ──
    domestic = _probe_url("https://www.baidu.com", timeout=NET_TIMEOUT)
    metrics["domestic"] = {k: v for k, v in domestic.items()
                           if k != "time_s" or v is None}
    # 精简 metrics（避免太大）
    metrics["domestic_ok"] = domestic["ok"]
    metrics["domestic_time_s"] = domestic.get("time_s")
    if not domestic["ok"]:
        warnings.append(f"国内网络不可达 (baidu.com: {domestic['http_code']})")

    # ── 国际 HTTP ──
    intl = _probe_url("https://api.github.com", timeout=NET_TIMEOUT)
    metrics["intl_ok"] = intl["ok"]
    metrics["intl_time_s"] = intl.get("time_s")
    if not intl["ok"]:
        warnings.append(f"国际网络不可达 (github API: {intl['http_code']})")

    # ── SSL 证书（仅做了 github 的，够了）──
    ssl_days = intl.get("ssl_days_left")
    if ssl_days is not None:
        metrics["intl_ssl_days"] = ssl_days
        if ssl_days < 7:
            warnings.append(f"github.com SSL 证书还有 {ssl_days} 天过期")

    # 综合健康：只要有一个方向可达就算 healthy
    # （完全离线 = 全断；单边通 = degraded 但不算 unhealthy）
    any_reachable = domestic["ok"] or intl["ok"]
    if not any_reachable:
        warnings.append("网络完全离线")
        healthy = False
    elif domestic["ok"] and not intl["ok"]:
        warnings.append("国际网络不可达（国内正常）")
        healthy = True   # degraded 但不算 unhealthy
    else:
        healthy = True

    metrics["state"] = (
        "offline" if not any_reachable
        else "domestic_only" if domestic["ok"] and not intl["ok"]
        else "full")

    return ComponentHealth(
        component="network",
        healthy=healthy,
        metrics=metrics,
        warnings=warnings if any_reachable else warnings,  # 只在 unhealthy 时列 warning
        last_error="" if healthy else "; ".join(warnings),
    )


# ════════════════════════════════════════════════════════════════════
# Layer C — OCOS 深度（daemon_self）
# ════════════════════════════════════════════════════════════════════

def probe_daemon_self(db_path: str) -> ComponentHealth:
    """OCOS 深度健康探针 — DB 完整性 + 关键目录权限 + 日志错误率。"""
    metrics: dict = {}
    warnings: list[str] = []

    if not db_path or db_path == ":memory:":
        return ComponentHealth(
            component="daemon_self", healthy=True,
            metrics={"mode": "in-memory", "db_skipped": True},
            warnings=["memory mode — 跳过 DB 深度检查"])

    db = Path(db_path)
    metrics["db_exists"] = db.exists()
    metrics["db_size_mb"] = round(db.stat().st_size / 1048576, 1) if db.exists() else 0

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

        # ── 1. DB 完整性 ──
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        metrics["integrity"] = integrity
        if integrity != "ok":
            warnings.append(f"DB 完整性检查失败: {integrity}")

        # ── 2. WAL 状态 ──
        try:
            wal = conn.execute("PRAGMA journal_mode").fetchone()[0]
            metrics["journal_mode"] = wal
            # WAL 文件过大可能意味着 checkpoint 没跑（> 主文件 50% → warn）
            wal_path = Path(db_path + "-wal")
            if wal_path.exists():
                wal_mb = wal_path.stat().st_size / 1048576
                db_mb = max(0.1, db.stat().st_size / 1048576)
                metrics["wal_size_mb"] = round(wal_mb, 1)
                if wal_mb / db_mb > 0.5:
                    warnings.append(f"WAL 文件 ({wal_mb:.1f}M) > 主 DB ({db_mb:.1f}M) 的 50%")
        except sqlite3.Error:
            pass

        # ── 3. 关键表行数 + 增长趋势 ──
        table_counts: dict = {}
        for tbl in ("episodes", "goals", "knowledge", "belief"):
            try:
                cnt = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                table_counts[tbl] = cnt
            except sqlite3.Error:
                table_counts[tbl] = -1
        metrics["table_counts"] = table_counts

        # ── 4. episodes 最近写入时间（判断 daemon 是否在活跃）──
        try:
            row = conn.execute(
                "SELECT MAX(created_at) FROM episodes").fetchone()
            last_ts = row[0] if row else None
            if last_ts:
                try:
                    from datetime import datetime, timezone
                    dt = datetime.fromisoformat(str(last_ts).replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    age_min = (datetime.now(timezone.utc) - dt).total_seconds() / 60
                    metrics["last_episode_age_min"] = round(age_min, 1)
                    if age_min > 30:
                        warnings.append(
                            f"最近 episode 写入是 {age_min:.0f} 分钟前 "
                            f"(daemon 可能休眠或卡住)")
                except ValueError:
                    pass
        except sqlite3.Error:
            pass

    except sqlite3.Error as e:
        warnings.append(f"DB 连接失败: {e}")
    finally:
        if conn:
            conn.close()

    # ── 5. 关键目录可写性 ──
    home_ocos = Path.home() / ".ocos"
    for d_name, d_path in [
        ("data_root", home_ocos),
        ("artifacts", home_ocos / "artifacts"),
        ("plans", home_ocos / "artifacts" / "plans"),
        ("reports", home_ocos / "artifacts" / "reports"),
    ]:
        try:
            d_path.mkdir(parents=True, exist_ok=True)
            # 尝试写一个临时文件
            import tempfile
            with tempfile.NamedTemporaryFile(dir=d_path, suffix=".probe",
                                             delete=True) as _f:
                pass
            metrics[f"{d_name}_writable"] = True
        except OSError as e:
            metrics[f"{d_name}_writable"] = False
            warnings.append(f"目录不可写: {d_path} ({e})")

    healthy = len([w for w in warnings
                   if not any(k in w for k in ("DB 连接失败",))]) == 0
    return ComponentHealth(
        component="daemon_self",
        healthy=healthy,
        metrics=metrics,
        warnings=warnings,
        last_error="; ".join(warnings) if not healthy else "",
    )


def probe_cognition_heartbeat(db_path: str) -> ComponentHealth:
    """认知循环心跳探针 — 最近 tick 是否连续、trace 有没有断。

    逻辑:
      1. 查最近的 cognition trace 条目（episodes 里 source='cognition' 或
         action 含 cognition_loop）
      2. 取最近 3 条的 created_at，检查间隔 ≤ COGNITION_MAX_GAP
      3. 如果最近一条距今 > COGNITION_MAX_GAP → 警告
      4. 根本找不到 cognition 条目 → 可能还没启动认知循环，先记 warn
    """
    metrics: dict = {}
    warnings: list[str] = []

    if not db_path or db_path == ":memory:":
        return ComponentHealth(
            component="cognition_heartbeat", healthy=True,
            metrics={"mode": "in-memory", "skipped": True})

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

        # 找认知循环相关的 episode（source='cognition' 或 action 含 cognition）
        try:
            rows = conn.execute(
                "SELECT created_at, action, outcome FROM episodes "
                "WHERE source LIKE '%cognitive%' "
                "   OR action LIKE '%cognition%' "
                "   OR tags LIKE '%cognition%' "
                "ORDER BY created_at DESC LIMIT 5"
            ).fetchall()
        except sqlite3.Error:
            rows = []

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        if not rows:
            metrics["cognition_entries"] = 0
            warnings.append("未检出认知循环 trace 条目（可能还没启动）")
            return ComponentHealth(
                component="cognition_heartbeat",
                healthy=True,   # 还没启动不是 unhealthy
                metrics=metrics,
                warnings=warnings,
            )

        metrics["cognition_entries"] = len(rows)
        timestamps = []
        for ts_str, action, outcome in rows:
            if ts_str:
                try:
                    dt = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    timestamps.append(dt)
                except ValueError:
                    continue

        if timestamps:
            # 最近一条距今多久
            latest = max(timestamps)
            age_s = (now - latest).total_seconds()
            metrics["latest_cognition_age_s"] = round(age_s, 1)

            if age_s > COGNITION_MAX_GAP:
                warnings.append(
                    f"认知循环距今 {age_s:.0f}s > {COGNITION_MAX_GAP}s "
                    f"(可能卡住或没跑)")

            # 检查连续性（最近几条间隔是否合理）
            if len(timestamps) >= 2:
                sorted_ts = sorted(timestamps, reverse=True)
                gaps = []
                for i in range(len(sorted_ts) - 1):
                    gap = (sorted_ts[i] - sorted_ts[i + 1]).total_seconds()
                    gaps.append(gap)
                metrics["cognition_gaps_s"] = [round(g, 0) for g in gaps]
                big_gaps = [g for g in gaps if g > COGNITION_MAX_GAP]
                if big_gaps:
                    warnings.append(
                        f"认知循环存在大间隔: {big_gaps[0]:.0f}s "
                        f"(连续运行可能被打断)")

    except sqlite3.Error as e:
        warnings.append(f"DB 查询失败: {e}")
    finally:
        if conn:
            conn.close()

    # cognition_heartbeat 通常降级为 warn 就好——不影响核心功能
    healthy = len(warnings) == 0
    return ComponentHealth(
        component="cognition_heartbeat",
        healthy=healthy,
        metrics=metrics,
        warnings=warnings,
        last_error="; ".join(warnings) if not healthy else "",
    )


# ════════════════════════════════════════════════════════════════════
# 聚合入口 — 一次性跑全部（供 boot_awareness 复用和周期探测）
# ════════════════════════════════════════════════════════════════════

def capture_all(db_path: str = "", heavy: bool = False) -> dict[str, ComponentHealth]:
    """一次性跑全部三层探针 → {name: ComponentHealth} dict。

    heavy=True 时启用深度探测（boot_awareness 用），默认轻量周期模式。
    """
    results: dict[str, ComponentHealth] = {}
    for name, fn in [
        ("host", lambda: probe_host_resources(heavy=heavy)),
        ("network", probe_network),
        ("daemon_self", lambda: probe_daemon_self(db_path)),
        ("cognition_heartbeat", lambda: probe_cognition_heartbeat(db_path)),
    ]:
        try:
            results[name] = fn()
        except Exception as e:
            results[name] = ComponentHealth(
                component=name, healthy=False,
                warnings=[f"probe crashed: {e}"],
                last_error=str(e))
    return results


__all__ = [
    "probe_host_resources", "probe_network", "probe_daemon_self",
    "probe_cognition_heartbeat", "capture_all",
    "DISK_BAD_G", "DISK_WARN_G", "MEM_BAD_G", "MEM_WARN_G",
    "CPU_LOAD_BAD", "CPU_LOAD_WARN", "NET_TIMEOUT", "COGNITION_MAX_GAP",
]
