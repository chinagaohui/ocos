"""P0-1 Step 1 — S2 SelfState 专属持久化：Persistence / Ownership / Reload。

本模块只做 Step 1 边界内三件事（P0-1_PLAN §Step 1）：
  1. canonical serialization：S2 提交态固定字段顺序 + content_hash 由提交态计算。
  2. atomic commit：candidate → SelfUpdateContract 治理门 → version=N+1 → hash → 原子持久化。
  3. boot/reload：唯一 S2，无历史建初始态，有历史恢复最后 committed 态。

明确 NOT（Step 1 不做，留待 Step 2）：
  - ✗ S1→S2 迁移 / Self Claim→Delta 生成。
  - ✗ 7 域归并（Situation/Worldview）。
  - ✗ 生产 Thinking 接线（Step 3）。

关键红线：
  - 新增专属 `self_state` 表，**不复用** agent_self_model(S1) 作真身。
  - agent_self_model(S1) 保持 S1 Evidence 身份：本模块**不写它、不依赖它**反推 S2。
  - Prompt 文本 / S1 实时值**不是** persistence source；content_hash 只由提交态 canonical 计算。
  - 唯一 S2 真身由属主（AgentRuntime）经 `SelfStateManager` 独占持有；
    Thinking 只能经唯一 accessor（`SelfProjectionAccessor`）读取 S2 投影。
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import types as _types
import typing
from dataclasses import MISSING, dataclass, field, fields, is_dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from ocos.storage.connection import get_connection, transaction
from ocos.storage.migrations import ensure_schema
from ocos.storage.schema import TABLE_SELF_STATE

# ── S2 类型导入（serializer 注册表 与 类型重建用）────────────────────────────
from ocos.self.self_types import (
    CapabilityStatement,
    DomainStatement,
    ExperiencePattern,
    KnowledgeConfidence,
    PreferenceEntry,
    PreferenceType,
    SelfBoundaryRules,
    SelfModel,
    SelfUpdateContract,
    SelfUpdateSource,
)
from ocos.self.capability_awareness import CapabilityAwareness
from ocos.self.knowledge_boundary import KnowledgeBoundary
from ocos.self.experience_profile import ExperienceProfile
from ocos.self.preference_model import PreferenceModel
from ocos.self.cognitive_state import AttentionHealth, CognitiveLoad, CognitiveState

logger = logging.getLogger(__name__)

# update_history 落库保留上限（FROZEN §STEP0#2 "有限 update_history"）。
_MAX_PERSISTED_HISTORY = 20


class SelfStateError(Exception):
    """S2 持久化/所有权 基类异常。"""


class SelfStateIntegrityError(SelfStateError):
    """提交态内容与 content_hash 不符（怀疑被篡改/损坏）。"""


class SelfStateVersionConflict(SelfStateError):
    """版本不是当前 committed 的 N+1，拒绝提交（保证单调递增）。"""


class SelfStateRejected(SelfStateError):
    """治理门拒绝（SelfUpdateContract 边界校验失败 或 identity_ref 不符）。"""


class SelfStateNotBooted(SelfStateError):
    """尚未 boot 就尝试更新/投影。"""


# ═══════════════════════════════════════════════════════════════════════════════
# canonical serialization（Step 1b）
# ═══════════════════════════════════════════════════════════════════════════════

# dataclass 实例 → 类名注册表（重建时按 __type 标签查找）。
_TYPE_REGISTRY: dict[str, type] = {
    cls.__name__: cls
    for cls in (
        CapabilityStatement,
        DomainStatement,
        ExperiencePattern,
        PreferenceEntry,
        KnowledgeConfidence,
        PreferenceType,
        SelfBoundaryRules,
        SelfModel,
        SelfUpdateContract,
        SelfUpdateSource,
        CapabilityAwareness,
        KnowledgeBoundary,
        ExperienceProfile,
        PreferenceModel,
        AttentionHealth,
        CognitiveLoad,
        CognitiveState,
    )
}


def _to_canonical(obj):
    """把 S2 任意 dataclass/Enum/datetime 转成固定顺序 primitive 树。

    固定顺序规则：
      - dataclass 字段按 **声明顺序**（dataclasses.fields 有序）。
      - dataclass 实例打 `__type` 标签，重建时按注册表还原。
      - Enum → .value（字符串）；datetime → ISO-8601。
      - dict/list/tuple 保持顺序；与字段类型无关，抽象为通用 primitive。
    """
    if is_dataclass(obj) and not isinstance(obj, type):
        out: dict = {"__type": type(obj).__name__}
        for f in fields(obj):
            out[f.name] = _to_canonical(getattr(obj, f.name))
        return out
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {_to_canonical(k): _to_canonical(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_canonical(x) for x in obj]
    return obj


def serialize_state(state: SelfModel) -> tuple[str, str]:
    """返回 (state_json, content_hash)。

    content_hash 由**提交态** canonical 计算（非 Prompt、非 S1 实时值）。
    只保存有限的 update_history（FROZEN §STEP0#2）。
    """
    carry = state
    if len(state.update_history) > _MAX_PERSISTED_HISTORY:
        carry = replace(
            state,
            update_history=list(state.update_history[-_MAX_PERSISTED_HISTORY:]),
        )
    canonical = _to_canonical(carry)
    state_json = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
    return state_json, _hash(state_json)


def _hash(state_json: str) -> str:
    return hashlib.sha256(state_json.encode("utf-8")).hexdigest()


def _default_for(f):
    """字段缺省值：literal default 优先，default_factory 次之，否则 None。"""
    if f.default is not MISSING:
        return f.default
    if f.default_factory is not MISSING:
        return f.default_factory()
    return None


def _rebuild(value):
    """根据 canonical partition 重建 dataclass 实例（含 __type 标签递归）。"""
    if isinstance(value, dict) and "__type" in value:
        cls = _TYPE_REGISTRY.get(value["__type"])
        if cls is None:
            raise SelfStateIntegrityError(f"unknown type tag: {value['__type']}")
        hints = typing.get_type_hints(cls)
        kwargs = {
            f.name: _rebuild_typed(hints[f.name], value.get(f.name, _default_for(f)))
            for f in fields(cls)
        }
        return cls(**kwargs)
    if isinstance(value, list):
        # 列表元素带 __type 标签时逐个重建；原始 primitive 原样返回。
        return [
            _rebuild(x) if isinstance(x, dict) and "__type" in x else x
            for x in value
        ]
    return value


def _rebuild_typed(hint, value):
    if value is None:
        return None
    # dataclass 值走 __type 标签重建（对 Optional[Any]/dict 值同样适用）
    if isinstance(value, dict):
        if "__type" in value:
            return _rebuild(value)
        origin = typing.get_origin(hint)
        if origin is dict:
            kt, vt = typing.get_args(hint)
            return {
                _rebuild_typed(kt, k): _rebuild_typed(vt, v)
                for k, v in value.items()
            }
        return value
    origin = typing.get_origin(hint)
    if origin in (list, set, frozenset, tuple):
        args = typing.get_args(hint)
        if origin is tuple:
            if len(args) == 2 and args[1] is Ellipsis:
                return tuple(_rebuild_typed(args[0], x) for x in value)
            return tuple(_rebuild_typed(a, x) for a, x in zip(args, value))
        elem = args[0]
        return origin(_rebuild_typed(elem, x) for x in value)
    if origin in (typing.Union, _types.UnionType):
        args = [a for a in typing.get_args(hint) if a is not type(None)]
        if not args:
            return value
        return _rebuild_typed(args[0], value)
    if isinstance(hint, type) and issubclass(hint, Enum):
        return hint(value)
    if hint is datetime:
        return datetime.fromisoformat(value)
    return value


def deserialize_state(state_json: str, content_hash: str | None = None) -> SelfModel:
    """从 canonical JSON 重建 SelfModel，并校验 content_hash（用/不用写保护）。

    content_hash 非 None 时做完整性校验：任一 corrupt 即抛 SelfStateIntegrityError。
    """
    if content_hash is not None:
        if _hash(state_json) != content_hash:
            raise SelfStateIntegrityError(
                "content_hash mismatch (state may be tampered/corrupt)"
            )
    canonical = json.loads(state_json)
    rebuilt = _rebuild(canonical)
    if not isinstance(rebuilt, SelfModel):
        raise SelfStateIntegrityError("state_json root is not a SelfModel")
    return rebuilt


# ═══════════════════════════════════════════════════════════════════════════════
# SelfStateStore — 专属持久化载体 + 原子 commit（Step 1a / 1c）
# ═══════════════════════════════════════════════════════════════════════════════


class SelfStateStore:
    """`self_state` 表的读写与原子提交（S2 专属，不复用 agent_self_model）。

    单条 identity 一行 = 最新 committed 态。所有写入走事务；失败即回滚，
    不产生半状态。commit 强制版本严格 = 当前 N+1（保证单调递增）。
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def initialize(self) -> None:
        ensure_schema(self._db_path)

    def exists(self, identity_ref: str) -> bool:
        conn = get_connection(self._db_path)
        row = conn.execute(
            f"SELECT 1 FROM {TABLE_SELF_STATE} WHERE identity_ref = ?",
            (identity_ref,),
        ).fetchone()
        return row is not None

    def load(self, identity_ref: str) -> SelfModel | None:
        """加载最后一个 committed 态（含完整性校验）。无历史返回 None。"""
        conn = get_connection(self._db_path)
        row = conn.execute(
            f"SELECT version, state_json, content_hash, updated_at "
            f"FROM {TABLE_SELF_STATE} WHERE identity_ref = ?",
            (identity_ref,),
        ).fetchone()
        if row is None:
            return None
        state = deserialize_state(row["state_json"], row["content_hash"])
        if state.identity_ref != identity_ref:
            raise SelfStateIntegrityError(
                "stored identity_ref does not match query key (tampered)"
            )
        return state

    def commit(self, state: SelfModel) -> None:
        """原子提交一个 committed 态。事务失败则回滚，旧状态保持完整。"""
        state_json, content_hash = serialize_state(state)
        with transaction(self._db_path) as conn:
            row = conn.execute(
                f"SELECT version FROM {TABLE_SELF_STATE} WHERE identity_ref = ?",
                (state.identity_ref,),
            ).fetchone()
            current = int(row["version"]) if row else 0
            if state.version != current + 1:
                raise SelfStateVersionConflict(
                    f"expected version {current + 1}, got {state.version}"
                )
            conn.execute(
                f"INSERT OR REPLACE INTO {TABLE_SELF_STATE} "
                f"(identity_ref, version, state_json, content_hash, updated_at) "
                f"VALUES (?, ?, ?, ?, ?)",
                (
                    state.identity_ref,
                    state.version,
                    state_json,
                    content_hash,
                    state.updated_at.isoformat(),
                ),
            )

    def delete_all(self) -> int:
        """清空（仅测试用）。"""
        with transaction(self._db_path) as conn:
            return conn.execute(f"DELETE FROM {TABLE_SELF_STATE}").rowcount


