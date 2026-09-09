"""SymbolicReasoner — OCOS 自己的符号推理器（零 LLM 调用）。

核心能力：给定一个任务描述，基于 BeliefStore + PatternStore +
EpisodeStore 做简单因果预测，返回 {expected_success, confidence,
similar_experiences, suggested_procedure, agent_success_map, verdict}。

设计原则：
  1. 纯逻辑组件（不是 Engine 子类，15 Engines 够用）
  2. 无 LLM 依赖（全程规则/统计/相似度匹配）
  3. 保守：数据不足时 verdict="use_llm"，不瞎猜
  4. 可组合：被 ReasoningEngine/DecisionBridge 按需调用

相似度算法（v2 — 2026-09-09 升级）：
  TF-IDF cosine + unigram+bigram 混合 token
  ← 原来 bi-gram Jaccard 在中文场景下 confidence ~0.20，永远达不到 0.8
"""
from __future__ import annotations

import json
import logging
import math
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── TF-IDF cosine 相似度（v2 核心升级）───────────────────────────────────────

_STOPWORDS_CN = set("的了在是和与或对为于从到把被让使将也都还但却而")
_STOPWORDS_EN = {
    "the", "a", "an", "is", "are", "was", "were", "to", "of", "in",
    "for", "on", "with", "by", "from", "at", "as", "and", "or",
    "but", "not", "no", "do", "does", "did", "be", "been", "being",
    "have", "has", "had", "i", "you", "he", "she", "it", "we", "they",
    "this", "that", "these", "those", "my", "your", "his", "its",
    "our", "their", "about", "into", "through", "over", "under",
}


def _tokenize(text: str) -> list[str]:
    """中英混合分词：unigram（字/英文词）+ bi-gram（字对/词对）混合 token。

    为什么混合：纯 unigram 太碎（中文单字信息量低），纯 bi-gram 太稀疏
    （短文本可能只有 3-5 个 bi-gram）。混合后 TF-IDF 既有字级覆盖又有词级
    精度。
    """
    if not text:
        return []
    chunks = re.split(r"[\s，。！？、；：,.!?;:()（）\[\]【】\n]+", text.lower())
    tokens: list[str] = []
    for chunk in chunks:
        if not chunk:
            continue
        # 纯英文/数字
        if re.match(r"^[a-z0-9_]+$", chunk):
            if chunk not in _STOPWORDS_EN and len(chunk) > 1:
                tokens.append("w:" + chunk)  # w: 前缀标记英文词
        else:
            # 含中文
            en_subs = re.findall(r"[a-z]{2,}", chunk)
            tokens.extend("w:" + t for t in en_subs if t not in _STOPWORDS_EN)
            # 中文单字（unigram）
            cn_chars = [
                ch for ch in chunk
                if "\u4e00" <= ch <= "\u9fff" and ch not in _STOPWORDS_CN
            ]
            tokens.extend("c:" + ch for ch in cn_chars)  # c: 前缀标记中文字
            # 中文 bi-gram（字对）— 给 TF-IDF 更多词级信号
            for i in range(len(cn_chars) - 1):
                tokens.append("b:" + cn_chars[i] + cn_chars[i + 1])
    return tokens


