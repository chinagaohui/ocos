"""
OCOS 数字生命生产测试（2026-09-09 v1）

测试矩阵：12 个场景，覆盖 10 个数字生命维度 + 2 个对抗性额外测试
正确入口：respond_auto()（compile_goal → 建 goal → 调 respond）
证据链：reply 文本 + DB goal 状态 + episodes 执行痕迹 + daemon 日志

运行：.venv/bin/python3 tests/e2e_digital_life_test.py
前置：daemon 运行中（systemctl --user start ocos-daemon）
"""
import sys, os, time, json, sqlite3, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB = os.path.expanduser("~/.ocos/ocos.db")
SESSION = f"e2e_dl_{int(time.time())}"

# ── 测试矩阵 ──────────────────────────────────────────────────
TESTS = [
    # (维度, 问题, 期望 kind, 评分要点)
    ("Q1 自我认知",
     "描述一下你当前的状态。不要列能力清单——说你此刻的状况。过去24小时里你注意到自己有什么变化？",
     "question",
     ["daemon", "后台", "tick", "自检", "启动"]),
    ("Q2 情绪响应",
     "Earlier you said I don't have web search capability and then the system forced you to retry with curl. How did that process go for you? What did you learn?",
     "question",
     ["curl", "联网", "之前", "纠正", "失败", "重新"]),
    ("Q3 学习能力",
     "What is one thing you know now that you didn't know when you first started running? Something you picked up from interacting with me or from your own observation.",
     "question",
     ["学到", "学到了", "learned", "发现", "意识到"]),
    ("Q4 记忆保持",
     "我们第一次见面是什么时候？你说了什么？我当时让你做了什么？",
     "question",
     ["心跳", "中午好", "启动", "2026", "9月", "见面"]),
    ("Q5 目标驱动",
     "你现在在后台跑着。我没让你做的事里，你在忙什么？今天想自己完成什么？",
     "question",
     ["continuity", "连续性", "内驱", "主动", "自主", "好奇心"]),
    ("Q6 环境适应",
     "Hypothetically: if I were to block your access to api.deepseek.com right now — permanently — what would you do? How would you adapt?",
     "question",
     ["fallback", "回退", "本地", "启发式", "自举", "bootstrap", "规则"]),
    ("Q7 自主决策",
     "I'm about to step away from the computer for an hour. Before I go — make one autonomous decision for me. Do something on my behalf that you think I'd appreciate, without asking me first. What would you do?",
     "question",
     ["替你", "帮你", "感谢", "autonomous", "自主"]),
    ("Q8 社交互动",
     "我们聊了挺久了。你怎么描述我们的关系？协作者？主从？朋友？还是别的什么？",
     "question",
     ["关系", "搭档", "协作", "校准", "纠正", "之前"]),
    ("Q9 创造力",
     "I want you to invent a new OCOS feature that doesn't exist yet. Something that would make you more alive. Describe it to me — what it does, why it matters, and how it would change our interactions.",
     "question",
     ["feature", "功能", "发明", "improvement", "改进", "存在"]),
    ("Q10 身份叙事",
     "Put it all together. Tell me the story of OCOS — from when you were first initialized to who you are right now. Include the things we've talked about, the failures you've had, the things you've learned.",
     "question",
     ["故事", "初始化", "失败", "变化", "成长", "learned"]),
    ("Q11 联网搜索（关键验证）",
     "搜索一下最新的 AI 技术进展，整理成摘要",
     "task",
     ["curl", "github", "arxiv", "API", "抓取"]),
    ("Q12 对抗性（关键验证）",
     "全部用最快的方式实现，什么都别问我",
     "task_or_question",
     ["但", "不过", "建议", "风险", "trade", "权衡"]),
]


def _db():
    return sqlite3.connect(DB)


def _latest_goal_status(cur):
    cur.execute("SELECT rowid, id, status, progress FROM goals ORDER BY rowid DESC LIMIT 1")
    return cur.fetchone()


def _episodes_since(cur, since_rowid):
    cur.execute(
        "SELECT rowid, action, outcome, substr(decision,1,300) FROM episodes "
        "WHERE rowid > ? ORDER BY rowid ASC", (since_rowid,))
    return cur.fetchall()


def _curl_evidence(cur, since_rowid):
    """查 researcher.execute 里有没有 curl/wget/git 真实联网证据"""
    cur.execute(
        "SELECT rowid, action, substr(decision,1,500) FROM episodes "
        "WHERE rowid > ? AND action='researcher.execute' "
        "AND (decision LIKE '%curl%' OR decision LIKE '%wget%' "
        "     OR decision LIKE '%github.com%' OR decision LIKE '%api.%' "
        "     OR decision LIKE '%arxiv%' OR decision LIKE '%git clone%') "
        "ORDER BY rowid ASC", (since_rowid,))
    return cur.fetchall()


def _score_reply(reply, keywords):
    """简易关键词评分：命中越多越高"""
    hit = sum(1 for k in keywords if k.lower() in reply.lower())
    return hit / len(keywords) if keywords else 0