# ═══════════════════════════════════════════════════════════════════════════════
# SelfStateManager — 唯一 S2 属主：boot/reload + 权威更新 + 唯一 accessor（Step 1d/1e）
# ═══════════════════════════════════════════════════════════════════════════════


def _make_initial(identity_ref: str) -> SelfModel:
    """合法初始状态：identity_ref + 空 5 组件 + 默认边界。

    注意：不从 IdentityAnchor 复制对象，只引用 agent_id 字符串（S40-01）。
    """
    now = datetime.now(timezone.utc)
    return SelfModel(
        identity_ref=identity_ref,
        version=1,
        created_at=now,
        updated_at=now,
        capability_awareness=CapabilityAwareness(),
        knowledge_boundary=KnowledgeBoundary(),
        experience_profile=ExperienceProfile(),
        preference_model=PreferenceModel(),
        cognitive_state=CognitiveState(),
        self_confidence=0.5,
        boundary_rules=SelfBoundaryRules(),
    )


class SelfStateManager:
    """S2 唯一属主，由 AgentRuntime 独占持有。

    - boot(identity_ref)：无历史 → 建初始态并原子提交 v1；有历史 → 恢复最后 committed 态。
      绝不通过 S1 重新"推导"一个 S2 作为 boot 真身。
    - commit_change(contract)：把已填充的 candidate 经治理门提交为 vN+1（幂等单调）。
    - build_candidate()：从当前 committed 态深拷贝一个 candidate，供模块填充后提交。
    - accessor：唯一只读 Self projection 入口。
    """

    def __init__(self, db_path: str) -> None:
        self._store = SelfStateStore(db_path)
        self._store.initialize()
        self._current: SelfModel | None = None
        self._identity_ref: str | None = None

    # ── boot / reload ─────────────────────────────────────────────────────

    def boot(self, identity_ref: str) -> SelfModel:
        """加载唯一 S2。无历史建初始态；有历史恢复最后 committed 态。"""
        if not isinstance(identity_ref, str) or not identity_ref.strip():
            raise SelfStateError(f"invalid identity_ref: {identity_ref!r}")
        self._identity_ref = identity_ref
        if self._store.exists(identity_ref):
            self._current = self._store.load(identity_ref)
            logger.info("S2 restored v%d for %s", self._current.version, identity_ref)
        else:
            self._current = _make_initial(identity_ref)
            self._store.commit(self._current)  # 原子提交 v1
            logger.info("S2 initialized v1 for %s", identity_ref)
        return self._current

    @property
    def current(self) -> SelfModel:
        if self._current is None:
            raise SelfStateNotBooted("S2 not booted yet")
        return self._current

    @property
    def identity_ref(self) -> str:
        return self.current.identity_ref

    @property
    def version(self) -> int:
        return self.current.version

    # ── 权威更新（Step 1c: candidate→contract→治理门→vN+1→hash→atomic）─────

    def build_candidate(self) -> SelfModel:
        """从当前 committed 态深拷贝一个 candidate（经 canonical 往返，纯新对象）。"""
        canonical = _to_canonical(self.current)
        return _rebuild(canonical)

    def commit_change(
        self, candidate: SelfModel, contract: SelfUpdateContract
    ) -> SelfModel:
        """治理门 → version=N+1 → hash → 原子提交 → 成为新 committed 态。

        唯一产生新 committed 状态的入口（persist 层）。
        治理门（SelfGovernor） = SelfBoundaryRules.is_update_allowed。
        失败（治理拒绝/identity 变更/密钥版本）不落任何半状态。
        """
        cur = self.current
        # 1) SelfGovernor / 边界治理门
        allowed, reason = cur.boundary_rules.is_update_allowed(contract)
        if not allowed:
            raise SelfStateRejected(f"governance gate denied: {reason}")
        # 2) identity_ref 只引不复制、不可变
        if candidate.identity_ref != cur.identity_ref:
            raise SelfStateRejected("identity_ref is immutable")
        # 3) candidate 必须是当前态派生的未缓冲版本 → 属主负责 bump 到 N+1
        if candidate.version != cur.version:
            raise SelfStateVersionConflict(
                f"candidate version {candidate.version} != current {cur.version}"
            )
        committed = replace(
            candidate,
            version=cur.version + 1,
            updated_at=datetime.now(timezone.utc),
            update_history=[*candidate.update_history, contract],  # provenance 入 update_history
        )
        # 4) hash + 原子持久化（版本冲突会被 store 二次拦截）
        self._store.commit(committed)
        self._current = committed
        return committed

    @property
    def accessor(self) -> "SelfProjectionAccessor":
        """唯一读 accessor —— Thinking / Self projection 的唯一入口。"""
        return SelfProjectionAccessor(self)


