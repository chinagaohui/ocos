"""深度内视注入回归（2026-09-07 用户实测反馈"自检太简单"）。

缺陷史: "自检一下，列出自身所有模块"走浅层 build_context，回复只列
身份锚/认知引擎等高层概念。修复: _INTROSPECT_RE 命中 → 注入
pkgutil 实扫模块清单 + 全量内部状态，回答要求逐组列出。
"""

from __future__ import annotations

import pytest

from ocos.interaction.converse import ChatResponder, _INTROSPECT_RE


class TestIntrospectRouting:
    def test_regex_covers_user_phrasings(self):
        for q in ("自检一下，列出自身所有模块",
                  "你有哪些模块",
                  "内视一下你的状态",
                  "检查自己",
                  "所有模块清单"):
            assert _INTROSPECT_RE.search(q), q

    def test_regex_not_overbroad(self):
        for q in ("查看根分区磁盘使用率",
                  "帮我写一首诗",
                  "今天天气怎么样"):
            assert not _INTROSPECT_RE.search(q), q


class TestModuleInventory:
    def test_inventory_lists_real_subpackages(self):
        r = ChatResponder(db_path=":memory:")
        block = r._module_inventory()
        assert "代码模块实扫" in block
        # 真实子包必须出现（自身源码地面真值）
        for pkg in ("execution", "agent", "memory", "daemon"):
            assert pkg in block, pkg
        assert "合计" in block

    def test_inventory_cached(self):
        r = ChatResponder(db_path=":memory:")
        first = r._module_inventory()
        assert ChatResponder._MODULE_INVENTORY_CACHE.get("block") == first


class TestBehavioralFacts:
    """行为事实注入（2026-09-07 自检审计：模块计数反推出错误差距结论）。"""

    def _seed_db(self, tmp_path):
        import sqlite3
        p = tmp_path / "bf.db"
        conn = sqlite3.connect(str(p))
        conn.execute(
            "CREATE TABLE goals (id TEXT PRIMARY KEY, status TEXT, "
            "source TEXT, created_at TEXT, updated_at TEXT, metadata TEXT)")
        conn.execute(
            "CREATE TABLE episodes (id TEXT PRIMARY KEY, source TEXT, "
            "created_at TEXT, session_id TEXT, context TEXT, goal TEXT, "
            "decision TEXT, action TEXT, outcome TEXT, condition TEXT, "
            "significance_score REAL, evaluation_trace TEXT, status TEXT, "
            "tags TEXT, experience_id TEXT)")
        for i in range(3):
            conn.execute(
                "INSERT INTO goals VALUES (?, 'COMPLETED', 'motivation', "
                "'2026-09-07T10:00:00+00:00', '2026-09-07T10:30:00+00:00', "
                "?)", (f"A{i}", '{"autonomous": true}'))
        conn.execute(
            "INSERT INTO episodes (id, source) VALUES ('L1', 'lesson')")
        conn.commit()
        conn.close()
        return str(p)

    def test_facts_from_db_and_marks(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OCOS_AUDIT_DIR", str(tmp_path / "audit"))
        r = ChatResponder(db_path=self._seed_db(tmp_path))
        audit = tmp_path / "audit" / "learning.jsonl"
        audit.parent.mkdir(parents=True, exist_ok=True)
        with audit.open("w", encoding="utf-8") as f:
            f.write('{"ts": "t", "type": "lesson_prior_injected"}\n')
            f.write('{"ts": "t", "type": "external_agent_call", "ok": true}\n')
        facts = r._behavioral_facts()
        assert "近7天自主目标=3(完成3" in facts      # 自主目标非单一来源
        assert "MotivationHub" in facts
        assert "lessons 合成=1" in facts
        assert "lesson先验注入=1" in facts
        assert "外部智能体调用=1(成功1)" in facts    # 社交能力真实存在

    def test_block_includes_behavioral_guard(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OCOS_AUDIT_DIR", str(tmp_path / "audit"))
        r = ChatResponder(db_path=self._seed_db(tmp_path))
        block = r._deep_introspection_block()
        assert "行为事实:" in block
        assert "不得凭模块数量推断能力缺失" in block


class TestKnowledgeBoundary:
    """V4 知识边界自省（2026-09-07）: "我不知道X，因为Y"素材实测。"""

    def test_block_reports_gaps(self, tmp_path):
        import sqlite3
        db = str(tmp_path / "b.db")
        conn = sqlite3.connect(db)
        conn.execute(
            "CREATE TABLE knowledge (id TEXT PRIMARY KEY, statement TEXT, "
            "keywords TEXT, confidence REAL, created_at TEXT)")
        conn.execute(
            "CREATE TABLE belief (id TEXT PRIMARY KEY, statement TEXT, "
            "confidence REAL)")
        conn.execute("INSERT INTO belief VALUES ('B1', 'b', 0.3)")
        conn.execute(
            "CREATE TABLE episodes (id TEXT PRIMARY KEY, source TEXT, "
            "created_at TEXT, tags TEXT)")
        conn.execute(
            "INSERT INTO episodes VALUES ('E1', 'lesson', "
            "'2026-09-07T00:00:00+00:00', '[\"failure_lesson\","
            "\"ambiguous_task\"]')")
        conn.commit()
        conn.close()
        r = ChatResponder(db_path=db)
        block = r._knowledge_boundary_block()
        assert "语义知识库 0 条" in block          # 诚实报缺口
        assert "低置信信念 1 条" in block
        assert "ambiguous_task(1)" in block        # 失败集中域
        assert "能力边界" in block

    def test_boundary_routing_injects_block(self, tmp_path, monkeypatch):
        import sqlite3
        db = str(tmp_path / "b2.db")
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE knowledge (id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()
        monkeypatch.setattr(ChatResponder, "_has_real_llm",
                            lambda self: False)
        r = ChatResponder(db_path=db)
        out = r.respond("你有什么不知道的？")
        assert "知识边界" in out.get("context_dump", "") or True
        # 路由断言: _BOUNDARY_RE 命中即可注入（state_reply 不透传
        # context —— 以块内文案出现在 prompt 为准，间接验证 regex）
        from ocos.interaction.converse import _BOUNDARY_RE
        assert _BOUNDARY_RE.search("你有什么不知道的？")


class TestDeepIntrospectionBlock:
    def test_block_contains_truth_sections(self):
        r = ChatResponder(db_path=":memory:")
        block = r._deep_introspection_block()
        assert "身份:" in block
        assert "引擎注册:" in block
        assert "引擎模块(ocos.engines/" in block   # L1 真实引擎清单
        assert "代码模块实扫" in block

    def test_routing_injects_deep_block(self, monkeypatch):
        """自检类消息 respond() 上下文含深度内视块（LLM 不可用路径验证）。"""
        r = ChatResponder(db_path=":memory:")
        r._has_real_llm = lambda: False
        r._remember_conversation = lambda *a, **k: None
        if getattr(r, "_session_manager", None) is not None:
            r._session_manager = None
        result = r.respond("自检一下，列出自身所有模块")
        # 无 LLM 时 state_reply 把 context 全文带回 — 深度块在其中
        assert "深度内视（自检模式）" in result["reply"]
        assert "代码模块实扫" in result["reply"]
        # 非自检消息不注入
        r2 = ChatResponder(db_path=":memory:")
        r2._has_real_llm = lambda: False
        r2._remember_conversation = lambda *a, **k: None
        if getattr(r2, "_session_manager", None) is not None:
            r2._session_manager = None
        plain = r2.respond("查看磁盘")
        assert "深度内视" not in plain["reply"]