def _tfidf_cosine(query_text: str, docs: list[str]) -> list[float]:
    """计算 query 和每个 doc 的 TF-IDF cosine 相似度。

    纯 Python 实现，零依赖。500 条文档每条几百字 → 毫秒级。

    Returns:
        和 docs 等长的相似度列表 [0.0, 1.0]。
    """
    if not docs:
        return []
    query_tokens = _tokenize(query_text)
    if not query_tokens and not any(_tokenize(d) for d in docs):
        return [0.0] * len(docs)

    # 1. 对所有 docs + query 算 token 列表
    doc_tokens_list = [_tokenize(d) for d in docs]
    all_tokens_list = [query_tokens] + doc_tokens_list  # [query, doc1, doc2, ...]
    n_docs_total = len(all_tokens_list)

    # 2. 算 IDF：每个 token 在多少"文档"（含 query）里出现
    df: dict[str, int] = Counter()
    for tokens in all_tokens_list:
        for tok in set(tokens):
            df[tok] += 1
    idf: dict[str, float] = {
        tok: math.log((n_docs_total + 1) / (freq + 1)) + 1.0
        for tok, freq in df.items()
    }

    # 3. 算 query 的 TF-IDF 向量
    query_tf = Counter(query_tokens)
    query_vec: dict[str, float] = {
        tok: count * idf.get(tok, 1.0)
        for tok, count in query_tf.items()
    }
    query_norm = math.sqrt(sum(v * v for v in query_vec.values())) or 1e-9

    # 4. 算每个 doc 的 TF-IDF 向量 → cosine
    results: list[float] = []
    for doc_tokens in doc_tokens_list:
        if not doc_tokens or not query_tokens:
            results.append(0.0)
            continue
        doc_tf = Counter(doc_tokens)
        # 只算 query 和 doc 的交集 token（稀疏加速）
        common = set(query_vec.keys()) & set(doc_tf.keys())
        if not common:
            results.append(0.0)
            continue
        dot = 0.0
        for tok in common:
            doc_weight = doc_tf[tok] * idf.get(tok, 1.0)
            dot += query_vec[tok] * doc_weight
        # doc 的完整 norm（需要所有 token，不只是 common）
        doc_norm_sq = 0.0
        for tok, count in doc_tf.items():
            w = count * idf.get(tok, 1.0)
            doc_norm_sq += w * w
        doc_norm = math.sqrt(doc_norm_sq) or 1e-9
        results.append(dot / (query_norm * doc_norm))

    return results


# ── 输出数据类 ──────────────────────────────────────────────────────────────

@dataclass
class SymbolicPrediction:
    """SymbolicReasoner 单次预测输出。"""

    expected_success: float          # 0.0 - 1.0 预期成功率
    confidence: float                # 0.0 - 1.0 推理置信度
    similar_experiences: list[dict]  # top-3 相似历史
    suggested_procedure: str | None  # C 类矫正模板（如果命中失败模式）
    agent_success_map: dict[str, float]  # {agent_type: 历史成功率}
    verdict: str                     # "symbolic_skip_llm" | "use_llm"
    source_count: int = 0            # 本次查询用到的 episode 数

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_success": round(self.expected_success, 3),
            "confidence": round(self.confidence, 3),
            "similar_experiences": self.similar_experiences[:3],
            "suggested_procedure": self.suggested_procedure,
            "agent_success_map": {k: round(v, 3) for k, v in self.agent_success_map.items()},
            "verdict": self.verdict,
            "source_count": self.source_count,
        }


# ── SymbolicReasoner 主体 ────────────────────────────────────────────────────