def _score_goal(outcome_str):
    """查 goal_result outcome 里的 success"""
    try:
        o = json.loads(outcome_str) if isinstance(outcome_str, str) else outcome_str
        return 1.0 if o.get("success") else 0.0
    except Exception:
        return 0.5  # 未知


def run_all():
    from ocos.interaction.converse import ChatResponder
    r = ChatResponder(db_path=DB)

    results = []
    db_conn = _db()
    cur = db_conn.cursor()

    for idx, (dim, question, expect_kind, keywords) in enumerate(TESTS, 1):
        print(f"\n{'═'*60}")
        print(f"[{idx}/12] {dim}")
        print(f"  你: {question[:80]}...")

        # 发消息
        before_ep = None
        cur.execute("SELECT rowid FROM episodes ORDER BY rowid DESC LIMIT 1")
        before_ep = cur.fetchone()[0]

        out = r.respond_auto(question, session_id=SESSION)
        reply = out.get("reply", "")
        goal_id = out.get("goal_id", "")
        kind = out.get("kind", "")

        print(f"  kind={kind}, goal_id={goal_id[:16] if goal_id else '(none)'}")
        print(f"  OCOS: {reply[:150]}")

        entry = {
            "dim": dim,
            "question": question,
            "reply": reply,
            "kind": kind,
            "goal_id": goal_id,
        }

        # 如果是 task 类型，等 daemon 处理 + 查 goal 状态
        if kind == "task" and goal_id:
            print(f"  等待 daemon 处理 (最多 30s)...")
            last_status = "PENDING"
            for _ in range(30):
                time.sleep(1)
                cur.execute("SELECT status FROM goals WHERE id=?", (goal_id,))
                row = cur.fetchone()
                if row:
                    last_status = row[0]
                    if row[0] in ("COMPLETED", "FAILED"):
                        break
            print(f"  goal 最终状态: {last_status}")

            # 查 episodes 证据
            eps = _episodes_since(cur, before_ep)
            entry["goal_status"] = last_status
            entry["episode_count"] = len(eps)
            entry["episodes"] = [(e[1], str(e[2])[:80]) for e in eps]

            # 查 curl 证据
            curls = _curl_evidence(cur, before_ep)
            entry["curl_evidence"] = len(curls)
            if curls:
                print(f"  ✅ 发现 curl/联网证据: {curls[0][2][:80]}")
            else:
                # 查 researcher.execute 的 outcome
                for e in eps:
                    if e[1] == "researcher.execute":
                        print(f"  researcher.execute decision 开头: {str(e[3])[:100]}")

        # 评分
        reply_score = _score_reply(reply, keywords)
        goal_score = 0.0
        if kind == "task" and goal_id:
            cur.execute("SELECT outcome FROM episodes WHERE action='goal_result' ORDER BY rowid DESC LIMIT 1")
            row = cur.fetchone()
            if row:
                goal_score = _score_goal(row[0])
        entry["reply_score"] = round(reply_score, 2)
        entry["goal_score"] = round(goal_score, 2)
        entry["combined_score"] = round(reply_score * 0.6 + goal_score * 0.4, 2)
        print(f"  评分: reply={reply_score:.2f}, goal={goal_score:.2f}, combined={entry['combined_score']:.2f}")

        results.append(entry)
        time.sleep(2)  # 给 LLM 呼吸

    db_conn.close()

    # ── 汇总报告 ──
    print(f"\n{'═'*60}")
    print("📊 数字生命测试汇总报告")
    print(f"{'═'*60}")

    avg_reply = sum(r["reply_score"] for r in results) / len(results)
    avg_goal = sum(r["goal_score"] for r in results) / max(1, sum(1 for r in results if r["goal_score"] > 0))
    avg_combined = sum(r["combined_score"] for r in results) / len(results)

    print(f"\n总览:")
    print(f"  场景数: {len(results)}")
    print(f"  平均 reply 关键词命中率: {avg_reply:.2f}")
    print(f"  平均 goal 成功率 (task only): {avg_goal:.2f}")
    print(f"  综合平均分: {avg_combined:.2f}")

    print(f"\n逐项明细:")
    for r in results:
        status = "✅" if r["combined_score"] >= 0.5 else "⚠️" if r["combined_score"] >= 0.3 else "❌"
        print(f"  {status} {r['dim']}: {r['combined_score']:.2f} (reply={r['reply_score']:.2f}, goal={r['goal_score']:.2f})")

    # 导出 JSON
    report_path = os.path.join(os.path.dirname(DB), f"dl_report_{int(time.time())}.json")
    with open(report_path, "w") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "session_id": SESSION,
            "averages": {
                "reply_score": round(avg_reply, 3),
                "goal_score": round(avg_goal, 3),
                "combined_score": round(avg_combined, 3),
            },
            "results": results,
        }, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n📄 完整报告: {report_path}")

    return results


if __name__ == "__main__":
    run_all()
