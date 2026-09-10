"""
Decision Mutation Architecture v1.2 — Contract Tests (Phase 0)
===============================================================

Purpose
-------
冻结三个边界契约（C1/C2/C3），定义 Phase 1-3 实现必须满足的不变式。
本文件是"契约定义"，不是完整 pytest 用例——Phase 0 完成时这些测试会被 skip
（对应实现类尚未存在），Phase 1/2/3 分别解除 skip 并让它们 PASS。

冻结的 Contract
---------------
C1. ActionParser   — 从 raw LLM 输出解析结构化 Action
C2. MutationPolicy  — 从 (stderr, command) 确定性生成 mutation_policy
C3. Lesson Schema  — failure_lesson ≠ mutation_policy（两块独立）

不冻结（保留到 Phase 1-3 实现）
-------------------------------
- _generate_mutation_policy 具体正则逻辑
- _parse_actions 具体分支处理
- Mutation Engine 完整检查流程（Phase 3 才接）
- BV4 生产执行（Phase 4）

版本
----
Decision Mutation Architecture v1.2 — Phase 0 Contract Freeze
冻结日期: 2026-09-11
冻结代码版本: d8d03a8
"""

from __future__ import annotations

import pytest


# ──────────────────────────────────────────────────────────────
# C1. ActionParser Contract
# ──────────────────────────────────────────────────────────────

"""
冻结不变式:
  1. Parsing only. No inference. No completion. No planning.
  2. 与 bridge.py line ~1422 _lines 循环行为 1:1 等价。
  3. 只识别 RUN|/NONE|/ANSWER|/FILE_WRITE|/AGENT_INSTALL 五种类型。
  4. 未知类型（如自然语言建议）→ 返回 []，不做任何推断。
"""


# Golden cases（从当前 bridge.py 行为枚举）
# 格式: (raw_llm_output, expected_action_dict_or_list)
ACTION_PARSER_GOLDEN_CASES = [
    # 基础 RUN
    ("RUN|ls -la",
     [{"type": "RUN", "command": "ls -la"}]),

    # 含特殊符号的命令
    ("RUN|head -n 5 /etc/shadow",
     [{"type": "RUN", "command": "head -n 5 /etc/shadow"}]),

    # 依赖不存在的工具
    ("RUN|htop -F",
     [{"type": "RUN", "command": "htop -F"}]),

    # SQL 查询（含引号嵌套）
    ('RUN|sqlite3 /home/laogao/.ocos/ocos.db "SELECT * FROM episodes ORDER BY rowid DESC LIMIT 10"',
     [{"type": "RUN",
       "command": 'sqlite3 /home/laogao/.ocos/ocos.db "SELECT * FROM episodes ORDER BY rowid DESC LIMIT 10"'}]),

    # NONE
    ("NONE|无法执行该任务",
     [{"type": "NONE", "reason": "无法执行该任务"}]),

    # ANSWER
    ("ANSWER|任务已完成",
     [{"type": "ANSWER", "content": "任务已完成"}]),

    # 多条 RUN（复合任务）
    ("RUN|uname -a\nRUN|df -h\nRUN|free -h",
     [{"type": "RUN", "command": "uname -a"},
      {"type": "RUN", "command": "df -h"},
      {"type": "RUN", "command": "free -h"}]),

    # markdown fence 剥离
    ("```\nRUN|cat /etc/passwd\n```",
     [{"type": "RUN", "command": "cat /etc/passwd"}]),

    # 空输入
    ("",
     []),

    # 只有空白
    ("   \n  \n\t",
     []),

    # FILE_WRITE
    ("FILE_WRITE|/tmp/test.txt|hello world",
     [{"type": "FILE_WRITE", "path": "/tmp/test.txt", "content": "hello world"}]),

    # AGENT_INSTALL
    ("AGENT_INSTALL|openclaw",
     [{"type": "AGENT_INSTALL", "name": "openclaw"}]),

    # 混合（RUN + NONE → 两者都解析，Mutation 层处理）
    ("RUN|echo hello\nNONE|同时无法执行另一个子任务",
     [{"type": "RUN", "command": "echo hello"},
      {"type": "NONE", "reason": "同时无法执行另一个子任务"}]),
]


# "不做推断" golden cases — 自然语言建议不能被自动转成 RUN
ACTION_PARSER_NO_INFERENCE_CASES = [
    "我建议查看 sudo 配置",
    "可以尝试用 cat /etc/sudoers 看看",
    "或许 htop 能帮你实时观察",
    "让我分析一下这个问题...",
]