class SymbolicReasoner:
    """OCOS 不依赖 LLM 的符号推理器。

    查询三层数据：
      1. BeliefStore（表 belief）→ 主题级置信度
      2. PatternStore（表 pattern）→ trigger→relation 规则
      3. EpisodeStore（表 episodes）→ goal_result 统计聚合
    """

    # 置信度阈值：≥ 0.6 时 verdict="symbolic_skip_llm"
    # v2 调整：TF-IDF cosine 分值整体比 Jaccard 高但仍偏保守，
    # 0.6 让 OCOS 在有相似经验（≥3条）时就能独立决策，不等 0.8
    HIGH_CONFIDENCE_THRESHOLD = 0.6
    # 低阈值：< 此值 verdict 必为 "use_llm"
    MIN_CONFIDENCE_THRESHOLD = 0.3

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            # 懒找默认路径：$HOME/.ocos/ocos.db（daemon 生产路径）
            import os as _os
            db_path = _os.path.expanduser("~/.ocos/ocos.db")
        self._db_path = db_path

    def predict(
        self,
        task_description: str,
        agent_type: str | None = None,
        context: str | None = None,
    ) -> SymbolicPrediction:
        """对单个任务做符号预测。

        Args:
            task_description: 待执行任务的自然语言描述
            agent_type: 目标 agent 类型（如 "researcher"/"writer"）；
                        传 None 时返回所有 agent 的成功率
            context: 额外上下文（可选，会并入相似度计算）

        Returns:
            SymbolicPrediction 结果
        """
        text = task_description or ""
        if context:
            text = text + " " + context

        agent_success: dict[str, float] = {}
        similar: list[dict] = []
        belief_hits: list[dict] = []
        pattern_hits: list[dict] = []
        source_count = 0
        suggested_procedure: str | None = None

        conn = self._try_connect()
        if conn is None:
            # 无法打开 DB → 保守返回 use_llm
            return SymbolicPrediction(
                expected_success=0.5,
                confidence=0.0,
                similar_experiences=[],
                suggested_procedure=None,
                agent_success_map={},
                verdict="use_llm",
            )

        try:
            # ── Step 1: EpisodeStore 聚合（主数据源）──
            agent_success, similar, source_count = self._query_episodes(
                conn, text, agent_type
            )

            # ── Step 2: BeliefStore 主题匹配 ──
            belief_hits = self._query_beliefs(conn, text)

            # ── Step 3: PatternStore trigger 匹配 ──
            pattern_hits = self._query_patterns(conn, text)

            # ── Step 4: 综合置信度 ──
            success, conf = self._aggregate(
                agent_success, similar, belief_hits, pattern_hits, source_count
            )

            # ── Step 5: 失败模式 → C 类模板 ──
            if success < 0.4 and conf > self.MIN_CONFIDENCE_THRESHOLD:
                suggested_procedure = self._infer_procedure(text, agent_type)

            # ── Step 6: verdict ──
            if conf >= self.HIGH_CONFIDENCE_THRESHOLD and source_count >= 3:
                verdict = "symbolic_skip_llm"
            else:
                verdict = "use_llm"

        except Exception as e:
            logger.debug("SymbolicReasoner.predict error: %s", e)
            return SymbolicPrediction(
                expected_success=0.5,
                confidence=0.0,
                similar_experiences=[],
                suggested_procedure=None,
                agent_success_map={},
                verdict="use_llm",
            )
        finally:
            conn.close()

        return SymbolicPrediction(
            expected_success=success,
            confidence=conf,
            similar_experiences=similar[:3],
            suggested_procedure=suggested_procedure,
            agent_success_map=agent_success,
            verdict=verdict,
            source_count=source_count,
        )

    # ── 数据源查询 ──────────────────────────────────────────────────────────

    def _try_connect(self) -> sqlite3.Connection | None:
        if not self._db_path:
            return None
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception:
            return None

    def _query_episodes(
        self,
        conn: sqlite3.Connection,
        text: str,
        agent_type: str | None,
    ) -> tuple[dict[str, float], list[dict], int]:
        """从 episodes 表聚合历史成功率 + 找相似 goal。"""
        agent_success: dict[str, float] = {}
        similar: list[dict] = []

        # 近 30 天：decision（有真实 goal 文本）+ experience + lesson（failure 统计）
        try:
            rows = conn.execute(
                "SELECT goal, action, outcome, created_at, source "
                "FROM episodes "
                "WHERE source IN ('goal_result', 'experience', 'decision', 'lesson') "
                "  AND datetime(created_at) >= datetime('now','-30 days') "
                "  AND goal IS NOT NULL AND goal != '' AND goal != 'None' "
                "ORDER BY created_at DESC LIMIT 500"
            ).fetchall()
        except sqlite3.Error:
            return agent_success, similar, 0

        if not rows:
            return agent_success, similar, 0

        # ── v2 TF-IDF 批量算相似度（一次调用覆盖所有 episodes）──
        goal_texts = [str(r["goal"] or "") for r in rows]
        sims = _tfidf_cosine(text, goal_texts)

        scored: list[tuple[float, sqlite3.Row]] = []
        success_by_action: dict[str, list[bool]] = {}

        for i, r in enumerate(rows):
            goal_text = goal_texts[i]
            action_text = str(r["action"] or "")
            outcome_blob = r["outcome"] or "{}"
            try:
                oc = json.loads(outcome_blob) if outcome_blob else {}
            except Exception:
                oc = {}
            ok_val = oc.get("success", True)
            success = bool(ok_val) if ok_val is not None else True

            # v2: TF-IDF cosine 结果
            sim = sims[i] if i < len(sims) else 0.0
            if sim > 0.02:  # 阈值放宽：TF-IDF 分值整体比 Jaccard 低一点
                scored.append((sim, r))

            # action 聚合：action 形如 "researcher.execute" → agent="researcher"
            # 但要过滤非 agent 的 source 标记（failure_lesson, goal_result, ...）
            agent = action_text.split(".")[0] if "." in action_text else action_text
            _KNOWN_AGENTS = {"researcher", "writer", "reviewer", "planner",
                             "summarizer", "critic", "code_agent"}
            if agent and agent in _KNOWN_AGENTS:
                success_by_action.setdefault(agent, []).append(success)

        # 构建 agent_success
        for agent, results in success_by_action.items():
            agent_success[agent] = sum(results) / len(results) if results else 0.0

        # 匹配 agent_type 时优先
        if agent_type and agent_type in agent_success:
            # 排序：先 agent_type + 相似度，再相似度
            scored.sort(key=lambda x: (
                agent_type in str(x[1]["action"] or ""),
                x[0],
            ), reverse=True)
        else:
            scored.sort(key=lambda x: x[0], reverse=True)

        for sim, row in scored[:5]:
            try:
                oc = json.loads(row["outcome"] or "{}")
            except Exception:
                oc = {}
            similar.append({
                "goal": str(row["goal"] or "")[:120],
                "action": str(row["action"] or "")[:50],
                "success": oc.get("success"),
                "similarity": round(sim, 3),
            })

        return agent_success, similar, len(rows)

    def _query_beliefs(
        self, conn: sqlite3.Connection, text: str
    ) -> list[dict]:
        """查 BeliefStore 中相关度最高的 belief。"""
        try:
            rows = conn.execute(
                "SELECT statement, confidence, scope "
                "FROM belief ORDER BY created_at DESC LIMIT 100"
            ).fetchall()
        except sqlite3.Error:
            return []

        hits: list[dict] = []
        # v2: 批量算 TF-IDF — scope 和 statement 分开算取 max
        scope_texts = [str(r["scope"] or "") for r in rows]
        stmt_texts = [str(r["statement"] or "") for r in rows]
        sims_scope = _tfidf_cosine(text, scope_texts)
        sims_stmt = _tfidf_cosine(text, stmt_texts)

        for i, r in enumerate(rows):
            sim = max(
                sims_scope[i] if i < len(sims_scope) else 0.0,
                sims_stmt[i] if i < len(sims_stmt) else 0.0,
            )
            if sim > 0.02:
                hits.append({
                    "statement": str(r["statement"])[:100],
                    "confidence": r["confidence"],
                    "similarity": round(sim, 3),
                })

        hits.sort(key=lambda x: x["similarity"], reverse=True)
        return hits[:3]

    def _query_patterns(
        self, conn: sqlite3.Connection, text: str
    ) -> list[dict]:
        """查 PatternStore 中相关度最高的 pattern。"""
        try:
            rows = conn.execute(
                "SELECT trigger_condition, observed_relation, confidence, "
                "supporting_episode_count "
                "FROM pattern ORDER BY confidence DESC LIMIT 50"
            ).fetchall()
        except sqlite3.Error:
            return []

        hits: list[dict] = []
        # v2: 批量 TF-IDF
        triggers = [str(r["trigger_condition"] or "") for r in rows]
        relations = [str(r["observed_relation"] or "") for r in rows]
        sims_trigger = _tfidf_cosine(text, triggers)
        sims_rel = _tfidf_cosine(text, relations)

        for i, r in enumerate(rows):
            sim = max(
                sims_trigger[i] if i < len(sims_trigger) else 0.0,
                sims_rel[i] if i < len(sims_rel) else 0.0,
            )
            if sim > 0.015:  # pattern trigger 可能很短，阈值略低
                hits.append({
                    "trigger": triggers[i][:80],
                    "relation": relations[i][:80],
                    "confidence": r["confidence"],
                    "n": r["supporting_episode_count"],
                    "similarity": round(sim, 3),
                })

        hits.sort(key=lambda x: x["similarity"], reverse=True)
        return hits[:3]

    # ── 综合推理 ────────────────────────────────────────────────────────────

    def _aggregate(
        self,
        agent_success: dict[str, float],
        similar: list[dict],
        belief_hits: list[dict],
        pattern_hits: list[dict],
        source_count: int,
    ) -> tuple[float, float]:
        """综合各数据源 → (expected_success, confidence)。"""
        # 1. 从 similar_experiences 里算成功率（最核心的信号）
        if similar:
            sim_successes = [
                1.0 if h["success"] else 0.0
                for h in similar if h.get("success") is not None
            ]
            if sim_successes:
                success_sim = sum(sim_successes) / len(sim_successes)
                # 按相似度加权
                weights = [h["similarity"] for h in similar if h.get("success") is not None]
                total_w = sum(weights) or 1.0
                weighted_success = sum(
                    s * w for s, w in zip(sim_successes, weights)
                ) / total_w
                success = weighted_success
            else:
                success = 0.5
        else:
            success = 0.5  # 无相似经验 → 先验 50/50

        # 2. Belief 置信度修正
        if belief_hits:
            avg_belief_conf = sum(b["confidence"] for b in belief_hits) / len(belief_hits)
            if avg_belief_conf > 0.6:
                # belief 置信度高 → 更相信
                pass  # 只用于 confidence 计算，不改 success 本身

        # 3. Pattern 匹配：relation 含 "failure"/"fail" → 拉低 success
        for p in pattern_hits:
            rel = (p.get("relation") or "").lower()
            if any(k in rel for k in ("fail", "error", "失败", "错", "break", "timeout")):
                success = min(success, 0.3)
                break

        # 4. Confidence（v2 改：加权求和而非平均，多信号互相加强）
        #    TF-IDF cosine 在短文本上 0.25+ 等价于长文本 0.75+ 的相关度，
        #    需要 ×1.8 补偿。source_count 表示有多少历史可用，权重 0.4。
        signals = []
        if similar:
            top_sim = max(h["similarity"] for h in similar)
            n_relevant = sum(1 for h in similar if h["similarity"] > 0.05)
            # v2: ×1.8 补偿短文本 TF-IDF 分值偏低
            signals.append(top_sim * 1.8 * min(n_relevant, 3) / 3.0)
            signals.append(min(source_count, 50) / 50.0 * 0.4)
        if belief_hits:
            signals.append(
                sum(b["confidence"] for b in belief_hits) / len(belief_hits) * 0.4
            )
        if pattern_hits:
            avg_p_conf = sum(p["confidence"] for p in pattern_hits) / len(pattern_hits)
            signals.append(avg_p_conf * 0.3)

        if signals:
            conf = sum(signals)  # v2: 加权求和（不是平均）
        else:
            conf = 0.0

        # 保险：source_count < 2 → confidence 压低
        if source_count < 2:
            conf *= 0.5

        return success, min(conf, 1.0)

    def _infer_procedure(
        self, text: str, agent_type: str | None
    ) -> str | None:
        """失败模式推断 → cause_to_procedure 映射。

        复用 Phase A 的 cause_to_procedure（零 LLM）。
        """
        try:
            from ocos.learning.experience_learning import (
                cause_to_procedure, FailureCause,
            )
        except Exception:
            return None

        # 关键词扫描 → 判断最可能的 FailureCause
        tl = (text or "").lower()
        if any(k in tl for k in ("超时", "timeout", "time out", "timed out")):
            return cause_to_procedure(FailureCause.TIMEOUT, text)
        if any(k in tl for k in ("权限", "permission", "denied", "沙盒", "sandbox", "审批", "pending")):
            return cause_to_procedure(FailureCause.PERMISSION_DENIED, text)
        if any(k in tl for k in ("不存在", "not found", "undefined", "模块", "module", "命令", "command", "脚本", "script", "执行")):
            return cause_to_procedure(FailureCause.EXECUTION_ERROR, text)

        return None
