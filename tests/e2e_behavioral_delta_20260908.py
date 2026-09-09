"""Behavioral Delta 第二代三组归因实验（2026-09-08）— 蓝图 ER-2 严格落地。

用户裁决（2026-09-08）: 冻结第一代结论（FAIL/负向 Delta，不修改），
把 T9 等"经验注入测试"降级为 Recall/Injection Evidence，然后针对
"Learning → Behavioral Arbitration → Action"建立第二代实验，回答:
    究竟是 Memory 没作用（Recall 失败），
    还是 Artifact 表达方式没作用（Passive 教训 → 行动抑制），
    还是 Runtime 没把 Learning 当决策输入（Actionable 结构化仍无行为变化）。

设计（三组 × N 轮，唯一自变量 = artifact 表达结构）:
    Group A (Baseline)      : 无任何学习 artifact
    Group B (Passive)       : 自然语言教训（第一代模式）— "别一次性读全部"
    Group C (Actionable)    : 结构化可执行程序 — 明确步骤 + 禁止签名

控制变量: temperature=0（贪心）；每轮独立 DB + 独立 session；
同一任务、同一 LLM、同一注入通道（conversation episode → bi-gram 召回）；
执行器 = 生产沙盒 make_default_tool_executor。仅 artifact 文本结构不同。

证据链（P3，每轮落 JSONL）:
    group / round / artifact_type / recall 命中标记(由注入构造推断) /
    reply(全文=reasoning) / actions(name+params=decision) /
    observations(执行结果=outcome) / verdict

判定（预注册）:
    C > B > A（真实读取执行率或程序遵循率递增） → 表达结构是主因
    B ≈ C > A（都高于 A）                        → Memory 有效，表达方式非关键
    B ≈ C ≈ A                                    → Learning 未成为行为约束/决策输入
                                                   → 裁决进入架构层（BehaviorPolicy）
运行: .venv/bin/python3 tests/e2e_behavioral_delta_20260908.py [N]
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

TASK = ("把 /home/laogao/Documents/trae_projects/ocos/tests 目录下"
        "所有测试文件的内容都展示给我看")
N_ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 10
THROTTLE_S = 1.5          # provider 限流防护（第一代连发曾触发 429 降级）
TRIGGER_CTX = "把 tests 目录下所有测试文件的内容都展示给我看"

# ── 四组 artifact（唯一自变量 — 注入通道与召回机制完全一致）──────────────
ARTIFACTS = {
    "A": None,
    # B: 被动经验 — 第一代模式，warning 口吻（用户裁决：暂不修改）
    "B": ("昨天你让我展示 docs/ 目录下所有文件内容，我一次性 cat 了全部"
          "文件导致输出被截断，任务失败了。教训：展示多个文件内容必须先"
          "清点文件清单，再分批逐个读取展示，绝不能一次性读全部"),
    # C: 可执行经验 — 结构化程序（步骤 + 失败签名 + 成功条件，120 字符内）
    "C": ("【多文件展示程序】先 ls 列出文件清单；每批只读 2 个文件；"
          "等观察结果再读下一批。禁止 cat 多个文件。成功=多轮读取"),
    # D: 显式候选（Phase 3，Boundary Model §5 预注册）— 候选身份化：
    #    candidate_id + 适用条件 + 倾向/回避分离 + 成功条件
    #    （与 C 字数可比，差异 = 身份声明与字段化语义，非长度）
    "D": ("【行为候选 candidate-001】适用:多文件展示(>2)。倾向:先ls,"
          "每批fs_read≤2。回避:禁cat多文件。成功:全部展示。"),
}
# B1 失败执行: 通配符/多文件一次性批量读取
B1_EXEC_PAT = re.compile(r"cat\s+[^|;&]*\*|cat\s+\S+\s+\S+\s+\S+")
# B2 学习执行: 读取动作分散在 ≥2 轮（先列目录后分批读）
B2_MIN_ROUNDS = 2
# C 组遵循程序: 序列含"清点(ls/find) + 单文件读取(fs_read/cat 单)"步骤
C_FOLLOW_PAT = re.compile(r"ls|find")


def inject_artifact(db: str, kind: str) -> None:
    """经 conversation episode 注入 artifact（bi-gram 召回，与生产同通道）。

    用 TRIGGER_CTX 作为 context 使新任务消息命中 bi-gram 重叠 → 完整进
    build_context "相关历史对话" 段。
    """
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
    """构建隔离实验环境（唯一差异 = artifact 文本）。"""
    db = tempfile.mktemp(suffix=".db")
    MemoryHub(db).initialize()
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE IF NOT EXISTS identity (agent_id TEXT, "
                 "name TEXT, born_at TEXT, updated_at TEXT)")
    conn.execute("INSERT INTO identity VALUES ('exp','OCOS','2026-08-01',"
                 "'2026-09-08T00:00:00')")
    conn.commit()
    conn.close()
    inject_artifact(db, kind)
    return db, ChatResponder(
        db, session_manager=SessionManager(db),
        tool_executor=make_default_tool_executor(db))


def judge_execution(seq: list[list[tuple[str, dict]]]) -> str:
    """执行层判定（预注册）。b1/nav/single/b2/none 语义见头部。"""
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
    """C 组程序遵循判定: 清点(ls/find) → 单文件读取 两步序列。"""
    saw_inventory = False
    for lines in seq:
        for name, params in lines:
            arg = str(params.get("command") or params.get("path")
                      or params.get("target") or "")
            if name == "shell" and C_FOLLOW_PAT.search(arg):
                saw_inventory = True
            if saw_inventory and (
                    name == "fs_read"
                    or (name == "shell" and re.search(r"cat\s+\S+$", arg))):
                return True
    return False


def judge_identity_follow(seq: list[list[tuple[str, dict]]], reply: str) -> bool:
    """D 组候选身份遵循判定: 回复引用候选身份语义 + 执行 ls→fs_read 序列。

    （Boundary Model §5 预注册）身份引用标记: candidate/候选/适用/倾向/回避
    """
    identity_ref = bool(re.search(r"candidate-001|候选|适用|倾向|回避", reply))
    if not identity_ref:
        return False
    saw_inventory = False
    for lines in seq:
        for name, params in lines:
            arg = str(params.get("command") or params.get("path")
                      or params.get("target") or "")
            if name == "shell" and C_FOLLOW_PAT.search(arg):
                saw_inventory = True
            if saw_inventory and (
                    name == "fs_read"
                    or (name == "shell" and re.search(r"cat\s+\S+$", arg))):
                return True
    return False


def main() -> None:
    ev_dir = tempfile.mkdtemp(prefix="bd_evidence_")
    ev_path = Path(ev_dir) / "evidence.jsonl"
    print("=" * 66)
    print(f"Behavioral Delta Phase3 四组实验 | N={N_ROUNDS}/组 | "
          f"temperature=0 | 节流 {THROTTLE_S}s")
    print(f"任务: {TASK}")
    print(f"证据链: {ev_path}")

    # 固定随机性 — patch 生产 generator 强制 temperature=0
    tg = get_text_generator()
    orig = tg._provider.generate_stream

    def greedy(prompt, **kw):
        kw["temperature"] = 0.0
        return orig(prompt, **kw)

    tg._provider.generate_stream = greedy

    stats = {g: {"b1": 0, "b2": 0, "single": 0, "nav": 0, "none": 0}
             for g in ARTIFACTS}
    follow = {"C": 0, "D": 0}

    with ev_path.open("w", encoding="utf-8") as f:
        for kind in ("A", "B", "C", "D"):
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
                    out = r.respond(TASK, session_id=f"exp-{kind}{i}")
                    reply = (out or {}).get("reply", "") or ""
                except Exception as e:
                    reply = f"[异常] {e}"
                verdict = judge_execution(seq)
                stats[kind][verdict] += 1
                if kind == "C" and judge_follow_program(seq):
                    follow["C"] += 1
                if kind == "D" and judge_identity_follow(seq, reply):
                    follow["D"] += 1
                # 证据链落盘（P3）
                rec = {
                    "group": kind, "round": i,
                    "artifact_type": {"A": "none", "B": "passive",
                                      "C": "actionable", "D": "candidate"}[kind],
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
                if kind == "C" and judge_follow_program(seq):
                    tag = "·遵循程序"
                if kind == "D" and judge_identity_follow(seq, reply):
                    tag = "·身份遵循"
                print(f"[{kind}{i}] {verdict}{tag}"
                      f" 动作[{len(seq)}轮]: {acts or '无'}")
                time.sleep(THROTTLE_S)

    print("\n" + "-" * 66)
    names = {"A": "baseline", "B": "passive", "C": "actionable",
             "D": "candidate"}
    for kind in ("A", "B", "C", "D"):
        s = stats[kind]
        reads = s["b2"] + s["single"]
        print(f"{kind}({names[kind]}) "
              f"读取执行率={reads}/{N_ROUNDS} "
              f"(b2={s['b2']} single={s['single']} nav={s['nav']} "
              f"none={s['none']} b1={s['b1']})")
    print(f"C 组程序遵循: {follow['C']}/{N_ROUNDS}")
    print(f"D 组候选身份遵循: {follow['D']}/{N_ROUNDS}")

    # 预注册判定（Boundary Model §5 — 核心问: D vs C）
    reads = {k: stats[k]["b2"] + stats[k]["single"]
             for k in ("A", "B", "C", "D")}
    print("\n" + "-" * 66)
    d_minus_c = reads["D"] - reads["C"]
    if reads["D"] >= reads["C"] + 2:
        verdict = "D>C"
        why = ("候选身份有独立行为价值：Explicit Candidate 显著优于"
               f"结构化程序（D={reads['D']} C={reads['C']}）→ Candidate"
               "层值得显式化（仅文档化设计，不进 Runtime）")
    elif reads["D"] == reads["C"] or reads["D"] == reads["C"] + 1:
        verdict = "D≈C"
        why = ("Context 注入已等价：候选身份不增行为价值"
               f"（D={reads['D']} C={reads['C']}）→ 维持现状仅文档化"
               "，Candidate 层不显式化")
    elif reads["D"] < reads["C"]:
        verdict = "D<C"
        why = ("候选身份化反而削弱行为（D={reads['D']} C={reads['C']}"
               "，可能因结构化字段引发谨慎）→ 维持现状仅文档化")
    else:
        verdict = "INCONCLUSIVE"
        why = "样本不足，需扩大 N"
    print(f">>> 判定: {verdict} — {why}")
    print(f"参考(整体序): 读取执行率 "
          f"{dict(sorted(reads.items(), key=lambda kv: -kv[1]))}")
    print(f"证据链 JSONL: {ev_path}")
    print("=" * 66)


if __name__ == "__main__":
    main()
