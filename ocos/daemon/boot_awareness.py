"""启动自省（数字生命·环境适应力）— 每次启动像人一样先审视自身。

用户需求（2026-09-08）: 断电/关机/重启后启动，OCOS 先自动探查宿主机、
网络等环境情况，做出详情分析，再优化自身适应力。

流程: 采集(系统/GPU/磁盘/内存/网络/自身状态/停机推断) → 分析(findings)
      → 适应(boot_context.json 环境先验供目标执行注入 + 异常条件转刺激)
      → 汇报(outbox kind="report" 推对话流)

设计原则:
  - 全部事实可溯源（命令原始输出保留摘要），无 LLM、无编造；
  - 只读探查 + 小体量落盘，失败降级不抛——自省是增值产物，不阻断启动；
  - 异常条件复用 MotivationHub.propose_stimulus（升级阶梯/每日预算/
    饱和静默三道闸全继承），不自建目标管线；
  - 断电/重启推断诚实措辞：boot_id 变更 = 宿主机重启（硬事实）；
    episode 间隔 > 运行时长 = "停机约 X 小时（关机或断电，无法区分）"。
"""

from __future__ import annotations

import json
import logging
import sqlite3
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

BOOT_CONTEXT_PATH = Path.home() / ".ocos" / "boot_context.json"
DISK_WARN_G = 15.0          # 磁盘可用 < 15G → warn + 刺激
DISK_BAD_G = 5.0
MEM_WARN_G = 2.0            # 内存可用 < 2G → warn
NET_TIMEOUT = 8             # 联通性探测上限（秒）
RECENT_BOOT_S = 1800        # uptime < 30min 视为"近期启动"


def _run(cmd: str, timeout: int = 10) -> tuple[bool, str]:
    """跑一条只读探查命令，返回 (ok, 截断输出)。失败不抛。"""
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (r.returncode == 0,
                (r.stdout or r.stderr or "").strip()[:500])
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, str(e)[:200]


def _probe_url(url: str, timeout: int = NET_TIMEOUT) -> dict:
    """curl 联通性探测 → {ok, http_code, time_s}。"""
    ok, out = _run(
        f"curl -s --max-time {timeout} -o /dev/null "
        f"-w '%{{http_code}} %{{time_total}}' {url}",
        timeout=timeout + 3)
    if ok and " " in out:
        code, _, t = out.partition(" ")
        try:
            return {"ok": code.startswith("2") or code.startswith("3"),
                    "http_code": code, "time_s": float(t)}
        except ValueError:
            pass
    return {"ok": False, "http_code": out[:40] or "unreachable",
            "time_s": None}


def _read_boot_id() -> str:
    ok, out = _run("cat /proc/sys/kernel/random/boot_id", timeout=3)
    return out.strip() if ok else ""


def _collect_system() -> dict:
    sysinfo: dict = {}
    ok, out = _run("uname -r", timeout=3)
    sysinfo["kernel"] = out if ok else "?"
    try:
        uptime_s = float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        uptime_s = -1.0
    sysinfo["uptime_s"] = uptime_s
    ok, out = _run("df -BG --output=avail / 2>/dev/null | tail -1",
                   timeout=3)
    try:
        sysinfo["disk_avail_g"] = float(out.strip().rstrip("G").strip())
    except ValueError:
        sysinfo["disk_avail_g"] = -1.0
    # 内存可用量 — 直接读 /proc/meminfo（free 输出受 locale 影响，
    # 中文环境列头为「内存：」导致 /^Mem:/ 匹配失败）；kB → GiB
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8") \
                .splitlines():
            if line.startswith("MemAvailable:"):
                sysinfo["mem_avail_g"] = round(
                    float(line.split()[1]) / 1048576, 1)
                break
        else:
            sysinfo["mem_avail_g"] = -1.0
    except (OSError, ValueError, IndexError):
        sysinfo["mem_avail_g"] = -1.0
    ok, out = _run("nproc", timeout=3)
    sysinfo["cpu_cores"] = int(out) if (ok and out.isdigit()) else 0
    # GPU — nvidia-smi 失败退 lspci（与 bridge 硬件命令集同语义）
    ok, out = _run("nvidia-smi --query-gpu=name,memory.total "
                   "--format=csv,noheader", timeout=8)
    if ok and out:
        sysinfo["gpu"] = out.splitlines()[0][:120]
        sysinfo["gpu_is_nvidia"] = True
    else:
        ok2, out2 = _run("lspci 2>/dev/null | grep -iE 'vga|3d' | head -2",
                         timeout=5)
        sysinfo["gpu"] = out2 if (ok2 and out2) else "未检出"
        sysinfo["gpu_is_nvidia"] = False
    return sysinfo


