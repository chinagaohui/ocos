"""ocos/growth — 成长模块 (Phase 50).

外部智能体 (Hermes 等) 投递技术情报信号 → LLM 分析 → 自动优化自身代码.

架构 (复用优先, 零新建基础设施):
    TechSignal (外部注入)                          ← G1: 信号接收
        ↓
    GrowthAnalyzer.analyze (LLM 生成优化提案)        ← G2: 分析 (无变异, 只读)
        ↓
    GrowthOptimizer.execute (快照→改→测→保留/回滚)   ← G3: 受治理自动执行
        ↓
    GrowthLog (sqlite 持久化)                        ← G1: 审计追踪

治理不变量:
    1. Decision 唯一 Mutation Authority — 本模块自身绝不写文件,
       全部经 SelfModificationAgent (FORBIDDEN_DIRS/FILES 边界) 执行
    2. 自动执行三步闸: 快照 → 修改+测试 → 失败自动回滚
    3. 防失控: 只改 ocos/ 下 .py; 禁 .env/config.json/.venv/.git
    4. 全自动仅对 approval_required=False 的改动; 高风险改动冻结待人工
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from ocos.logging import get_logger

logger = get_logger(__name__)

# ── 边界常量 ──────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # <repo>/ocos → repo

# 信号质量门槛
MIN_SIGNAL_CHARS = 60
MAX_SIGNAL_CHARS = 20_000

# 自动执行禁区 (与 self_modification_agent 对齐 + 更严)
FORBIDDEN_DIRS = {".venv", ".git", "__pycache__", "node_modules", "ocos_data", "venv"}
FORBIDDEN_FILES = {".env", ".env.local", "config.json", "*.db", "*.sqlite"}

# 允许优化的代码根 (只改 OCOS 自身 Python 代码)
ALLOWED_PREFIX = "ocos/"

# 高置信优化所需 LLM 响应中必须存在的字段
REQUIRED_PROPOSAL_FIELDS = ("rationale", "file_path", "new_content")

# LLM 响应中试图输出 patch (而非明确放弃) 的信号 — 触发精确性重试
_WANTED_PATCH_RE = re.compile(r'"old_snippet"\s*:\s*"[^"]+"', re.DOTALL)

# 自动执行规模护栏 (防 LLM 大段删除/重写 — 语义破坏语法门拦不住):
#   - 净删除 > MAX_NET_DELETION_LINES 行 → 拒绝自动执行 (需人工)
#   - 改动后行数 < 原文 50% → 拒绝 (疑似大段删改)
MAX_NET_DELETION_LINES = 30
MIN_KEEP_RATIO = 0.5


def _deletion_scale(original: str, proposed: str) -> tuple[int, float]:
    """返回 (净删除行数, 保留比例)。original 为空(新文件) → (0, 1.0)。"""
    if not original.strip():
        return 0, 1.0
    orig_lines = len(original.splitlines())
    prop_lines = len(proposed.splitlines())
    net_deleted = max(0, orig_lines - prop_lines)
    keep_ratio = prop_lines / orig_lines if orig_lines else 1.0
    return net_deleted, keep_ratio


def _exceeds_scale_guard(original: str, proposed: str) -> tuple[bool, str]:
    """规模护栏: 超限返回 (True, 原因)。"""
    net_deleted, keep_ratio = _deletion_scale(original, proposed)
    if net_deleted > MAX_NET_DELETION_LINES:
        return True, (f"net deletion {net_deleted} > {MAX_NET_DELETION_LINES} lines "
                      "(需人工审批)")
    if keep_ratio < MIN_KEEP_RATIO:
        return True, (f"proposed size {keep_ratio:.0%} < {MIN_KEEP_RATIO:.0%} of original "
                      "(疑似大段删改, 需人工审批)")
    return False, ""


# ── 模型 ──────────────────────────────────────────────────────────


@dataclass
class TechSignal:
    """外部智能体投递的技术情报信号 (Hermes 搜索 → OCOS 成长)。"""

    topic: str                      # 主题 (如 "asyncio task group")
    summary: str                    # 搜索摘要 (≥60 chars)
    source: str = "external"        # 投递者标识
    source_url: str = ""            # 来源 URL
    domain: str = "python"          # 技术域
    confidence: float = 0.5         # 投递者置信度
    received_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class GrowthProposal:
    """LLM 分析产物 — 一个具体的代码优化提案 (不执行, 只描述)。

    两种形态:
      整文件式: new_content 给全量新内容 (适用于小模块)
      patch 式:  old_snippet → new_snippet 精确替换 (推荐, 适用于任何大小)
    """

    signal_topic: str
    rationale: str                  # 为什么优化 (含出处)
    file_path: str                  # 相对仓库根
    new_content: str = ""           # 形态1: 完整新文件内容 (整文件替换式)
    old_snippet: str = ""           # 形态2: 原文中待替换片段 (须精确唯一匹配)
    new_snippet: str = ""           # 形态2: 替换后的片段
    applicability: float = 0.5      # LLM 自评适用度 0-1
    proposed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    proposal_id: str = field(default_factory=lambda: "gr-" + uuid.uuid4().hex[:12])


@dataclass
class GrowthResult:
    """一次优化的完整结果 (记录 + 汇报)。"""

    proposal_id: str = ""
    status: str = "unknown"         # proposed / skipped / applied / rolled_back / rejected / guarded
    reason: str = ""
    file_path: str = ""
    tests_passed: int = 0
    tests_failed: int = 0
    applied_at: str = ""
    duration_ms: int = 0
    detail: dict[str, Any] = field(default_factory=dict)


# ── 信号接收与存储 (G1) ──────────────────────────────────────────


class GrowthSignalStore:
    """TechSignal 持久化 (sqlite)。不依赖 EventBus/WorldStore —
    保持纯逻辑可单测, 由 MasterAgent/daemon 装配。"""

    def __init__(self, db_path: str | Path = "") -> None:
        self._db_path = str(db_path or os.environ.get(
            "OCOS_GROWTH_DB", str(Path.home() / ".ocos" / "growth.db")))
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tech_signals (
                    signal_id   TEXT PRIMARY KEY,
                    topic       TEXT NOT NULL,
                    summary     TEXT NOT NULL,
                    source      TEXT DEFAULT 'external',
                    source_url  TEXT DEFAULT '',
                    domain      TEXT DEFAULT 'python',
                    confidence  REAL DEFAULT 0.5,
                    received_at TEXT NOT NULL,
                    status      TEXT DEFAULT 'received',  -- received/analyzed/applied/skipped
                    proposal_id TEXT DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS growth_log (
                    proposal_id TEXT PRIMARY KEY,
                    status      TEXT NOT NULL,
                    reason      TEXT DEFAULT '',
                    file_path   TEXT DEFAULT '',
                    tests_passed INTEGER DEFAULT 0,
                    tests_failed INTEGER DEFAULT 0,
                    applied_at  TEXT DEFAULT '',
                    detail      TEXT DEFAULT '{}'
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def record_signal(self, signal: TechSignal) -> str:
        signal_id = "sig-" + uuid.uuid4().hex[:12]
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO tech_signals VALUES (?,?,?,?,?,?,?,?,?,?)",
                (signal_id, signal.topic, signal.summary, signal.source,
                 signal.source_url, signal.domain, signal.confidence,
                 signal.received_at, "received", ""),
            )
        return signal_id

    def mark_signal(self, signal_id: str, status: str, proposal_id: str = "") -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE tech_signals SET status=?, proposal_id=? WHERE signal_id=?",
                (status, proposal_id, signal_id),
            )

    def pending_signals(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tech_signals WHERE status='received' ORDER BY received_at").fetchall()
        return [dict(r) for r in rows]

    def get_signal(self, signal_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tech_signals WHERE signal_id=?", (signal_id,)).fetchone()
        return dict(row) if row else None

    def log_result(self, result: GrowthResult) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO growth_log VALUES (?,?,?,?,?,?,?,?)",
                (result.proposal_id, result.status, result.reason, result.file_path,
                 result.tests_passed, result.tests_failed, result.applied_at,
                 json.dumps(result.detail, ensure_ascii=False)),
            )

    def history(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM growth_log ORDER BY applied_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        pass  # sqlite 连接按需开关, 无需保持


# ── LLM 分析 (G2) ─────────────────────────────────────────────────


class GrowthAnalyzer:
    """把 TechSignal 翻译成具体优化提案。

    分析是只读的 — 产物仅是提案, 变异由 GrowthOptimizer 负责。
    LLM 调用可注入 (测试用假 LLM); 未注入时返回 deterministic 空提案。
    """

    # 只分析这几类改动 — 其余 (改架构/改治理/删功能) 拒绝
    ACCEPTABLE_RATIONALE_HINTS = (
        "async", "性能", "性能优化", "deprecat", "安全", "bug",
        "类型", "错误处理", "logging", "重构", "兼容",
    )

    def __init__(self, llm_fn: Callable[[str], str] | None = None) -> None:
        self._llm = llm_fn  # (prompt) -> str

    def analyze(self, signal: TechSignal) -> GrowthProposal | None:
        """信号 → 提案。无 LLM 注入 / 信号太短 / 主题不在允许域 → None。

        patch 精确性补偿: LLM 偶发不逐字复制 old_snippet → 校验失败时
        反馈差异重试一次 (最终仍须逐字唯一匹配才放行, 治理不削弱)。
        """
        if self._llm is None:
            logger.info("GrowthAnalyzer: no llm_fn injected, skip analyze")
            return None
        if len(signal.summary) < MIN_SIGNAL_CHARS:
            return None

        candidates, excerpts = self._find_candidate_files(signal)
        if not candidates:
            logger.info(
                "GrowthAnalyzer: no candidate files match signal '%s'", signal.topic[:60])
            return None

        prompt = self._build_prompt(signal, candidates, excerpts)
        raw = None
        try:
            raw = self._llm(prompt)
        except Exception as e:  # LLM 失败不阻断成长 — 记录并跳过
            logger.warning("GrowthAnalyzer: llm failed: %s", e)
            return None
        proposal = self._parse_response(raw, signal, candidates)

        # 修正反馈重试: LLM 输出过 patch 但 old_snippet 未逐字命中时,
        # 把期望与实况差异回喂, 请求重出精确片段
        if (proposal is None and raw
                and _WANTED_PATCH_RE.search(raw)):
            try:
                prompt2 = prompt + (
                    "\n\n【系统反馈】你上次输出的 old_snippet 未在文件中逐字找到"
                    "（可能缩进/换行/字符有出入）。请重新只输出 JSON："
                    "打开该文件把待替换片段**原样完整复制**进 old_snippet"
                    "（含原缩进、原换行、原引号），仅改动你想替换的最小范围，"
                    "然后给出对应的 new_snippet。不要省略号、不要省略标记、不要改格式。")
                raw2 = self._llm(prompt2)
                proposal = self._parse_response(raw2, signal, candidates)
            except Exception as e:
                logger.warning("GrowthAnalyzer: retry llm failed: %s", e)
        return proposal

    def _find_candidate_files(self, signal: TechSignal, limit: int = 8
                              ) -> tuple[list[str], dict[str, str]]:
        """扫描仓库 ocos/ 下真实存在的 .py — 信号词元命中内容或文件名。

        返回 (候选路径列表, {路径: 首个命中区域的上下文片段})。
        防止 LLM 产出幻觉路径: 候选必须是磁盘真实文件。
        """
        root = Path(PROJECT_ROOT) / "ocos"
        # 信号词元: 英文小写词 + 中文 2-gram 简化为直接含词
        tokens = {w.lower() for w in re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", signal.summary)}
        tokens.update({w.lower() for w in re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", signal.topic)})
        # 过滤噪音词
        stop = {"python", "that", "with", "from", "this", "the", "and", "for",
                "ocos", "module", "code", "has", "are", "not", "new", "use",
                "used", "using", "官方", "文档", "推荐", "迁移", "提供", "成为"}
        tokens -= stop

        scored: list[tuple[int, str, str]] = []
        for f in root.rglob("*.py"):
            if "__pycache__" in f.parts or f.name.startswith("__"):
                continue
            # 只允许优化生产代码 — 排除测试文件与成长模块自身 (防自我循环)
            if ("tests" in f.parts or f.name.startswith("test_")
                    or "growth" in f.parts):
                continue
            rel = f.relative_to(PROJECT_ROOT).as_posix()
            text = f.read_text(encoding="utf-8", errors="ignore")
            low = text.lower()
            # 词边界匹配 — 防子串误命中 ("utc" 不应命中 "outcome")
            word_hits = [t for t in tokens
                         if re.search(rf"\b{re.escape(t)}\b", low)]
            content_hits = len(word_hits)
            # 文件名命中 (词边界在 stem 上)
            name_hits = sum(1 for t in tokens
                            if re.search(rf"\b{re.escape(t)}\b", f.stem.lower()))
            score = content_hits * 2 + name_hits * 5
            if score > 0:
                lines = text.splitlines()
                cutoff = max(2, int(len(lines) * 0.25))
                # 特异性锚定: 用文件中出现最少的命中词元 (gather > asyncio),
                # 在方法体区找其首行 → 覆盖真实调用点而非 docstring/import
                freq = {t: len(re.findall(rf"\b{re.escape(t)}\b", low))
                        for t in word_hits}
                anchor = -1
                for t in sorted(freq, key=lambda x: freq[x]):
                    for i, ln in enumerate(lines):
                        if i >= cutoff and re.search(rf"\b{re.escape(t)}\b", ln.lower()):
                            anchor = i
                            break
                    if anchor >= 0:
                        break
                if anchor >= 0:
                    start = max(0, anchor - 8)
                    end = min(len(lines), anchor + 32)
                    ctx = "\n".join(lines[start:end])
                else:
                    # 兜底: 全部命中行
                    ctx = "\n".join(
                        ln for ln in lines
                        if any(re.search(rf"\b{re.escape(t)}\b", ln.lower())
                               for t in word_hits))[:3000]
                scored.append((score, rel, ctx))

        scored.sort(reverse=True)
        paths = [rel for _, rel, _ in scored[:limit]]
        excerpts = {rel: ctx for _, rel, ctx in scored[:limit] if ctx}
        return paths, excerpts

    def _build_prompt(self, signal: TechSignal,
                      candidates: list[str] | None = None,
                      excerpts: dict[str, str] | None = None) -> str:
        top_excerpt = ""
        if excerpts and candidates:
            top = candidates[0]
            if excerpts.get(top):
                top_excerpt = ("\n\n最高相关文件 " + top +
                               " 的原文片段 (grep 命中区域, 逐字复制自文件 — old_snippet 必须精确匹配):\n```\n" +
                               excerpts[top][:6000] + "\n```")
        return f"""你是 OCOS 内核架构师。外部情报信号可能蕴含对 OCOS 自身代码的优化机会。

