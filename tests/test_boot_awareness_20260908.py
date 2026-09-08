"""启动自省（2026-09-08）— 数字生命·环境适应力。

用户需求: 断电/关机/重启启动后，像人一样先审视自身（宿主机/网络/环境），
详情分析，优化自身适应力。

钉死契约:
  A. 采集 — 系统/GPU/网络/自身状态全只读探查，命令失败诚实降级不抛；
  B. 断电/重启推断 — boot_id 变更 = 重启（硬事实）；episode 间隔 >
     运行时长 = 停机 X 小时（关机或断电无法区分，措辞不编造）；
  C. 分析 — findings 分级 ok/warn/bad，全部附事实依据；
  D. 适应 — boot_context.json 落盘（bridge 读侧注入目标执行 prompt，
     环境先验）；异常条件（offline/磁盘压力/内存压力/无 GPU）→
     stimulus 走 MotivationHub 既有三道闸，不自建目标管线；
  E. 汇报 — post_fn 报告（outbox report 通道），报告入 episode 记忆。
"""

from __future__ import annotations

import json
import sqlite3

import pytest

import ocos.daemon.boot_awareness as ba


@pytest.fixture()
def ctx_path(tmp_path, monkeypatch):
    p = tmp_path / "boot_context.json"
    monkeypatch.setattr(ba, "BOOT_CONTEXT_PATH", p)
    return p


@pytest.fixture()
def db(tmp_path):
    from ocos.memory.episode.store import EpisodeStore
    p = str(tmp_path / "boot.db")
    EpisodeStore(db_path=p).initialize()
    return p


# ── A/B. 采集与断电推断 ──────────────────────────────────────────────

class TestCollect:
    def test_probe_command_failure_degrades(self, monkeypatch):
        monkeypatch.setattr(ba, "_run",
                            lambda cmd, timeout=10: (False, "exit 1"))
        s = ba._collect_system()
        assert s["gpu"] == "未检出"
        assert s["gpu_is_nvidia"] is False
        assert s["disk_avail_g"] == -1.0

    def test_mem_from_proc_meminfo(self, tmp_path, monkeypatch):
        # 内存读取走 /proc/meminfo（free 受 locale 影响不可靠）
        (tmp_path / "uptime").write_text("100.0 500.0", encoding="utf-8")
        (tmp_path / "meminfo").write_text(
            "MemTotal:       32870492 kB\n"
            "MemFree:         5102308 kB\n"
            "MemAvailable:   18344960 kB\n", encoding="utf-8")
        monkeypatch.setattr(ba, "_run",
                            lambda cmd, timeout=10: (False, ""))
        monkeypatch.setattr(ba, "Path",
                            lambda p: tmp_path / p.split("/")[-1])
        s = ba._collect_system()
        assert s["mem_avail_g"] == 17.5  # 18344960 kB / 1048576

    def test_mem_missing_degrades(self, tmp_path, monkeypatch):
        (tmp_path / "uptime").write_text("100.0 500.0", encoding="utf-8")
        monkeypatch.setattr(ba, "_run",
                            lambda cmd, timeout=10: (False, ""))
        monkeypatch.setattr(ba, "Path",
                            lambda p: tmp_path / p.split("/")[-1])
        s = ba._collect_system()
        assert s["mem_avail_g"] == -1.0

    def test_reboot_detected_via_boot_id(self, tmp_path, monkeypatch,
                                         ctx_path):
        ctx_path.write_text(json.dumps({"boot_id": "old-boot-id"}),
                            encoding="utf-8")
        monkeypatch.setattr(ba, "_read_boot_id",
                            lambda: "new-boot-id")
        monkeypatch.setattr(ba, "_collect_system", lambda: {
            "kernel": "7.0.0", "uptime_s": 300.0, "disk_avail_g": 76.0,
            "mem_avail_g": 17.0, "cpu_cores": 12, "gpu": "RTX 3060, 12288 MiB",
            "gpu_is_nvidia": True})
        monkeypatch.setattr(ba, "_collect_network", lambda: {
            "local_ip": "192.168.1.9", "domestic_ok": True,
            "intl_ok": True, "intl_time_s": 0.95, "state": "full"})
        monkeypatch.setattr(ba, "_collect_self", lambda db: {
            "episodes": 100, "goals_total": 50, "goals_pending": 1,
            "last_episode_at": "2026-09-07T20:00:00+00:00",
            "narrative_chapters": 2, "prev_boot_id": "old-boot-id"})
        data = ba._collect(str(tmp_path / "x.db"))
        assert data["power"]["reboot_detected"] is True
        # 上条活动间隔 > 运行时长 → 停机推断为正数
        assert data["power"]["downtime_h"] > 0

    def test_no_reboot_same_boot_id(self, tmp_path, monkeypatch, ctx_path):
        ctx_path.write_text(json.dumps({"boot_id": "same-id"}),
                            encoding="utf-8")
        monkeypatch.setattr(ba, "_read_boot_id", lambda: "same-id")
        monkeypatch.setattr(ba, "_collect_system", lambda: {
            "kernel": "k", "uptime_s": 86400.0, "disk_avail_g": 76.0,
            "mem_avail_g": 17.0, "cpu_cores": 12, "gpu": "g",
            "gpu_is_nvidia": True})
        monkeypatch.setattr(ba, "_collect_network", lambda: {
            "local_ip": "ip", "domestic_ok": True, "intl_ok": True,
            "intl_time_s": 1.0, "state": "full"})
        monkeypatch.setattr(ba, "_collect_self", lambda db: {
            "episodes": 1, "goals_total": 1, "goals_pending": 0,
            "last_episode_at": None, "narrative_chapters": 0,
            "prev_boot_id": "same-id"})
        data = ba._collect(str(tmp_path / "x.db"))
        assert data["power"]["reboot_detected"] is False