def _collect_network() -> dict:
    net: dict = {}
    ok, out = _run("hostname -I 2>/dev/null | awk '{print $1}'", timeout=3)
    net["local_ip"] = out.split()[0] if (ok and out.split()) else "未知"
    domestic = _probe_url("https://www.baidu.com")
    intl = _probe_url("https://api.github.com")
    net["domestic_ok"] = domestic["ok"]
    net["intl_ok"] = intl["ok"]
    net["intl_time_s"] = intl.get("time_s")
    if not domestic["ok"]:
        net["state"] = "offline"
    elif not intl["ok"]:
        net["state"] = "domestic_only"
    else:
        net["state"] = "full"
    return net


def _collect_self(db_path: str) -> dict:
    st: dict = {}
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        st["episodes"] = conn.execute(
            "SELECT COUNT(*) FROM episodes").fetchone()[0]
        st["goals_total"] = conn.execute(
            "SELECT COUNT(*) FROM goals").fetchone()[0]
        st["goals_pending"] = conn.execute(
            "SELECT COUNT(*) FROM goals WHERE status='PENDING'").fetchone()[0]
        row = conn.execute(
            "SELECT MAX(created_at) FROM episodes").fetchone()
        st["last_episode_at"] = row[0] if row else None
    except sqlite3.Error as e:
        st["error"] = str(e)[:120]
    finally:
        conn.close()
    try:
        ndir = Path.home() / ".ocos" / "narrative"
        st["narrative_chapters"] = len(list(ndir.glob("week_*.md")))
    except OSError:
        st["narrative_chapters"] = 0
    if BOOT_CONTEXT_PATH.exists():
        try:
            st["prev_boot_id"] = json.loads(
                BOOT_CONTEXT_PATH.read_text(encoding="utf-8")).get(
                "boot_id", "")
        except (ValueError, OSError):
            st["prev_boot_id"] = ""
    else:
        st["prev_boot_id"] = ""
    return st


def _parse_ts(ts) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _collect(db_path: str) -> dict:
    sysinfo = _collect_system()
    net = _collect_network()
    selfst = _collect_self(db_path)
    power: dict = {"boot_id": _read_boot_id()}
    up_s = sysinfo.get("uptime_s", -1.0)
    power["recent_boot"] = 0 <= up_s < RECENT_BOOT_S
    prev_boot = selfst.get("prev_boot_id", "")
    power["reboot_detected"] = bool(prev_boot) and (
        power["boot_id"] != prev_boot)
    # 停机推断: 上条 episode 距今间隔 > 本次运行时长 → 中间经历过停机
    # （关机或断电无法区分——诚实措辞，不编造原因）
    last_dt = _parse_ts(selfst.get("last_episode_at"))
    if last_dt is not None and up_s >= 0:
        gap_h = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
        power["gap_since_activity_h"] = round(gap_h, 2)
        power["downtime_h"] = (round(gap_h - up_s / 3600.0, 2)
                               if gap_h * 3600 > up_s else 0.0)
    else:
        power["gap_since_activity_h"] = None
        power["downtime_h"] = None
    return {"system": sysinfo, "network": net, "self": selfst,
            "power": power,
            "collected_at": datetime.now(timezone.utc).isoformat()}


# ── 分析 ─────────────────────────────────────────────────────────────

