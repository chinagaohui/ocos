"""OCOS CLI — feedback 命令（S8 C3：评审反馈回流到 OCOS 记忆）。"""

from __future__ import annotations

from ocos.opentale_bridge.feedback_reflux import FeedbackReflux
from ocos.opentale_bridge.organ_client import OrganClientError


def cmd_feedback(args, session) -> int:
    """ocos feedback <project> — 收集评审反馈并写入 OCOS 记忆。"""
    reflux = FeedbackReflux(organ_base=getattr(args, "base_url", "http://127.0.0.1:8000/api/organ"))
    try:
        fb = reflux.collect_and_store(args.project)
    except OrganClientError as e:
        print(f"Organ 调用失败: {e}")
        return 1
    if fb.get("status") == "error":
        print(f"收集失败: {fb.get('detail')}")
        return 1
    print(f"反馈已回流到 OCOS 记忆（~/.ocos/feedback/{args.project}.json）:")
    print(f"  项目   : {fb['project']}")
    print(f"  章节   : {fb.get('chapters')}")
    print(f"  评审分 : {fb.get('book_review_score')}")
    print(f"  角色   : {'、'.join(fb.get('characters', []) or []) or '无'}")
    issues = fb.get("issues", []) or []
    if issues:
        print(f"  待改进 : {len(issues)} 项")
        for i in issues[:5]:
            print(f"    · {str(i.get('message', i))[:80]}")
    return 0
