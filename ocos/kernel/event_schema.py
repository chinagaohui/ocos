"""
OCOS Event Schema — Event 定义与序列化。

对应宪法 Part 2: Event Model。
提供 Event 的 JSON 序列化/反序列化，以及 schema 版本验证。
"""

from __future__ import annotations

import json
from typing import Any

from ocos.kernel.abi import Event, EventType, SCHEMA_VERSION



# ── Event Type Schema Registry ──────────────────────────────────────────────────

EVENT_SCHEMA_REGISTRY: dict[EventType, dict[str, Any]] = {
    EventType.OBSERVATION_RECEIVED: {
        "description": "系统收到外部观察",
        "required_payload_fields": ["content", "source"],
    },
    EventType.OBSERVATION_VALIDATED: {
        "description": "观察验证通过",
        "required_payload_fields": ["observation_id", "is_valid"],
    },
    EventType.MEMORY_STORED: {
        "description": "记忆已存储",
        "required_payload_fields": ["memory_id", "operation"],
    },
    EventType.MEMORY_RETRIEVED: {
        "description": "记忆已检索",
        "required_payload_fields": ["memory_id", "operation"],
    },
    EventType.KNOWLEDGE_CANDIDATE_PROPOSED: {
        "description": "知识候选提出（需 Governance 审批）",
        "required_payload_fields": ["knowledge_id", "level", "content"],
    },
    EventType.KNOWLEDGE_PROMOTED: {
        "description": "知识提升成功",
        "required_payload_fields": ["knowledge_id", "from_level", "to_level"],
    },
    EventType.KNOWLEDGE_DEPRECATED: {
        "description": "知识已弃用",
        "required_payload_fields": ["knowledge_id", "reason"],
    },
    # ── Resource ───────────────────────────────────────────────────────────
    EventType.RESOURCE_EXHAUSTED: {
        "description": "资源耗尽告警",
        "required_payload_fields": ["resource_name", "current_usage"],
    },
    EventType.RESOURCE_RELEASED: {
        "description": "资源已释放",
        "required_payload_fields": ["resource_name", "released_amount"],
    },

    # ── Adaptive Control ───────────────────────────────────────────────────
    EventType.ADAPTATION_APPLIED: {
        "description": "自适应控制已应用",
        "required_payload_fields": ["target", "strategy", "reason"],
    },

    # ── Trace ──────────────────────────────────────────────────────────────
    EventType.TRACE_RECORDED: {
        "description": "追踪记录",
        "required_payload_fields": ["trace_id", "trace_type"],
    },

    # ── Audit ──────────────────────────────────────────────────────────────
    EventType.AUDIT_CHECK_PASSED: {
        "description": "审计检查通过",
        "required_payload_fields": ["check_name", "target"],
    },
    EventType.AUDIT_CHECK_FAILED: {
        "description": "审计检查未通过",
        "required_payload_fields": ["check_name", "target", "reason"],
    },

    # ── Information ────────────────────────────────────────────────────────
    EventType.INFORMATION_DELETED: {
        "description": "Information 已从系统删除",
        "required_payload_fields": ["address", "reason", "governance_approval_id"],
    },

    # ── Information 系列事件（INFORMATION_LIFECYCLE 生命周期契约） ───────────
    EventType.INFORMATION_CREATED: {
        "description": "Information 已创建（对应 Acquire 阶段）",
        "required_payload_fields": ["address", "semantic_role", "persistence", "content_summary"],
    },
    EventType.INFORMATION_VALIDATED: {
        "description": "Information 已验证（对应 Validate 阶段）",
        "required_payload_fields": ["address", "is_valid", "validation_detail"],
    },
    EventType.INFORMATION_STATUS_CHANGED: {
        "description": "Information 状态变更（对应 Decay / Archive 阶段）",
        "required_payload_fields": ["address", "new_status"],
    },
    EventType.INFORMATION_QUERIED: {
        "description": "Information 查询（RPC 式请求-响应）",
        "required_payload_fields": ["query_type", "query_params"],
    },
    EventType.RELATION_CREATED: {
        "description": "关系已创建",
        "required_payload_fields": ["source_address", "target_address", "relation_type"],
    },
    EventType.RELATION_REMOVED: {
        "description": "关系已移除",
        "required_payload_fields": ["source_address", "target_address", "relation_type"],
    },
    # ── Process (Phase 15 — Process Foundation) ──────────────────────
    EventType.INFORMATION_TRANSFORMATION_STARTED: {
        "description": "Information 转换过程已开始",
        "required_payload_fields": ["process_id", "process_type", "input_addresses"],
    },
    EventType.INFORMATION_TRANSFORMATION_COMPLETED: {
        "description": "Information 转换过程已完成",
        "required_payload_fields": ["process_id", "process_type", "output_addresses"],
    },
    EventType.INFORMATION_TRANSFORMATION_FAILED: {
        "description": "Information 转换过程失败",
        "required_payload_fields": ["process_id", "process_type", "error"],
    },
    # ── Process Runtime (Phase 18) ──────────────────────────────────
    EventType.PROCESS_CREATED: {
        "description": "Process 已创建",
        "required_payload_fields": ["process_id", "process_type"],
    },
    EventType.PROCESS_STARTED: {
        "description": "Process 已开始执行",
        "required_payload_fields": ["process_id"],
    },
    EventType.PROCESS_COMPLETED: {
        "description": "Process 已完成",
        "required_payload_fields": ["process_id"],
    },
    EventType.PROCESS_FAILED: {
        "description": "Process 失败",
        "required_payload_fields": ["process_id", "error"],
    },
    EventType.DECISION_FORMED: {
        "description": "决策已形成",
        "required_payload_fields": ["decision_id", "goal_id", "reasoning"],
    },
    EventType.DECISION_VALIDATED: {
        "description": "决策已通过 Policy 验证",
        "required_payload_fields": ["decision_id", "is_permitted"],
    },
    EventType.DECISION_REVOKED: {
        "description": "决策已被撤销",
        "required_payload_fields": ["decision_id", "reason"],
    },
    EventType.DECISION_SUPERSEDED: {
        "description": "决策已被新决策取代",
        "required_payload_fields": ["decision_id", "superseded_by"],
    },
    EventType.DECISION_EXPIRED: {
        "description": "决策已过期（超时或失去时效）",
        "required_payload_fields": ["decision_id", "reason"],
    },
    EventType.DECISION_EXECUTED: {
        "description": "决策已执行（COMMITTED → EXECUTED）",
        "required_payload_fields": ["decision_id"],
    },
    EventType.ACTION_PROPOSED: {
        "description": "Action 已被提出",
        "required_payload_fields": ["action_id", "decision_id", "action_type"],
    },
    EventType.ACTION_SCHEDULED: {
        "description": "Action 已被调度",
        "required_payload_fields": ["action_id", "priority"],
    },
    EventType.ACTION_EXECUTED: {
        "description": "Action 执行成功",
        "required_payload_fields": ["action_id", "result"],
    },
    EventType.ACTION_FAILED: {
        "description": "Action 执行失败",
        "required_payload_fields": ["action_id", "error"],
    },
    # ── Goal (Phase 17.2) ────────────────────────────────────────
    EventType.GOAL_SET: {
        "description": "Goal 被创建",
        "required_payload_fields": ["goal_id", "description"],
    },
    EventType.GOAL_UPDATED: {
        "description": "Goal 描述或优先级更新",
        "required_payload_fields": ["goal_id"],
    },
    EventType.GOAL_PAUSED: {
        "description": "Goal 被暂停",
        "required_payload_fields": ["goal_id"],
    },
    EventType.GOAL_RESUMED: {
        "description": "Goal 从暂停恢复",
        "required_payload_fields": ["goal_id"],
    },
    EventType.GOAL_COMPLETED: {
        "description": "Goal 达成",
        "required_payload_fields": ["goal_id"],
    },
    EventType.GOAL_FAILED: {
        "description": "Goal 判定为不可达",
        "required_payload_fields": ["goal_id", "reason"],
    },
    EventType.GOAL_CANCELLED: {
        "description": "Goal 被创建者撤销",
        "required_payload_fields": ["goal_id"],
    },
    EventType.GOAL_SUPERSEDED: {
        "description": "Goal 被新 Goal 替代",
        "required_payload_fields": ["goal_id", "superseded_by"],
    },
    EventType.GOAL_EXPIRED: {
        "description": "Goal 超时或失去时效",
        "required_payload_fields": ["goal_id"],
    },
    # ── Execution (Phase 17.1 — Theory → Code Alignment) ──────────
    EventType.EXECUTION_STARTED: {
        "description": "Execution 已开始执行",
        "required_payload_fields": ["execution_id", "decision_id"],
    },
    EventType.EXECUTION_COMPLETED: {
        "description": "Execution 已完成",
        "required_payload_fields": ["execution_id", "status"],
    },
    EventType.EXECUTION_FAILED: {
        "description": "Execution 执行失败",
        "required_payload_fields": ["execution_id", "error"],
    },
    EventType.EXECUTION_INTERRUPTED: {
        "description": "Execution 被中断",
        "required_payload_fields": ["execution_id", "reason"],
    },
    EventType.EXECUTION_CANCELLED: {
        "description": "Execution 被取消",
        "required_payload_fields": ["execution_id", "reason"],
    },
    EventType.SCHEDULER_TICK: {
        "description": "调度器心跳",
        "required_payload_fields": ["cycle"],
    },
    EventType.EMERGENCY_HALT: {
        "description": "系统紧急停止",
        "required_payload_fields": ["reason", "triggered_by"],
    },
    EventType.GOVERNANCE_APPROVAL_REQUESTED: {
        "description": "Governance 审批请求",
        "required_payload_fields": ["proposal_id", "proposal_type", "details"],
    },
    EventType.GOVERNANCE_APPROVED: {
        "description": "Governance 审批通过",
        "required_payload_fields": ["proposal_id", "approved_by"],
    },
    EventType.GOVERNANCE_REJECTED: {
        "description": "Governance 审批拒绝",
        "required_payload_fields": ["proposal_id", "reason"],
    },
    EventType.PLUGIN_LOADED: {
        "description": "插件已加载",
        "required_payload_fields": ["plugin_name", "version"],
    },
    EventType.PLUGIN_ERROR: {
        "description": "插件运行错误",
        "required_payload_fields": ["plugin_name", "error"],
    },
}


def validate_event_payload(event_type: EventType, payload: dict[str, Any]) -> bool:
    """验证 Event payload 是否包含该 Event 类型所需的必要字段。"""
    schema = EVENT_SCHEMA_REGISTRY.get(event_type)
    if schema is None:
        return False
    required = schema.get("required_payload_fields", [])
    for field in required:
        if field not in payload:
            return False
    return True