def _analyze(data: dict) -> list[dict]:
    """采集结果 → findings（level: ok/warn/bad，全部附事实依据）。"""
    f: list[dict] = []
    sysinfo = data["system"]
    net = data["network"]
    power = data["power"]

    gpu = sysinfo.get("gpu", "未检出")
    f.append({"level": "ok" if sysinfo.get("gpu_is_nvidia") else "warn",
              "key": "gpu",
              "key_bad": (None if sysinfo.get("gpu_is_nvidia")
                          else "boot_gpu_absent"),
              "text": f"GPU: {gpu}"
                      + ("（CUDA 生态可用）" if sysinfo.get("gpu_is_nvidia")
                         else "（无 NVIDIA 卡，本地微调/推理受限）")})

    if net["state"] == "full":
        t = net.get("intl_time_s")
        f.append({"level": "ok", "key": "network",
                  "text": f"网络: 内外网均可达"
                          + (f"（国际链路 {t:.2f}s）" if t else "")})
    elif net["state"] == "domestic_only":
        f.append({"level": "warn", "key": "network",
                  "key_bad": "boot_network_degraded",
                  "text": "网络: 国内可达、国际不可达——外联调研类任务"
                          "预计失败，优先本地能力"})
    else:
        f.append({"level": "bad", "key": "network",
                  "key_bad": "boot_network_offline",
                  "text": "网络: 完全离线——外联任务全部不可行，"
                          "仅本地记忆与命令可用"})

    disk = sysinfo.get("disk_avail_g", -1)
    if disk < 0:
        f.append({"level": "warn", "key": "disk",
                  "text": "磁盘: 可用空间未知（df 失败）"})
    elif disk < DISK_BAD_G:
        f.append({"level": "bad", "key": "disk",
                  "key_bad": "boot_disk_pressure",
                  "text": f"磁盘: 仅剩 {disk:.0f}G——写入类操作有耗尽风险"})
    elif disk < DISK_WARN_G:
        f.append({"level": "warn", "key": "disk",
                  "key_bad": "boot_disk_pressure",
                  "text": f"磁盘: 可用 {disk:.0f}G——低于安全水位，"
                          f"大文件落盘前需清理"})
    else:
        f.append({"level": "ok", "key": "disk",
                  "text": f"磁盘: 可用 {disk:.0f}G"})

    mem = sysinfo.get("mem_avail_g", -1)
    if mem < 0:
        f.append({"level": "ok", "key": "memory",
                  "text": "内存: 采集失败（本轮视为未知，不推断）"})
    elif mem < MEM_WARN_G:
        f.append({"level": "warn", "key": "memory",
                  "key_bad": "boot_memory_pressure",
                  "text": f"内存: 可用 {mem:.0f}G——大模型加载可能失败"})
    else:
        f.append({"level": "ok", "key": "memory",
                  "text": f"内存: 可用 {mem:.0f}G"})

    if power.get("reboot_detected"):
        dt = power.get("downtime_h")
        detail = (f"，其间停机约 {dt:.1f} 小时（关机或断电，无法区分）"
                  if dt else "")
        f.append({"level": "ok", "key": "power",
                  "text": f"宿主机经历过重启（boot_id 变更）{detail}"
                          "——在途目标已由 stale-ACTIVE 回收机制接管"})
    elif power.get("recent_boot"):
        f.append({"level": "ok", "key": "power",
                  "text": "近期启动（运行不足 30 分钟），环境探查为"
                          "本次开机后首次"})
    return f


def _render_report(data: dict, findings: list[dict]) -> str:
    s, n, p = data["system"], data["network"], data["power"]
    st = data["self"]
    lines = ["[启动自省] 我醒来了，先审视了一下自身与所处环境："]
    lines.append(f"· 身体: {s.get('cpu_cores', '?')} 核 CPU / "
                 f"内存可用 {s.get('mem_avail_g', '?')}G / "
                 f"磁盘可用 {s.get('disk_avail_g', '?')}G / "
                 f"内核 {s.get('kernel', '?')}")
    lines.append(f"· 感官: GPU = {s.get('gpu', '未检出')}")
    net_txt = {"full": "内外网畅通", "domestic_only": "仅国内可达",
               "offline": "完全离线"}.get(n.get("state"), "未知")
    intl = (f"（国际 {n['intl_time_s']:.2f}s）"
            if n.get("intl_time_s") else "")
    lines.append(f"· 神经: 本机 {n.get('local_ip', '?')}，{net_txt}{intl}")
    if p.get("reboot_detected"):
        dt = p.get("downtime_h")
        lines.append("· 苏醒: 检测到宿主机重启"
                     + (f"，停机约 {dt:.1f} 小时（关机或断电）" if dt else ""))
    if st.get("episodes") is not None:
        lines.append(f"· 记忆: {st['episodes']} 段经历 / "
                     f"{st.get('goals_total', '?')} 个目标"
                     f"（{st.get('goals_pending', 0)} 个待办）/ "
                     f"{st.get('narrative_chapters', 0)} 章成长叙事")
    warns = [x for x in findings if x["level"] in ("warn", "bad")]
    if warns:
        lines.append("· 适应: " + "；".join(w["text"] for w in warns))
    else:
        lines.append("· 适应: 各项正常，无需特别调整")
    return "\n".join(lines)