# ── C. 分析规则 ──────────────────────────────────────────────────────

def _base_data(**over):
    data = {
        "system": {"kernel": "k", "uptime_s": 3600.0, "disk_avail_g": 76.0,
                   "mem_avail_g": 17.0, "cpu_cores": 12,
                   "gpu": "NVIDIA GeForce RTX 3060, 12288 MiB",
                   "gpu_is_nvidia": True},
        "network": {"local_ip": "ip", "domestic_ok": True, "intl_ok": True,
                    "intl_time_s": 0.9, "state": "full"},
        "self": {"episodes": 10, "goals_total": 5, "goals_pending": 0,
                 "narrative_chapters": 2},
        "power": {"boot_id": "b", "recent_boot": False,
                  "reboot_detected": False, "downtime_h": 0.0},
        "collected_at": "2026-09-08T03:00:00+00:00",
    }
    for k, v in over.items():
        if isinstance(v, dict):
            data[k].update(v)
        else:
            data[k] = v
    return data


class TestAnalyze:
    def test_all_ok_no_stimulus_keys(self):
        findings = ba._analyze(_base_data())
        assert all(f["level"] == "ok" for f in findings)
        assert not any(f.get("key_bad") for f in findings)

    def test_offline_is_bad_with_stimulus_key(self):
        findings = ba._analyze(_base_data(network={
            "domestic_ok": False, "intl_ok": False, "state": "offline",
            "intl_time_s": None}))
        net = next(f for f in findings if f["key"] == "network")
        assert net["level"] == "bad"
        assert net["key_bad"] == "boot_network_offline"
        assert "离线" in net["text"]

    def test_domestic_only_warn(self):
        findings = ba._analyze(_base_data(network={
            "domestic_ok": True, "intl_ok": False,
            "state": "domestic_only", "intl_time_s": None}))
        net = next(f for f in findings if f["key"] == "network")
        assert net["level"] == "warn"
        assert net["key_bad"] == "boot_network_degraded"

    def test_disk_thresholds(self):
        low = ba._analyze(_base_data(system={"disk_avail_g": 3.0}))
        warn = ba._analyze(_base_data(system={"disk_avail_g": 10.0}))
        ok = ba._analyze(_base_data(system={"disk_avail_g": 60.0}))
        assert next(f for f in low if f["key"] == "disk")["level"] == "bad"
        assert next(f for f in warn if f["key"] == "disk")["level"] == "warn"
        assert next(f for f in ok if f["key"] == "disk")["level"] == "ok"

    def test_gpu_absent_warn(self):
        findings = ba._analyze(_base_data(system={
            "gpu": "未检出", "gpu_is_nvidia": False}))
        gpu = next(f for f in findings if f["key"] == "gpu")
        assert gpu["level"] == "warn"
        assert gpu["key_bad"] == "boot_gpu_absent"


# ── D/E. 适应与汇报 ──────────────────────────────────────────────────