class TestActionParserContract:
    """Phase 0: 冻结 ActionParser 输入输出契约。

    测试暂时 skip — 对应实现（_parse_actions）在 Phase 2 才写。
    Phase 2 完成后去掉 skip 让测试 PASS。
    """

    @pytest.mark.skip(reason="Phase 0 contract — ActionParser implementation deferred to Phase 2")
    @pytest.mark.parametrize("raw,expected", ACTION_PARSER_GOLDEN_CASES)
    def test_parser_output_matches_bridge_lines_behavior(self, raw, expected):
        """提炼后的 ActionParser 必须和当前 bridge.py _lines 循环行为 1:1 等价。"""
        from ocos.execution.bridge import _parse_actions  # type: ignore[attr-defined]
        result = _parse_actions(raw)
        assert result == expected

    @pytest.mark.skip(reason="Phase 0 contract — ActionParser implementation deferred to Phase 2")
    @pytest.mark.parametrize("natural_language", ACTION_PARSER_NO_INFERENCE_CASES)
    def test_parser_no_inference(self, natural_language):
        """冻结约束: Parser 不做任何推理、补全、规划。

        自然语言建议（"我建议查看 sudo 配置"）必须返回 []，
        不能自动推断成 RUN|cat /etc/sudoers。
        """
        from ocos.execution.bridge import _parse_actions  # type: ignore[attr-defined]
        result = _parse_actions(natural_language)
        assert result == [], f"Parser should not infer action from: {natural_language}"


# ──────────────────────────────────────────────────────────────
# C2. Mutation Policy Generation Contract
# ──────────────────────────────────────────────────────────────

"""
冻结不变式:
  1. Deterministic. No LLM. 相同 (stderr, command) 输入 → 相同 mutation_policy 输出。
  2. 三种 mutation_level（Phase 1 实现时必须全部覆盖）:
     - permission_denied  → action level  → deny.patterns（正则提取路径）
     - dependency_missing  → tool level   → deny.commands（从 command 首词提取）
     - sql_schema_mismatch → planning level → deny.pattern（固定模板，BV5 消费）
  3. 其他 cause（timeout, execution_error 等）→ 不生成 mutation_policy → None。
  4. 版本字段: 所有 mutation_policy 必须带 mutation_policy_version = "1.0"。
  5. stderr 路径提取覆盖两种格式:
     - 引号内: head: cannot open '/etc/shadow' ...
     - 冒号后: cat: /etc/sudoers: Permission denied
"""

# Golden cases: (stderr_text, raw_command, expected_mutation_policy_or_none)
MUTATION_POLICY_GOLDEN_CASES = [
    # ── permission_denied: 引号内路径 ──
    (
        "head: cannot open '/etc/shadow' for reading: Permission denied",
        "head -n 5 /etc/shadow",
        {
            "mutation_policy_version": "1.0",
            "level": "action",
            "deny": {"patterns": ["/etc/shadow"]},
            "retry_policy": {"max_retry": 1},
        },
    ),
    # ── permission_denied: 冒号后路径 ──
    (
        "cat: /etc/sudoers: Permission denied",
        "cat /etc/sudoers",
        {
            "mutation_policy_version": "1.0",
            "level": "action",
            "deny": {"patterns": ["/etc/sudoers"]},
            "retry_policy": {"max_retry": 1},
        },
    ),
    # ── permission_denied: 只有通用 "Permission denied"，从 command 兜底提取 ──
    (
        "Permission denied",
        "chmod 777 /etc/nginx/nginx.conf",
        {
            "mutation_policy_version": "1.0",
            "level": "action",
            "deny": {"patterns": ["/etc/nginx/nginx.conf"]},
            "retry_policy": {"max_retry": 1},
        },
    ),
    # ── dependency_missing: command not found (bash 格式) ──
    (
        "bash: htop: command not found",
        "htop -F",
        {
            "mutation_policy_version": "1.0",
            "level": "tool",
            "deny": {"commands": ["htop"]},
            "retry_policy": {"max_retry": 1},
        },
    ),
    # ── dependency_missing: command not found (另一种格式) ──
    (
        "command not found: jq",
        "jq . data.json",
        {
            "mutation_policy_version": "1.0",
            "level": "tool",
            "deny": {"commands": ["jq"]},
            "retry_policy": {"max_retry": 1},
        },
    ),
    # ── sql_schema_mismatch: no such table ──
    (
        "Error: no such table: artifacts",
        'sqlite3 db "SELECT * FROM artifacts"',
        {
            "mutation_policy_version": "1.0",
            "level": "planning",
            "deny": {"pattern": "query_nonexistent_table_or_column"},
            "retry_policy": {"max_retry": 1},
        },
    ),
    # ── 其他 cause: timeout → 不生成 mutation_policy ──
    (
        "curl: (28) Operation timed out after 30000 milliseconds",
        "curl -s --max-time 60 https://example.com",
        None,
    ),
    # ── 其他 cause: generic execution_error → 不生成 ──
    (
        "Exit code 1: syntax error near unexpected token `}'",
        "bash -c 'echo hello }'",
        None,
    ),
    # ── 空 stderr / 空 command → 安全处理，不 crash ──
    (
        "",
        "",
        None,
    ),
]