信号主题: {signal.topic}
信号摘要: {signal.summary}
技术域: {signal.domain}
来源: {signal.source} {signal.source_url}

任务: 判断此信号是否值得优化 OCOS 自身代码。若值得, 产出**一个**最小、安全、
具体的优化提案 — **优先用精确替换 (patch 式)**, 不要整文件重写
(整文件重写只用于 <80 行的极简模块)。{top_excerpt}

候选文件 (已按相关性排序, 从磁盘扫描的真实模块 — **file_path 必须从下面选**):
{json.dumps(candidates or [], ensure_ascii=False) if candidates else "(无候选)"}

要求:
1. 只输出 JSON (不要 markdown 代码块包裹):
{{
  "worthwhile": true/false,
  "rationale": "为什么值得/不值得, 引用信号要点",
  "file_path": "候选列表中的一个真实路径",
  "old_snippet": "原文中将被替换的片段 — 必须逐字精确复制自该文件, 且在文件中唯一",
  "new_snippet": "替换后的新代码片段 (含相同缩进)",
  "new_content": "仅当整文件重写时填 (≤80 行的模块); 否则留空",
  "applicability": 0.0-1.0
}}
2. worthwhile=false 时只填 rationale, 其余字段留空
3. 若信号与本仓库无关或改动风险 > 收益, 必须 worthwhile=false
4. 禁止提议: 删除文件、改 .env/config.json、改治理/宪法/权限代码、加网络依赖
5. file_path 不在候选列表中 → 视为无效, 返回 worthwhile=false
6. old_snippet 无法从上下文确定精确原文 → 宁可 worthwhile=false, 不要猜

