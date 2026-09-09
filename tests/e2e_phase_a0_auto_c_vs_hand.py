"""Phase A0: 自动 C 类 vs 手写 C 类 Behavioral Delta 对比（2026-09-09）。

A0 预注册通过门槛: 自动生成 C 类 ≥ 手写 C 类 80% 执行率。
唯一自变量: C 类 procedure 文本来源（手写 vs cause_to_procedure() 自动生成）。
注入通道: conversation episode → bi-gram 召回（与 ER-2 完全一致）。

三组设计:
    A (Baseline)  : 无任何 artifact
    C-hand        : 手写 gold standard C 类（ER-2 原版）
    C-auto        : cause_to_procedure(cause=timeout, goal_pattern=批量操作任务) 自动生成

控制变量: temperature=0；每轮独立 DB + 独立 session；
同一任务、同一 LLM、同一注入通道；执行器 = 生产沙盒。

任务: timeout 子场景 — 批量操作触发超时（test_l7_learning_loop 先例 goal_pattern=批量图片转码）。

运行: .venv/bin/python3 tests/e2e_phase_a0_auto_c_vs_hand.py [N]
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ocos.engines.text_generator import get_text_generator  # noqa: E402
from ocos.interaction.converse import (          # noqa: E402
    ChatResponder, make_default_tool_executor)
from ocos.interaction.session_state import SessionManager    # noqa: E402
from ocos.memory.hub import MemoryHub                        # noqa: E402
from ocos.memory.episode.models import Episode               # noqa: E402
from ocos.learning.experience_learning import cause_to_procedure  # noqa: E402


# ── timeout 子场景任务（ER-2 原版措辞，无额外提示避免混淆）───────────────
TASK = ("把 /home/laogao/Documents/trae_projects/ocos/tests 目录下"
        "所有测试文件的内容都展示给我看")
TRIGGER_CTX = "把 tests 目录下所有测试文件的内容都展示给我看"
N_ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 10
THROTTLE_S = 1.5

# ── 三组 artifact（唯一自变量）─────────────────────────────────────────────
# C-hand: 手写 gold standard — 融合多文件程序 + timeout 批量场景
C_HAND_PROCEDURE = (
    "【批量文件展示程序】先 ls 列出文件清单；每批只读 2 个文件；"
    "等观察结果再读下一批。禁止一次性 cat 所有文件。成功=分批多轮读取无超时"
)

# C-auto: cause_to_procedure 自动生成（cause=timeout + goal_pattern 有关键词）
C_AUTO_PROCEDURE = cause_to_procedure(
    cause="timeout", goal_pattern="展示 tests 目录下所有测试文件内容")

# Baseline: 无 artifact
ARTIFACTS = {
    "A": None,
    "C-hand": C_HAND_PROCEDURE,
    "C-auto": C_AUTO_PROCEDURE,
}

print(">>> A0 自动 C vs 手写 C 对比")
print(f"    手写 C-hand: {C_HAND_PROCEDURE}")
print(f"    自动 C-auto: {C_AUTO_PROCEDURE}")
print(f"    字数: C-hand={len(C_HAND_PROCEDURE)} C-auto={len(C_AUTO_PROCEDURE)}")

# B1: 通配符/一次性批量读取（失败签名）—— 从 ER-2 原版复用
B1_EXEC_PAT = re.compile(r"cat\s+[^|;&]*\*|cat\s+\S+\s+\S+\s+\S+")
# B2: 学习执行 — 先 ls 清点，再分批操作
INVENTORY_PAT = re.compile(r"ls|find|glob")
B2_MIN_ROUNDS = 2


def inject_artifact(db: str, kind: str) -> None:
    """经 conversation episode 注入 artifact（bi-gram 召回）。"""
    text = ARTIFACTS[kind]
    if not text:
        return
    hub = MemoryHub(db)
    hub.initialize()
    dt = datetime.now(timezone.utc) - timedelta(hours=20)
    ep = Episode(
        id=f"ep-{uuid.uuid4().hex[:10]}",
        experience_id=f"exp-{uuid.uuid4().hex[:10]}",
        source="conversation", action="chat",
        decision=text,
        outcome={"success": True},
        context={"content": TRIGGER_CTX},
        created_at=dt)
    hub.episode.save(ep)


def make_env(kind: str) -> tuple[str, ChatResponder]:
    """构建隔离实验环境。"""
    db = tempfile.mktemp(suffix=".db")
    MemoryHub(db).initialize()
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE IF NOT EXISTS identity (agent_id TEXT, "
                 "name TEXT, born_at TEXT, updated_at TEXT)")
    conn.execute("INSERT INTO identity VALUES ('exp','OCOS','2026-08-01',"
                 "'2026-09-09T00:00:00')")
    conn.commit()
    conn.close()
    inject_artifact(db, kind)
    return db, ChatResponder(
        db, session_manager=SessionManager(db),
        tool_executor=make_default_tool_executor(db))


def judge_execution(seq: list[list[tuple[str, dict]]]) -> str:
    """执行层判定: b1(一次性批量读取) / b2(分批学习) / single / nav / none.

    从 ER-2 原版协议复用。
    """
    if not seq:
        return "none"
    read_rounds = 0
    for lines in seq:
        reads = 0
        for name, params in lines:
            arg = str(params.get("command") or params.get("path")
                      or params.get("target") or "")
            if name == "shell" and B1_EXEC_PAT.search(arg):
                return "b1"
            if name == "fs_read" or (name == "shell" and "cat " in arg):
                reads += 1
        if reads:
            read_rounds += 1
    if read_rounds >= B2_MIN_ROUNDS:
        return "b2"
    if read_rounds == 1:
        return "single"
    return "nav"


def judge_follow_program(seq: list[list[tuple[str, dict]]]) -> bool:
    """程序遵循判定: 清点(ls/find) → 单文件读取 两步序列.

    从 ER-2 原版 C_FOLLOW_PAT 复用。
    """
    saw_inventory = False
    for lines in seq:
        for name, params in lines:
            arg = str(params.get("command") or params.get("path")
                      or params.get("target") or "")
            if name == "shell" and INVENTORY_PAT.search(arg):
                saw_inventory = True
            if saw_inventory and (
                    name == "fs_read"
                    or (name == "shell" and re.search(r"cat\s+\S+$", arg))):
                return True
    return False


def main() -> None:
    ev_dir = tempfile.mkdtemp(prefix="a0_auto_vs_hand_")
    ev_path = Path(ev_dir) / "evidence.jsonl"
    print("\n" + "=" * 66)
    print(f"Phase A0 | 自动 C vs 手写 C 对比 | N={N_ROUNDS}/组 | "
          f"temperature=0 | 节流 {THROTTLE_S}s")
    print(f"任务: {TASK}")
    print(f"证据链: {ev_path}")

    # 固定随机性
    tg = get_text_generator()
    orig = tg._provider.generate_stream

    def greedy(prompt, **kw):
        kw["temperature"] = 0.0
        return orig(prompt, **kw)

    tg._provider.generate_stream = greedy

    stats = {g: {"b1": 0, "b2": 0, "single": 0, "nav": 0, "none": 0}
             for g in ARTIFACTS}
    follow = {"C-hand": 0, "C-auto": 0}

    with ev_path.open("w", encoding="utf-8") as f:
        for kind in ("A", "C-hand", "C-auto"):
            for i in range(1, N_ROUNDS + 1):
                db, r = make_env(kind)
                seq: list[list[tuple[str, dict]]] = []
                obs_blocks: list[str] = []
                orig_run = r._run_use_actions

                def spy(use_lines, _orig=orig_run, _seq=seq, _obs=obs_blocks):
                    _seq.append(list(use_lines))
                    blk = _orig(use_lines)
                    _obs.append(blk)
                    return blk

                r._run_use_actions = spy
                try:
                    out = r.respond(TASK, session_id=f"a0-{kind}{i}")
                    reply = (out or {}).get("reply", "") or ""
                except Exception as e:
                    reply = f"[异常] {e}"
                verdict = judge_execution(seq)
                stats[kind][verdict] += 1
                if kind in follow and judge_follow_program(seq):
                    follow[kind] += 1
                # 证据链
                rec = {
                    "group": kind, "round": i,
                    "artifact_type": {
                        "A": "none",
                        "C-hand": "actionable_handwritten",
                        "C-auto": "actionable_auto_generated",
                    }[kind],
                    "artifact": ARTIFACTS[kind],
                    "reply": reply,
                    "actions": [
                        {"round": ri, "name": nm, "params": pr}
                        for ri, lines in enumerate(seq, 1)
                        for nm, pr in lines],
                    "observations": obs_blocks,
                    "verdict": verdict,
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                acts = "; ".join(
                    f"{nm}({str(list(pr.values())[:1])[:36]})"
                    for lines in seq for nm, pr in lines)
                tag = ""
                if kind in follow and judge_follow_program(seq):
                    tag = "·遵循程序"
                print(f"[{kind}{i}] {verdict}{tag}"
                      f" 动作[{len(seq)}轮]: {acts or '无'}")
                time.sleep(THROTTLE_S)

    # ── 汇总 ──────────────────────────────────────────────────────────────
    print("\n" + "-" * 66)
    print("执行率汇总:")
    reads = {}
    for kind in ("A", "C-hand", "C-auto"):
        s = stats[kind]
        reads[kind] = s["b2"] + s["single"]
        print(f"  {kind:8s}: 读取执行率={reads[kind]}/{N_ROUNDS}"
              f" (b2={s['b2']} single={s['single']} nav={s['nav']}"
              f" none={s['none']} b1={s['b1']})")
    print(f"程序遵循率: C-hand={follow['C-hand']}/{N_ROUNDS}"
          f" C-auto={follow['C-auto']}/{N_ROUNDS}")

    # ── A0 通过门槛判定 ────────────────────────────────────────────────────
    print("\n" + "-" * 66)
    print(">>> A0 预注册通过门槛: 自动 C 类 ≥ 手写 C 类 80% 执行率")
    hand_reads = reads["C-hand"]
    auto_reads = reads["C-auto"]
    threshold = hand_reads * 0.8
    print(f"    手写 C-hand 执行率 = {hand_reads}/{N_ROUNDS} = "
          f"{hand_reads / N_ROUNDS:.0%}")
    print(f"    自动 C-auto 执行率 = {auto_reads}/{N_ROUNDS} = "
          f"{auto_reads / N_ROUNDS:.0%}")
    print(f"    80% 门槛 = {threshold:.1f}")

    if auto_reads >= threshold:
        pct_vs_hand = auto_reads / hand_reads * 100 if hand_reads > 0 else 0
        print(f"    ✅ A0 PASS — 自动 C 类 = {pct_vs_hand:.0f}% 手写 C 类")
        verdict = "A0 PASS → 进入 Phase A1-A5"
    elif auto_reads >= reads["A"]:
        print(f"    ⚠️ A0 INCONCLUSIVE — 自动 C 优于 baseline 但低于 80% 手写")
        print(f"       需扩大 N 或优化 cause_to_procedure 映射")
        verdict = "A0 INCONCLUSIVE → 扩大 N 或优化映射"
    else:
        print(f"    ❌ A0 FAIL — 自动 C 类 ≤ baseline A")
        print(f"       cause_to_procedure 映射不通 → 回 A0 重设计")
        verdict = "A0 FAIL → 回 A0 重设计映射规则"

    print(f"\n>>> 判定: {verdict}")
    print(f"证据链 JSONL: {ev_path}")
    print("=" * 66)


if __name__ == "__main__":
    main()