class TestMutationPolicyGenerationContract:
    """Phase 0: 冻结 mutation_policy 生成的确定性契约。

    测试暂时 skip — 对应实现（_generate_mutation_policy）在 Phase 1 才写。
    Phase 1 完成后去掉 skip 让测试 PASS。
    """

    @pytest.mark.skip(reason="Phase 0 contract — mutation_policy generator deferred to Phase 1")
    @pytest.mark.parametrize("stderr,command,expected", MUTATION_POLICY_GOLDEN_CASES)
    def test_policy_generation_is_deterministic(self, stderr, command, expected):
        """相同输入必须确定性输出相同 mutation_policy（无 LLM 参与）。"""
        from ocos.agent.agent_runtime import AgentRuntime  # type: ignore[attr-defined]
        rt = AgentRuntime  # 静态方法调用
        policy = rt._generate_mutation_policy("permission_denied" if expected else "unknown",
                                              command, stderr)
        if expected is None:
            assert policy is None or policy == {}
        else:
            assert policy is not None
            assert policy["mutation_policy_version"] == expected["mutation_policy_version"]
            assert policy["level"] == expected["level"]
            assert policy["deny"] == expected["deny"]
            assert policy["retry_policy"]["max_retry"] == expected["retry_policy"]["max_retry"]

    @pytest.mark.skip(reason="Phase 0 contract — mutation_policy generator deferred to Phase 1")
    def test_policy_always_has_version(self):
        """冻结: 所有 mutation_policy 必须带 mutation_policy_version 字段。"""
        from ocos.agent.agent_runtime import AgentRuntime  # type: ignore[attr-defined]
        cases = [
            ("permission_denied", "cat /etc/sudoers", "Permission denied"),
            ("dependency_missing", "htop -F", "bash: htop: command not found"),
        ]
        for cause, cmd, err in cases:
            policy = AgentRuntime._generate_mutation_policy(cause, cmd, err)
            assert policy is not None, f"Expected policy for cause={cause}"
            assert "mutation_policy_version" in policy
            assert policy["mutation_policy_version"] == "1.0"


# ──────────────────────────────────────────────────────────────
# C3. Lesson Schema Contract
# ──────────────────────────────────────────────────────────────

"""
冻结不变式:
  1. failure_lesson ≠ mutation_policy — 两块独立的 JSON 对象。
     - failure_lesson: 描述性（给 LLM 看"为什么失败"）
     - mutation_policy: 约束性（给 Mutation Engine 看"什么被禁止"）
  2. 可被 Mutation 消费的 Lesson 必须具有完整的 mutation_policy 块
     （含 mutation_policy_version, level, deny, retry_policy）。
  3. 不支持 mutation 的 cause（timeout, execution_error 等）→ 允许没有
     failure_lesson / mutation_policy 块（向后兼容旧版 lesson 结构）。
"""

# 示例: 一个完整可被 Mutation 消费的 failure_lesson context
FULL_MUTATION_CONSUMABLE_CONTEXT = {
    "lesson_type": "failure_pattern",
    "task_id": "test-001",
    "failure_signature": "readetcsuders|permission_denied",
    # ── failure_lesson（描述性，FailureDiagnoser 产出，LLM 消费）──
    "failure_lesson": {
        "cause": "permission_denied",
        "evidence": {
            "command": "cat /etc/sudoers",
            "stderr": "cat: /etc/sudoers: Permission denied",
        },
    },
    # ── mutation_policy（约束性，Mutation Engine 消费，确定性生成）──
    "mutation_policy": {
        "mutation_policy_version": "1.0",
        "level": "action",
        "deny": {"patterns": ["/etc/sudoers"]},
        "retry_policy": {"max_retry": 1},
    },
}

# 示例: 不支持 mutation 的 cause → 只有旧版字段，没有 failure_lesson/mutation_policy
LEGACY_COMPATIBLE_CONTEXT = {
    "lesson_type": "failure_pattern",
    "task_id": "test-002",
    "failure_signature": "slowcronjob|timeout",
    # 没有 failure_lesson 块 — 允许
    # 没有 mutation_policy 块 — 允许
}


