"""COG-V2 Phase 3.2 — 成功配方沉淀（程序记忆，确定性，零 LLM）。

同一"工具姿势"（agent × 首命令词）在近 7 天成功 ≥2 次 → 用确定性模板
生成一条 tool_recipe 知识，经 UnifiedIngestor 入库（knowledge_type=
procedure），RecallRouter 的 procedural 子库随后可召回进工作空间。

与 failure_lesson / mutation_policy 的关系：
    failure_lesson  = "哪条路走不通"（约束性，硬否决）；
    tool_recipe     = "哪条路走通过、走通过几次"（建设性，正面前验）。

幂等/防泛滥：
    - 每个 (agent, tool) 签名在 RECIPE_TTL_DAYS 内最多沉淀一次
      （以 source='recipe_sediment' 的 tool_recipe episode 为持久对账，
      跨重启有效）；TTL 过后成功样本仍在 → 刷新一条（天然支持衰减）；
    - 内容去重再交 ingestor content_key 兜一道；
    - 单次 dream 最多产出 MAX_RECIPES_PER_RUN 条。
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 7
RECIPE_TTL_DAYS = 30
MIN_SUCCESS = 2
MAX_RECIPES_PER_RUN = 3

# 命令行提取：执行回显/输出中的 "$ cmd args" 行
_CMD_RE = re.compile(r"(?:^|\n)\s*\$\s+([A-Za-z0-9_./-]+)(?:\s+([^\n]{0,60}))?")
_TASK_TYPE_RULES = (
    ("research", re.compile(r"检索|搜索|调研|查阅|文献|论文|资料|research|search|arxiv", re.I)),
    ("build", re.compile(r"开发|构建|实现|编写|部署|代码|脚本|build|implement|deploy", re.I)),
    ("analysis", re.compile(r"分析|评估|诊断|复盘|总结|统计|analy[sz]e|review|audit", re.I)),
    ("file", re.compile(r"文件|目录|读取|写入|备份|file|path|目录", re.I)),
)
_TASK_TYPE_ZH = {"research": "检索调研", "build": "开发构建",
                 "analysis": "分析评估", "file": "文件操作",
                 "general": "通用"}

# 确定性复用要点（工具语义稳定，无需 LLM 概括）
_TOOL_HINTS = {
    "curl": "先确认域名可达与网络状态，加超时/失败重试，注意 API 限流",
    "wget": "先确认 URL 可达，加超时与输出路径，失败看 HTTP 状态码",
    "python3": "先确认模块可用，涉及数据库先探测 schema 再写查询",
    "git": "先看 status/diff 确认工作区，只做只读检查或已授权写操作",
    "ls": "只读列目录安全；路径不存在先核实再换路径",
    "grep": "先缩小目录范围，注意正则词边界避免误匹配",
    "sqlite3": "先 .schema 探表，查询加 LIMIT，写操作前备份",
    "journalctl": "用 --since/--unit 收窄时间与服务范围",
    "systemctl": "先 status 看现状，重启后轮日志确认 boot 干净",
}
_GENERIC_HINT = "先做只读探测确认环境与路径，再执行实质动作；失败立即换路不重试同姿势"


class RecipeSedimentor:
    """扫描成功 episode → 确定性配方知识。"""

    def __init__(self, db_path: str, ingestor: Any = None) -> None:
        self._db_path = db_path
        self._ingestor = ingestor

    def maybe_sediment(
        self,
        *,
        now: Optional[datetime] = None,
        ingestor: Any = None,
    ) -> dict:
        """主入口；返回统计 {candidates, sedimented, skipped, recipes}。"""
        now = now or datetime.now(timezone.utc)
        ingestor = ingestor or self._ingestor
        stats = {"candidates": 0, "sedimented": 0, "skipped": 0,
                 "recipes": []}
        try:
            groups = self._collect_success_groups(now)
            stats["candidates"] = len(groups)
            fresh = self._filter_fresh_signatures(groups, now)
            for sig, eps in fresh[:MAX_RECIPES_PER_RUN]:
                statement = self._render_recipe(sig, eps)
                if not statement:
                    stats["skipped"] += 1
                    continue
                if ingestor is None:
                    # dry-run：不写对账 marker，否则会误封生产沉淀
                    stats["skipped"] += 1
                    continue
                ok = self._ingest(ingestor, sig, statement)
                # marker 必须如实记录入库结果：stored=false 的 marker
                # 不参与 TTL 去重，下个 dream 周期会重试（防镜像写失败
                # 时配方静默丢失，见 COG-V2 Phase3 生产首跑教训）。
                self._record_marker(sig, eps, now=now, stored=ok)
                if ok:
                    stats["sedimented"] += 1
                    stats["recipes"].append(statement[:120])
                else:
                    stats["skipped"] += 1
        except Exception as e:  # noqa: BLE001 — dream 附属流程，不阻断巩固
            logger.debug("recipe sediment failed: %s", e, exc_info=True)
        return stats

    # ── 收集：近 7 天成功执行 episode，按 (agent, tool) 聚合 ────────────

    def _collect_success_groups(self, now: datetime) -> dict[tuple, list[dict]]:
        since = (now - timedelta(days=LOOKBACK_DAYS)).isoformat()
        conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT id, action, goal, decision, context FROM episodes "
                "WHERE action LIKE '%.execute' "
                "AND json_extract(context, '$.success') = 1 "
                "AND created_at >= ? ORDER BY rowid DESC LIMIT 400",
                (since,)).fetchall()
        finally:
            conn.close()
        groups: dict[tuple, list[dict]] = defaultdict(list)
        for r in rows:
            try:
                ctx = json.loads(r["context"] or "{}")
            except ValueError:
                ctx = {}
            if not isinstance(ctx, dict) or ctx.get("success") is not True:
                continue
            agent = str(ctx.get("agent")
                        or (r["action"] or "").split(".")[0] or "?")
            text = f"{r['decision'] or ''}\n{ctx.get('output_excerpt') or ''}"
            tool, posture = self._extract_tool(text, agent)
            # 必须有真实命令证据：提不到首命令词（tool 退化为 agent 名）
            # 的子 agent LLM 输出不含"工具姿势"，不沉淀（生产实证：近 7 天
            # *.execute 多为结论摘要，回退会产生 "writer 用 writer 成功"
            # 这类零信息配方）。
            if not tool or tool == agent:
                continue
            desc = str(ctx.get("description") or r["goal"] or "")
            groups[(agent, tool)].append({
                "id": r["id"], "desc": desc, "posture": posture,
            })
        # 去重同 episode（一条记录只计一次）
        for sig, eps in list(groups.items()):
            uniq = {e["id"]: e for e in eps}
            if len(uniq) < MIN_SUCCESS:
                del groups[sig]
            else:
                groups[sig] = list(uniq.values())
        return dict(groups)

    @staticmethod
    def _extract_tool(text: str, agent: str) -> tuple[str, str]:
        """从回显中提首命令词与代表姿势（2 token 前缀）；提不到用 agent 名。"""
        for m in _CMD_RE.finditer(text or ""):
            tool, args = m.group(1), (m.group(2) or "").strip()
            base = tool.rsplit("/", 1)[-1]      # /usr/bin/python3 → python3
            if base in ("sudo", "xargs", "env", "time", "nohup"):
                continue
            posture = (f"{base} {args.split()[0]}" if args else base).strip()
            return base, posture[:48]
        # 无命令回显（如 sub-agent 直接返回）→ 姿势 = agent 本身
        return (agent, agent) if agent and agent != "?" else ("", "")

    # ── 新鲜度：签名 TTL 内只沉淀一次 ──────────────────────────────────

    def _filter_fresh_signatures(
        self, groups: dict[tuple, list[dict]], now: datetime
    ) -> list[tuple]:
        """返回 TTL 内未沉淀过的 (sig, eps)，按成功次数降序。"""
        since = (now - timedelta(days=RECIPE_TTL_DAYS)).isoformat()
        try:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
            try:
                rows = conn.execute(
                    "SELECT context FROM episodes "
                    "WHERE action='tool_recipe' AND source='recipe_sediment' "
                    "AND created_at >= ?", (since,)).fetchall()
            finally:
                conn.close()
        except sqlite3.Error:
            return []
        recent: set[tuple] = set()
        for (ctx_raw,) in rows:
            try:
                ctx = json.loads(ctx_raw or "{}")
            except ValueError:
                continue
            # stored=false 的 marker 是失败留痕，不构成 TTL 封条 —
            # 允许下个周期重试该签名。
            if not ctx.get("stored"):
                continue
            recent.add((str(ctx.get("agent")), str(ctx.get("tool"))))
        fresh = [sig for sig in groups if sig not in recent]
        fresh.sort(key=lambda s: len(groups[s]), reverse=True)
        return [(sig, groups[sig]) for sig in fresh]

    # ── 确定性模板 ─────────────────────────────────────────────────────

    def _render_recipe(self, sig: tuple, eps: list[dict]) -> str:
        agent, tool = sig
        task_type = self._dominant_task_type(eps)
        posture = Counter(e["posture"] for e in eps).most_common(1)[0][0]
        n = len(eps)
        hint = _TOOL_HINTS.get(tool, _GENERIC_HINT)
        return (
            f"【工具配方】{agent} 处理{_TASK_TYPE_ZH[task_type]}类任务时，"
            f"`{posture}` 姿势近 {LOOKBACK_DAYS} 天成功 {n} 次。"
            f"复用要点：{hint}。"
        )

    @staticmethod
    def _dominant_task_type(eps: list[dict]) -> str:
        cnt: Counter = Counter()
        for e in eps:
            text = e.get("desc", "")
            for name, rx in _TASK_TYPE_RULES:
                if rx.search(text):
                    cnt[name] += 1
                    break
            else:
                cnt["general"] += 1
        return cnt.most_common(1)[0][0]

    # ── 入库（走 ingestor 质量门）──────────────────────────────────────

    def _ingest(self, ingestor: Any, sig: tuple, statement: str) -> bool:
        try:
            from ocos.learning.unified_ingestor import (
                IngestArtifact, SourceChannel,
            )
            agent, tool = sig
            art = IngestArtifact(
                channel=SourceChannel.EXPERIENCE,
                content=statement,
                title=f"工具配方 {agent}/{tool}",
                confidence=0.75,
                tags=["tool_recipe", "recipe", str(agent), str(tool)],
                knowledge_type="procedure",
                metadata={"recipe_signature": f"{agent}:{tool}",
                          "agent": agent, "tool": tool},
            )
            results = ingestor.ingest([art], owner="recipe_sedimentor")
        except Exception as e:  # noqa: BLE001
            logger.info("recipe ingest failed: %s", e)
            return False
        if not results:
            return False
        status_val = getattr(getattr(results[0], "status", None), "value",
                             getattr(results[0], "status", None))
        # stored：新落盘；duplicate：同 content_key 已存在 — 两者都以
        # knowledge 行实际存在为准（镜像 fail-open 时 stored 也可能没行）。
        if status_val not in ("stored", "duplicate"):
            return False
        return self._row_exists(art.content_key)

    def _row_exists(self, unit_id: str) -> bool:
        try:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro",
                                   uri=True)
            try:
                row = conn.execute(
                    "SELECT 1 FROM knowledge WHERE id = ?", (unit_id,)
                ).fetchone()
            finally:
                conn.close()
            return row is not None
        except sqlite3.Error:
            # 核验本身失败时不堵沉淀（ingestor 已确认 stored）
            return True

    def _record_marker(self, sig: tuple, eps: list[dict], *,
                       now: datetime, stored: bool) -> None:
        """沉淀对账 episode — TTL/计数/审计的持久依据。"""
        agent, tool = sig
        # 原生 SQL 直写（learning 包不允许 import memory.episode）。
        try:
            import sqlite3 as _sql
            conn = _sql.connect(self._db_path, timeout=10)
            try:
                conn.execute(
                    """
                    INSERT INTO episodes (
                        id, experience_id, session_id, context, goal,
                        decision, action, outcome, condition,
                        significance_score, evaluation_trace, source,
                        status, tags, created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        f"EPI-RECIPE-{uuid.uuid4().hex[:12]}",
                        f"EXP-RECIPE-{uuid.uuid4().hex[:8]}",
                        "recipe_sediment",
                        json.dumps({"kind": "tool_recipe", "agent": agent,
                                    "tool": tool, "success_n": len(eps),
                                    "stored": stored}, ensure_ascii=False),
                        f"tool_recipe:{agent}:{tool}",
                        f"recipe sediment {agent}/{tool} n={len(eps)} "
                        f"stored={stored}",
                        "tool_recipe",
                        json.dumps({"success": stored, "agent": agent,
                                    "tool": tool, "success_n": len(eps)},
                                   ensure_ascii=False),
                        "",
                        0.5,
                        "{}",
                        "recipe_sediment",
                        "active",
                        json.dumps(["tool_recipe", "recipe", str(agent),
                                    str(tool)], ensure_ascii=False),
                        now.isoformat(),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:  # noqa: BLE001
            logger.debug("recipe marker skipped: %s", e)