# ── 适应 + 主入口 ────────────────────────────────────────────────────

def _adapt_write_context(data: dict, findings: list[dict],
                         report: str) -> None:
    """写 boot_context.json — 目标执行 prompt 的环境先验（读侧在 bridge）。"""
    try:
        BOOT_CONTEXT_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "boot_id": data["power"].get("boot_id", ""),
            "at": data["collected_at"],
            "uptime_s": data["system"].get("uptime_s"),
            "reboot_detected": data["power"].get("reboot_detected", False),
            "downtime_h": data["power"].get("downtime_h"),
            "gpu": data["system"].get("gpu"),
            "gpu_is_nvidia": data["system"].get("gpu_is_nvidia", False),
            "network_state": data["network"].get("state"),
            "intl_time_s": data["network"].get("intl_time_s"),
            "disk_avail_g": data["system"].get("disk_avail_g"),
            "mem_avail_g": data["system"].get("mem_avail_g"),
            "cpu_cores": data["system"].get("cpu_cores"),
            "kernel": data["system"].get("kernel"),
            "summary_line": report.splitlines()[0] if report else "",
            "findings": [{"level": x["level"], "key": x["key"],
                          "text": x["text"]} for x in findings],
        }
        BOOT_CONTEXT_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1),
            encoding="utf-8")
    except OSError as e:
        logger.warning("boot context write failed: %s", e)


def _adapt_save_episode(db_path: str, report: str, findings: list[dict],
                        data: dict) -> None:
    """报告入记忆（episode），供后续自省/复盘溯源。失败降级不抛。"""
    try:
        from ocos.memory.episode.models import Episode
        from ocos.memory.episode.store import EpisodeStore
        store = EpisodeStore(db_path)
        store.initialize()
        ep = Episode.from_candidate(
            experience_id=f"boot-{data['power'].get('boot_id', '')[:8]}"
                          f"-{uuid.uuid4().hex[:6]}",
            context={"kind": "boot_awareness",
                     "boot_id": data["power"].get("boot_id", ""),
                     "reboot_detected": data["power"].get(
                         "reboot_detected", False)},
            goal="启动自省：审视自身与环境",
            decision=report[:4000],
            action="boot_awareness.run",
            outcome={"success": True,
                     "warn_bad": sum(1 for x in findings
                                     if x["level"] in ("warn", "bad"))},
            condition="daemon boot trigger",
            significance_score=0.6,
            evaluation_trace={},
            source="boot_awareness",
            tags=["boot_awareness", "boot_report"],
        )
        store.save(ep)
    except Exception as e:
        logger.warning("boot awareness episode write failed: %s", e)


def run_boot_awareness(db_path: str, post_fn=None, stimulus_fn=None,
                       level: int = 1) -> dict:
    """启动自省主入口（daemon start 后调用一次）。

    post_fn: callable(str) — 报告推送（outbox report 通道）
    stimulus_fn: callable(list[dict]) — 异常条件转刺激
                 （走 MotivationHub.propose_stimulus 三道闸）
    返回 boot_context dict（供日志/测试断言）。
    """
    data = _collect(db_path)
    findings = _analyze(data)
    report = _render_report(data, findings)
    _adapt_write_context(data, findings, report)
    _adapt_save_episode(db_path, report, findings, data)
    if stimulus_fn is not None:
        try:
            stimuli = [{"key": x["key_bad"], "severity": "high",
                        "description": f"启动自省发现: {x['text']}",
                        "evidence": {"source": "boot_awareness",
                                     "at": data["collected_at"]}}
                       for x in findings if x.get("key_bad")]
            if stimuli:
                stimulus_fn(stimuli)
        except Exception:
            logger.exception("boot awareness stimulus dispatch failed")
    if post_fn is not None:
        try:
            post_fn(report)
        except Exception as e:
            logger.warning("boot awareness report post failed: %s", e)
    logger.info("Boot awareness: %s", report.replace("\n", " | "))
    return {"summary_line": report.splitlines()[0] if report else "",
            "findings": findings, "data": data, "report": report}


__all__ = ["run_boot_awareness", "BOOT_CONTEXT_PATH"]