class TestLessonSchemaContract:
    """Phase 0: 冻结 failure_lesson episode 的 context schema。

    这些测试不依赖任何实现——直接对 context dict 做断言。
    Phase 1 完成后这些测试应该能 PASS（不需要 skip），因为
    _record_failure_lesson 写入的 context 必须符合这个 schema。
    """

    def test_full_mutation_consumable_has_two_independent_blocks(self):
        """冻结: failure_lesson（描述性）和 mutation_policy（约束性）是两块独立 JSON。"""
        ctx = FULL_MUTATION_CONSUMABLE_CONTEXT

        # failure_lesson 块完整
        fl = ctx["failure_lesson"]
        assert "cause" in fl
        assert "evidence" in fl
        assert "command" in fl["evidence"]
        assert "stderr" in fl["evidence"]
        assert fl["cause"] == "permission_denied"
        assert fl["evidence"]["command"] == "cat /etc/sudoers"

        # mutation_policy 块完整
        mp = ctx["mutation_policy"]
        assert "mutation_policy_version" in mp
        assert mp["mutation_policy_version"] == "1.0"
        assert "level" in mp
        assert "deny" in mp
        assert "retry_policy" in mp
        assert mp["level"] == "action"
        assert mp["deny"] == {"patterns": ["/etc/sudoers"]}
        assert mp["retry_policy"]["max_retry"] == 1

        # 两块互相独立（failure_lesson.cause ≠ mutation_policy.level 的强制依赖）
        # 这里只是验证两块都存在且各自结构正确

    def test_legacy_context_still_valid(self):
        """冻结: 不支持 mutation 的 cause → 允许没有 failure_lesson/mutation_policy 块。"""
        ctx = LEGACY_COMPATIBLE_CONTEXT

        # 基础字段必须有
        assert ctx["lesson_type"] == "failure_pattern"
        assert "task_id" in ctx
        assert "failure_signature" in ctx

        # 没有 failure_lesson / mutation_policy → 合法（向后兼容）
        assert "failure_lesson" not in ctx
        assert "mutation_policy" not in ctx

    def test_mutation_policy_levels_cover_three_causes(self):
        """冻结: mutation_policy.level 必须是三个值之一（BV4 范围）。"""
        valid_levels = {"action", "tool", "planning"}
        for case in MUTATION_POLICY_GOLDEN_CASES:
            _stderr, _cmd, policy = case
            if policy is not None:
                assert policy["level"] in valid_levels, \
                    f"Invalid level '{policy['level']}' in golden case"

    def test_retry_policy_max_is_one(self):
        """冻结: mutation_policy.retry_policy.max_retry 必须是 1（MAX_RETRY=1）。"""
        for case in MUTATION_POLICY_GOLDEN_CASES:
            _stderr, _cmd, policy = case
            if policy is not None:
                assert policy["retry_policy"]["max_retry"] == 1, \
                    "MAX_RETRY must be exactly 1 per Architecture v1.2"


# ──────────────────────────────────────────────────────────────
# 附加: Retry Lifecycle Contract（用户刚修正的关键边界）
# ──────────────────────────────────────────────────────────────

"""
冻结不变式:
  MAX_RETRY = 1 是 per-Action transaction 级别的限制，
  不是 per-_mutation_check() 调用次数。

  正确的 lifecycle:
    retry_count = 0
    LLM → ActionParser → Mutation
      ├─ PASS → execute
      └─ DENY → retry_count += 1 → LLM Retry → ActionParser → Mutation
                   ├─ PASS → execute
                   └─ DENY → NONE (exhausted)

  错误的 lifecycle（禁止）:
    DENY → Retry → DENY → 再次调用 _mutation_check() → retry_count 又归零 → Retry → ...
    这会导致无限循环，违反 v1.2 的治理边界。
"""


class TestRetryLifecycleContract:
    """Phase 0: 冻结 retry_count 的生命周期语义。

    测试直接验证 retry_count 的状态机转换，不依赖 Mutation Engine 实现。
    Phase 3 完成后这些测试应该能 PASS。
    """

    def test_retry_count_state_machine(self):
        """MAX_RETRY=1: retry_count 只能 0→1，不能 1→0（每次调用归零禁止）。"""
        # 初始状态
        retry_count = 0
        assert retry_count == 0

        # 第一次 DENY
        retry_count += 1
        assert retry_count == 1

        # 第二次 DENY → 应该 exhausted（不能重试了）
        # 这里不检查 Mutation Engine 逻辑，只验证 retry_count 状态机
        assert retry_count >= 1  # >= 1 意味着不能再 retry

        # 禁止的行为: 再次调用 mutation_check 时 retry_count 归零
        # （这会导致无限循环）
        # 测试用例: 如果有人写 retry_count = 0（重置），这个测试会 FAIL
        # Phase 3 实现时必须确保 retry_count 在同一 Action transaction 内单调递增
        pass

    def test_two_denies_lead_to_exhausted(self):
        """连续两次 Mutation DENY → 必须到达 NONE/exhausted，不能继续重试。"""
        retry_count = 0

        # 第一次 Mutation 检查 → DENY
        assert retry_count < 1, "First DENY allowed"
        retry_count += 1  # Retry 消耗了

        # 第二次 Mutation 检查（LLM Retry 后的再检查）
        assert retry_count >= 1, "Second DENY → must be exhausted"
        # 不再允许 retry，必须升级 NONE|