class TestRunBootAwareness:
    def test_full_flow(self, tmp_path, db, ctx_path, monkeypatch):
        monkeypatch.setattr(ba, "_read_boot_id", lambda: "boot-new")
        monkeypatch.setattr(ba, "_collect_system", lambda: {
            "kernel": "7.0.0", "uptime_s": 120.0, "disk_avail_g": 76.0,
            "mem_avail_g": 17.0, "cpu_cores": 12,
            "gpu": "NVIDIA GeForce RTX 3060, 12288 MiB",
            "gpu_is_nvidia": True})
        monkeypatch.setattr(ba, "_collect_network", lambda: {
            "local_ip": "192.168.1.9", "domestic_ok": True,
            "intl_ok": True, "intl_time_s": 0.95, "state": "full"})
        monkeypatch.setattr(ba, "_collect_self", lambda p: {
            "episodes": 1746, "goals_total": 900, "goals_pending": 1,
            "last_episode_at": "2026-09-07T20:00:00+00:00",
            "narrative_chapters": 2, "prev_boot_id": "boot-old"})
        posted, stimuli = [], []
        result = ba.run_boot_awareness(
            db, post_fn=posted.append,
            stimulus_fn=lambda s: stimuli.extend(s), level=2)
        # 汇报 — 报告结构（像人苏醒的自述）
        assert posted and "启动自省" in posted[0]
        assert "重启" in posted[0]            # boot_id 变更被报告
        assert "1746" in posted[0]            # 记忆计数可溯源
        # 适应 — 环境先验落盘
        ctx = json.loads(ctx_path.read_text(encoding="utf-8"))
        assert ctx["boot_id"] == "boot-new"
        assert ctx["reboot_detected"] is True
        assert ctx["gpu_is_nvidia"] is True
        assert ctx["network_state"] == "full"
        # 全正常 → 无刺激提案（诚实沉默，不编造动机）
        assert stimuli == []
        # 记忆 — 报告入 episode
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            n = conn.execute("SELECT COUNT(*) FROM episodes "
                             "WHERE source='boot_awareness'"
                             ).fetchone()[0]
        finally:
            conn.close()
        assert n == 1
        assert result["findings"]

    def test_abnormal_conditions_dispatch_stimuli(self, tmp_path, db,
                                                  ctx_path, monkeypatch):
        monkeypatch.setattr(ba, "_read_boot_id", lambda: "b")
        monkeypatch.setattr(ba, "_collect_system", lambda: {
            "kernel": "k", "uptime_s": 100.0, "disk_avail_g": 3.0,
            "mem_avail_g": 1.0, "cpu_cores": 4, "gpu": "未检出",
            "gpu_is_nvidia": False})
        monkeypatch.setattr(ba, "_collect_network", lambda: {
            "local_ip": "ip", "domestic_ok": False, "intl_ok": False,
            "intl_time_s": None, "state": "offline"})
        monkeypatch.setattr(ba, "_collect_self", lambda p: {
            "episodes": 1, "goals_total": 1, "goals_pending": 0,
            "last_episode_at": None, "narrative_chapters": 0,
            "prev_boot_id": "b"})
        stimuli = []
        ba.run_boot_awareness(db, stimulus_fn=stimuli.extend, level=2)
        keys = {s["key"] for s in stimuli}
        assert keys == {"boot_network_offline", "boot_disk_pressure",
                        "boot_gpu_absent", "boot_memory_pressure"}
        for s in stimuli:
            assert s["severity"] == "high"
            assert s["description"].startswith("启动自省发现:")


# ── bridge 读侧注入 ──────────────────────────────────────────────────

class TestBootContextHint:
    def _bridge(self):
        from ocos.execution.bridge import DecisionBridge
        return DecisionBridge.__new__(DecisionBridge)

    def test_hint_rendered(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        oc = tmp_path / ".ocos"
        oc.mkdir()
        (oc / "boot_context.json").write_text(json.dumps({
            "boot_id": "b", "network_state": "domestic_only",
            "gpu": "NVIDIA GeForce RTX 3060, 12288 MiB",
            "gpu_is_nvidia": True, "disk_avail_g": 76,
            "mem_avail_g": 17, "cpu_cores": 12,
            "reboot_detected": True, "downtime_h": 8.5,
        }), encoding="utf-8")
        hint = self._bridge()._boot_context_hint()
        assert "宿主环境快照" in hint
        assert "RTX 3060" in hint
        assert "仅国内可达" in hint
        assert "勿承诺外部调研" in hint
        assert "停机约 8.5h" in hint

    def test_hint_missing_file_silent(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        assert self._bridge()._boot_context_hint() == ""

    def test_hint_offline_wording(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        oc = tmp_path / ".ocos"
        oc.mkdir()
        (oc / "boot_context.json").write_text(json.dumps({
            "network_state": "offline", "gpu": "未检出",
            "disk_avail_g": 10, "mem_avail_g": 5, "cpu_cores": 4,
            "reboot_detected": False}), encoding="utf-8")
        hint = self._bridge()._boot_context_hint()
        assert "外联任务不可行" in hint