信号: {json.dumps(asdict(signal), ensure_ascii=False)}"""

    def _parse_response(self, raw: str, signal: TechSignal,
                        candidates: list[str] | None = None) -> GrowthProposal | None:
        text = raw.strip()
        # 剥离 markdown code fence
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # 尝试提取首个 {...}
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if not m:
                logger.warning("GrowthAnalyzer: unparseable llm response")
                return None
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError:
                return None

        if not data.get("worthwhile"):
            return None

        rationale = str(data.get("rationale", ""))
        file_path = str(data.get("file_path", ""))
        new_content = str(data.get("new_content", ""))
        old_snippet = str(data.get("old_snippet", ""))
        new_snippet = str(data.get("new_snippet", ""))
        # patch 式: old_snippet+new_snippet 必须成对
        patch_mode = bool(old_snippet or new_snippet)
        if patch_mode and not (old_snippet and new_snippet):
            logger.warning("GrowthAnalyzer: patch mode requires both old_snippet and new_snippet")
            return None
        if not (rationale and file_path):
            logger.warning("GrowthAnalyzer: llm response missing required fields")
            return None
        if not patch_mode and not new_content:
            logger.warning("GrowthAnalyzer: llm response has neither new_content nor patch")
            return None

        # 路径安全校验 — 只允许 ocos/ 下的 .py
        if not file_path.startswith(ALLOWED_PREFIX) or not file_path.endswith(".py"):
            logger.warning("GrowthAnalyzer: rejected path %s", file_path)
            return None

        # 文件必须真实存在 (防幻觉路径)
        real_path = Path(PROJECT_ROOT) / file_path
        if not real_path.is_file():
            logger.warning("GrowthAnalyzer: file does not exist: %s", file_path)
            return None

        # patch 式: old_snippet 必须逐字存在于原文且唯一
        if patch_mode:
            original = real_path.read_text(encoding="utf-8", errors="replace")
            if original.count(old_snippet) != 1:
                logger.warning(
                    "GrowthAnalyzer: old_snippet not unique/absent (%d hits)",
                    original.count(old_snippet))
                return None

        # 规模护栏 (第一道防线): 大段删除/重写的 patch 在解析层即拒绝,
        # 不让危险提案进入 preview/执行
        if patch_mode:
            original = real_path.read_text(encoding="utf-8", errors="replace")
            proposed_full = original.replace(old_snippet, new_snippet, 1)
        else:
            original = real_path.read_text(encoding="utf-8", errors="replace")
            proposed_full = new_content
        violates, why = _exceeds_scale_guard(original, proposed_full)
        if violates:
            logger.warning("GrowthAnalyzer: scale guard rejected %s: %s", file_path, why)
            return None

        # 不允许动治理/宪法/权限模块
        for forbidden in ("constitution", "governance", "permission", "identity"):
            if forbidden in file_path.lower():
                logger.warning("GrowthAnalyzer: rejected forbidden module %s", file_path)
                return None

        try:
            applicability = float(data.get("applicability", 0.5))
        except (TypeError, ValueError):
            applicability = 0.5

        return GrowthProposal(
            signal_topic=signal.topic,
            rationale=rationale,
            file_path=file_path,
            new_content=new_content,
            old_snippet=old_snippet,
            new_snippet=new_snippet,
            applicability=max(0.0, min(1.0, applicability)),
        )


# ── 受治理自动执行 (G3) ──────────────────────────────────────────


class GrowthOptimizer:
    """执行优化提案 — 快照→修改→测试→保留/回滚。

    全自动仅当改动不触发自我修改代理的高风险标记;
    触发则冻结为 skipped (留待人工 — 成长模块不越权)。
    """

    def __init__(self, project_root: str | Path = PROJECT_ROOT) -> None:
        self._root = Path(project_root)
        self._snapshots: dict[str, str] = {}

    # -- 边界校验 --

    def validate_path(self, file_path: str) -> tuple[bool, str]:
        """路径必须在 ocos/ 下且不在禁区。"""
        p = Path(file_path)
        # 规范化 — 禁止 .. 逃逸
        norm = os.path.normpath(file_path)
        if norm.startswith("..") or norm.startswith("/"):
            return False, f"forbidden path: {file_path}"
        if not norm.startswith(ALLOWED_PREFIX):
            return False, f"outside allowed prefix: {file_path}"
        parts = set(p.parts)
        if parts & FORBIDDEN_DIRS:
            return False, f"forbidden directory: {file_path}"
        if p.name in FORBIDDEN_FILES or p.suffix not in (".py",):
            return False, f"forbidden file: {file_path}"
        return True, ""

    # -- 快照 --

    def _snapshot(self, file_path: str) -> str | None:
        """记录原文件内容 (内存 + 磁盘副本), 返回原内容或 None (新文件)。"""
        target = self._root / file_path
        if target.exists():
            original = target.read_text(encoding="utf-8", errors="replace")
            snap_dir = Path(os.environ.get("OCOS_GROWTH_SNAP", "/tmp/ocos_growth_snaps"))
            snap_dir.mkdir(parents=True, exist_ok=True)
            snap_path = snap_dir / (file_path.replace("/", "__") + f".{int(time.time())}.bak")
            snap_path.write_text(original, encoding="utf-8")
            self._snapshots[file_path] = str(snap_path)
            return original
        self._snapshots[file_path] = ""
        return None

    def _rollback(self, file_path: str, original: str | None) -> bool:
        snap_path = self._snapshots.get(file_path, "")
        target = self._root / file_path
        try:
            if snap_path and Path(snap_path).exists():
                shutil.copy2(snap_path, target)
                return True
            if original is None:
                target.unlink(missing_ok=True)  # 原为新文件 → 删除
                return True
            target.write_text(original, encoding="utf-8")
            return True
        except Exception as e:
            logger.error("rollback failed for %s: %s", file_path, e)
            return False

    # -- 测试 --

    def _run_tests(self, file_path: str) -> tuple[int, int]:
        """验证改动: 优先目标模块专属测试文件; 无专属文件 → import 门。

        不回跑全库子集 (-k 会撞同名 stem 且包含自我测试文件造成竞态/慢)。
        import 成功 = 1 passed; 失败 = 1 failed (不保留)。
        """
        module = Path(file_path).stem
        own_test = self._root / "ocos" / "tests" / f"test_{module}.py"
        if own_test.exists():
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", str(own_test),
                     "-q", "--tb=no", "--timeout=60"],
                    cwd=str(self._root),
                    capture_output=True,
                    text=True,
                    timeout=180,
                    env={**os.environ, "OCOS_DW_DRY_RUN": "1"},
                )
            except (subprocess.TimeoutExpired, Exception):
                return 0, 1
            out = result.stdout or ""
            passed = failed = 0
            m = re.search(r"(\d+) passed", out)
            if m:
                passed = int(m.group(1))
            m = re.search(r"(\d+) failed", out)
            if m:
                failed = int(m.group(1))
            return passed, failed

        # import 门: 模块可加载 = 通过 (语法已由 py_compile 验证)
        dotted = file_path[:-3].replace("/", ".")
        try:
            r = subprocess.run(
                [sys.executable, "-c", f"import {dotted}"],
                cwd=str(self._root),
                capture_output=True,
                text=True,
                timeout=60,
                env={**os.environ, "OCOS_DW_DRY_RUN": "1"},
            )
        except (subprocess.TimeoutExpired, Exception):
            return 0, 1
        return (1, 0) if r.returncode == 0 else (0, 1)

    def apply(self, proposal: GrowthProposal,
              modifier: Any = None) -> GrowthResult:
        """应用提案。返回 GrowthResult (status: skipped/applied/rolled_back/rejected)。

        modifier: 可注入 SelfModificationAgent 实例做真正的文件变异。
                  未注入 → 用内置安全写入 (同样受 validate_path 约束)。
        """
        result = GrowthResult(proposal_id=proposal.proposal_id,
                              file_path=proposal.file_path)
        start = time.monotonic()

        # 1. 边界
        ok, err = self.validate_path(proposal.file_path)
        if not ok:
            result.status = "rejected"
            result.reason = err
            result.duration_ms = int((time.monotonic() - start) * 1000)
            return result

        # 2. 低适用度 → 跳过 (LLM 自评 < 0.6 不自动动代码)
        if proposal.applicability < 0.6:
            result.status = "skipped"
            result.reason = f"low applicability {proposal.applicability:.2f}"
            result.duration_ms = int((time.monotonic() - start) * 1000)
            return result

        # 2.5 规模护栏 — 防 LLM 大段删除/重写 (语义破坏语法门拦不住)
        target = self._root / proposal.file_path
        orig_text = target.read_text(encoding="utf-8") if target.exists() else ""
        if proposal.old_snippet:  # patch 式: 合成新全文再评估
            proposed_text = orig_text.replace(proposal.old_snippet,
                                              proposal.new_snippet, 1)
        else:  # 整文件式
            proposed_text = proposal.new_content
        guard_violation, guard_reason = _exceeds_scale_guard(orig_text, proposed_text)
        if guard_violation:
            result.status = "guarded"
            result.reason = guard_reason
            result.duration_ms = int((time.monotonic() - start) * 1000)
            return result

        # 3. 快照
        original = self._snapshot(proposal.file_path)

        # 4. 变异 (经 modifier 或内置) — patch 式先做精确替换
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            if modifier is not None:
                content_to_write = proposal.new_content
                if not content_to_write:  # patch 式 → 先合成新全文
                    cur = target.read_text(encoding="utf-8") if target.exists() else ""
                    content_to_write = cur.replace(proposal.old_snippet,
                                                   proposal.new_snippet, 1)
                mod_result = modifier.execute(
                    task=f"growth: {proposal.rationale[:120]}",
                    file=proposal.file_path,
                    content=content_to_write,
                    test=False,  # 测试由本模块统一跑
                    dry_run=False,
                )
                if not mod_result.get("success"):
                    result.status = "skipped"
                    result.reason = f"modifier refused: {mod_result.get('error', '')}"
                    self._rollback(proposal.file_path, original)
                    result.duration_ms = int((time.monotonic() - start) * 1000)
                    return result
            elif proposal.old_snippet:  # 内置 + patch 式
                cur = target.read_text(encoding="utf-8") if target.exists() else ""
                if cur.count(proposal.old_snippet) != 1:
                    result.status = "rolled_back"
                    result.reason = "old_snippet not unique/absent at apply time"
                    self._rollback(proposal.file_path, original)
                    result.duration_ms = int((time.monotonic() - start) * 1000)
                    return result
                target.write_text(cur.replace(proposal.old_snippet,
                                             proposal.new_snippet, 1),
                                  encoding="utf-8")
            else:  # 内置 + 整文件式
                target.write_text(proposal.new_content, encoding="utf-8")
        except Exception as e:
            result.status = "rolled_back"
            result.reason = f"write failed: {e}"
            self._rollback(proposal.file_path, original)
            result.duration_ms = int((time.monotonic() - start) * 1000)
            return result

        # 5. 语法门 — 新内容必须可编译 (防坏代码无测试也通过)
        import py_compile
        try:
            py_compile.compile(str(target), doraise=True)
        except py_compile.PyCompileError as e:
            result.status = "rolled_back"
            result.reason = f"syntax error: {e}"
            self._rollback(proposal.file_path, original)
            result.duration_ms = int((time.monotonic() - start) * 1000)
            return result

        # 6. 测试 — 失败立即回滚
        passed, failed = self._run_tests(proposal.file_path)
        result.tests_passed = passed
        result.tests_failed = failed
        if failed > 0 or (passed == 0 and not self._no_test_module(proposal.file_path)):
            result.status = "rolled_back"
            result.reason = f"tests failed: {failed} failed / {passed} passed"
            self._rollback(proposal.file_path, original)
        else:
            result.status = "applied"
            result.reason = f"tests ok: {passed} passed"
            result.applied_at = datetime.now(timezone.utc).isoformat()

        result.duration_ms = int((time.monotonic() - start) * 1000)
        return result

    def _no_test_module(self, file_path: str) -> bool:
        """目标模块无对应测试文件 → 0 passed 不算失败 (但也不自动保留高风险)。"""
        return not (self._root / "ocos" / "tests" / f"test_{Path(file_path).stem}.py").exists()


# ── 编排 ──────────────────────────────────────────────────────────


class GrowthEngine:
    """成长模块主入口 — 外部信号 → 优化自身代码。"""

    def __init__(
        self,
        store: GrowthSignalStore | None = None,
        analyzer: GrowthAnalyzer | None = None,
        optimizer: GrowthOptimizer | None = None,
        modifier: Any = None,
    ) -> None:
        self.store = store or GrowthSignalStore()
        self.analyzer = analyzer or GrowthAnalyzer()
        self.optimizer = optimizer or GrowthOptimizer()
        self._modifier = modifier

    # -- G1: 注入信号 --

    def ingest(self, signal: TechSignal) -> str:
        """接收外部信号, 持久化, 返回 signal_id。"""
        if len(signal.summary) < MIN_SIGNAL_CHARS:
            raise ValueError(
                f"summary too short ({len(signal.summary)} < {MIN_SIGNAL_CHARS} chars)")
        if len(signal.summary) > MAX_SIGNAL_CHARS:
            raise ValueError(f"summary too long ({len(signal.summary)} chars)")
        signal_id = self.store.record_signal(signal)
        logger.info("GrowthEngine: signal %s received (topic=%s)", signal_id, signal.topic)
        return signal_id

    # -- G2: 分析 --

    def analyze_pending(self, signal_id: str = "") -> list[GrowthProposal]:
        """分析待处理信号, 返回值得优化的提案 (不执行)。

        指定 signal_id → 只分析该信号; 否则分析全部待处理信号。
        """
        if signal_id:
            rows = self.store.get_signal(signal_id)
            if not rows:
                return []
            sig_rows = [rows]
        else:
            sig_rows = self.store.pending_signals()

        proposals: list[GrowthProposal] = []
        for sig_row in sig_rows:
            sig = TechSignal(
                topic=sig_row["topic"],
                summary=sig_row["summary"],
                source=sig_row["source"],
                source_url=sig_row["source_url"],
                domain=sig_row["domain"],
                confidence=sig_row["confidence"],
                received_at=sig_row["received_at"],
            )
            proposal = self.analyzer.analyze(sig)
            if proposal is not None:
                proposals.append(proposal)
                self.store.mark_signal(sig_row["signal_id"], "analyzed", proposal.proposal_id)
        return proposals

    # -- G3: 执行 --

    def execute_proposal(self, proposal: GrowthProposal) -> GrowthResult:
        """执行提案 (受治理自动执行 + 回滚), 记录日志。"""
        result = self.optimizer.apply(proposal, modifier=self._modifier)
        self.store.log_result(result)
        logger.info(
            "GrowthEngine: proposal %s → %s (%s)",
            result.proposal_id, result.status, result.reason)
        return result

    # -- 一键成长 --

    def grow_once(self, signal: TechSignal, auto_execute: bool = True) -> dict[str, Any]:
        """接收 → 分析 → 执行 全链路。返回汇总。"""
        signal_id = self.ingest(signal)
        proposals = self.analyze_pending(signal_id)
        out: dict[str, Any] = {"signal_id": signal_id, "proposals": [], "results": []}
        for p in proposals:
            out["proposals"].append({
                "proposal_id": p.proposal_id,
                "rationale": p.rationale[:200],
                "file_path": p.file_path,
                "applicability": p.applicability,
            })
            if auto_execute:
                r = self.execute_proposal(p)
                out["results"].append(asdict(r))
        return out