class SelfProjectionAccessor:
    """S2 唯一只读投影 —— 从**已提交**的 S2 生成，不复读 S1 实时 render。

    只读：不提供任何写路径。Thinking 只能消费此 accessor 的输出。
    """

    def __init__(self, manager: SelfStateManager) -> None:
        self._manager = manager

    @property
    def current(self) -> SelfModel:
        return self._manager.current

    @property
    def identity_ref(self) -> str:
        return self._manager.current.identity_ref

    @property
    def version(self) -> int:
        return self._manager.current.version

    @property
    def content_hash(self) -> str:
        state_json, h = serialize_state(self._manager.current)
        return h

    def project(self) -> dict:
        """返回已提交 S2 的只读投影（固定顺序 canonical 结构）。"""
        return _to_canonical(self._manager.current)

    def committed_claims(self) -> list[dict]:
        """P0-4 B: 已提交 S2 入账的 claim/evidence 清单（只读，无副作用）。

        供 Decision₂ attribution trace 判定"本次决策所见投影消费了哪些 D"。
        来源 = current.update_history 中的每个 SelfUpdateContract（含 claim_id +
        evidence_ids）。不写 S2、不改 render/brief/prompt 语义。
        """
        s = self._manager.current
        history = list(getattr(s, "update_history", None) or [])
        out: list[dict] = []
        for contract in history:
            cid = getattr(contract, "claim_id", "") or ""
            if not cid:
                continue
            out.append({
                "claim_id": cid,
                "evidence_ids": list(getattr(contract, "evidence_ids", ()) or ()),
                "target_component": list(getattr(contract, "fields_changed", ()) or ()),
            })
        return out

    def component_consumption(self, component: str) -> Optional[dict]:
        """P0-4A：决策时刻【实际读取的组件】→ decision-relevant consumption manifest。

        『我实际读了 self_projection.<component>』发生时即形成消费关系，而非读完
        再遍历 update_history 猜『哪个 claim 对应它』。机制：
          - 驱动变量是**被读取的组件名**（Decision₂ 真正访问的那一项）；
          - 返回该组件当前值由哪个已提交 SelfUpdateContract 写入（provenance：
            claim_id / evidence_ids）+ S2 版本 / content_hash。
        只读、无副作用；不重算决策、不决定 Action。组件无 provenance 返回 None。
        """
        s = self._manager.current
        history = list(getattr(s, "update_history", None) or [])
        for contract in reversed(history):
            fields = getattr(contract, "fields_changed", ()) or ()
            if component not in fields:
                continue
            cid = getattr(contract, "claim_id", "") or ""
            if not cid:
                continue
            return {
                "self_version": s.version,
                "claim_id": cid,
                "delta_id": cid,  # decision-relevant delta = 该 claim 的身份
                "evidence_ids": list(getattr(contract, "evidence_ids", ()) or ()),
                "target_component": component,
                "content_hash": self.content_hash,
            }
        return None

    def render(self) -> str:
        """文本投影：由已提交 S2 生成，非 Prompt 源、不读 S1。"""
        s = self._manager.current
        parts = [
            f"SelfState v{s.version} (identity_ref={s.identity_ref}, "
            f"confidence={s.self_confidence:.2f})",
        ]
        if s.capability_awareness:
            parts.append(f"  {s.capability_awareness.summary()}")
            ca = s.capability_awareness
            if ca.known:
                # 已提交 S2 的 known 全集 → 权威 7 域自我表示的一部分。
                # 确定性排序；标注可用性/置信度，Thinking 据此引用自身能力。
                names = sorted(ca.known)
                joined = ", ".join(
                    f"{n}{'✓' if ca.known[n].available else '✗'}"
                    for n in names)
                parts.append(f"  known capabilities: {joined}")
        if s.knowledge_boundary:
            parts.append(f"  {s.knowledge_boundary.summary()}")
        if s.experience_profile:
            parts.append(f"  {s.experience_profile.summary()}")
        if s.preference_model:
            parts.append(f"  {s.preference_model.summary()}")
        if s.cognitive_state:
            parts.append(f"  {s.cognitive_state.summary()}")
        return "\n".join(parts)

    def brief(self) -> str:
        """紧凑 Self 摘要（决策空间自注入用，≤~180 字级）。非 Prompt 源、不读 S1。

        Thinking / 记忆路由的自注入槽位，等价替代 S1.render_brief()。
        """
        s = self._manager.current
        bits: list[str] = []
        ca = s.capability_awareness
        if ca is not None and ca.known:
            bits.append("capabilities:" + ", ".join(sorted(ca.known))[:90])
        kb = s.knowledge_boundary
        if kb is not None and kb.needs_verification:
            domains = list(kb.needs_verification)[:3]
            bits.append("needs_verification:" + "; ".join(str(d) for d in domains)[:60])
        cs = s.cognitive_state
        if cs is not None and cs.active_focus:
            bits.append("focus:" + str(cs.active_focus)[:40])
        return " | ".join(bits)


# ── P0-1 Step 3：S2 → Thinking 的进程级唯一 accessor 路由 ─────────────────────
# Thinking 的 authoritative Self source 唯一来自 S2 committed projection。
# 生产 Prompt 路径（converse/bridge/recall_router）一律经此取 S2，**绝不回退 S1.render()**。


_S2_LOCK = threading.Lock()
_S2_ACCESSOR_REGISTRY: dict[str, "SelfProjectionAccessor"] = {}


def register_self_projection(db_path: str, accessor) -> None:
    """把已 boot 的 S2 accessor 注册为进程内 db 唯一 accessor（AgentRuntime boot 时调用）。"""
    if not db_path or db_path == ":memory:":
        return
    with _S2_LOCK:
        _S2_ACCESSOR_REGISTRY[db_path] = accessor


def _resolve_identity_ref(db_path: str) -> Optional[str]:
    """从持久化 identity 表解析唯一 agent_id（合法身份锚，非 S1 推导）。"""
    try:
        conn = get_connection(db_path)
        row = conn.execute("SELECT agent_id FROM identity LIMIT 1").fetchone()
        return str(row["agent_id"]) if row else None
    except Exception:
        return None


def get_self_projection(db_path: str, identity_ref: Optional[str] = None):
    """进程内 S2 唯一只读 projection（committed → 7-domain Self representation）。

    - 优先返回已注册（runtime boot）的 accessor；否则按身份从持久化 reload committed S2。
    - restart 后为持久化恢复的 committed 态，**不是**从 S1 重新构造。
    - 无持久化载体(:memory:) 或 identity 不可解析 → None（调用方降级为空，绝不回退 S1）。
    """
    if not db_path or db_path == ":memory:":
        return None
    with _S2_LOCK:
        acc = _S2_ACCESSOR_REGISTRY.get(db_path)
        if acc is not None:
            return acc
    ident = identity_ref or _resolve_identity_ref(db_path)
    if not ident:
        return None
    manager = SelfStateManager(db_path)
    manager.boot(ident)
    acc = manager.accessor
    with _S2_LOCK:
        _S2_ACCESSOR_REGISTRY.setdefault(db_path, acc)
    return acc


__all__ = [
    "SelfStateError",
    "SelfStateIntegrityError",
    "SelfStateVersionConflict",
    "SelfStateRejected",
    "SelfStateNotBooted",
    "SelfStateStore",
    "SelfStateManager",
    "SelfProjectionAccessor",
    "register_self_projection",
    "get_self_projection",
    "serialize_state",
    "deserialize_state",
]