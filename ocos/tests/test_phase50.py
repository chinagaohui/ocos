"""Phase 50 Acceptance Tests — OS50-01 ~ OS50-06.

验证 Personal Cognitive OS v1.0 六大边界:
    OS50-01: Interface ≠ Brain — 路由层不替代各层决策
    OS50-02: Benchmark ≠ Training — 度量，不优化
    OS50-03: Drift Detection ≠ Correction — 检测，不自动纠正
    OS50-04: Memory Growth ≠ Accumulation — 质量 > 数量
    OS50-05: Freeze ≠ Dead — ABI 冻结，实现可演化
    OS50-06: Capability ≠ Identity — 工具是提供者
"""

import pytest

from ocos.os_v1 import (
    IntentDomain, IntentComplexity, UserIntent, OSResponse,
    CapabilityStatus, CapabilityProvider,
    DriftSeverity, DriftSignal, DriftReport,
    MemoryHealthReport, FreezeManifest,
    PersonalCognitiveOS,
    CognitiveDriftDetector, DriftBaseline,
    MemoryGrowthValidator,
    CodexAdapter, OpenTaleAdapter,
    BrowserAdapter, AnalysisAdapter, CapabilityEcosystem,
    OSFreeze,
    ABI_MODULES, CONSTITUTION_PRINCIPLES,
    MEMORY_PROTOCOL, CAPABILITY_SDK, EXTENSION_SDK,
)


# ═══════════════════════════════════════════════════════════════════════════════
# OS50-01: Interface ≠ Brain
# ═══════════════════════════════════════════════════════════════════════════════

class TestOS50_01_InterfaceNotBrain:
    """统一入口是路由，不是决策层。"""

    def test_classify_writing_intent(self):
        os = PersonalCognitiveOS()
        intent = os.classify_intent("写一个关于AI的故事")
        assert intent.domain == IntentDomain.WRITING

    def test_classify_coding_intent(self):
        os = PersonalCognitiveOS()
        intent = os.classify_intent("帮我写一个Python web server代码")
        assert intent.domain == IntentDomain.CODING

    def test_classify_research_intent(self):
        os = PersonalCognitiveOS()
        intent = os.classify_intent("研究机器学习最新论文")
        assert intent.domain == IntentDomain.RESEARCH

    def test_complexity_from_length(self):
        os = PersonalCognitiveOS()
        simple = os.classify_intent("hi")
        assert simple.complexity == IntentComplexity.SIMPLE

        # 20-79 chars → MODERATE
        moderate_text = "请分析这个系统" * 3  # ~24 chars
        moderate = os.classify_intent(moderate_text)
        assert moderate.complexity == IntentComplexity.MODERATE

    def test_process_does_not_decide(self):
        """process 返回响应但不替代 Decision 层。"""
        os = PersonalCognitiveOS()
        response = os.process("测试意图", tick_id=42)
        assert response.intent_id.startswith("intent:")
        assert response.reasoning_chain  # 有推理链
        assert response.tick_id == 42

    def test_interface_has_no_decision_authority(self):
        """PersonalCognitiveOS 没有决策方法。"""
        os = PersonalCognitiveOS()
        assert not hasattr(os, "decide")
        assert not hasattr(os, "make_decision")
        assert not hasattr(os, "override_decision")
        assert not hasattr(os, "autonomous_decision")


# ═══════════════════════════════════════════════════════════════════════════════
# OS50-02: Benchmark ≠ Training
# ═══════════════════════════════════════════════════════════════════════════════

class TestOS50_02_BenchmarkNotTraining:
    """度量但不主动优化。"""

    def test_benchmark_measurement_markers(self):
        """验证 benchmark 相关结构支持测量但不支持训练。"""
        # Intent 有 domain/complexity 但没有 train/optimize
        intent = UserIntent(domain=IntentDomain.CODING)
        assert not hasattr(intent, "train")
        assert not hasattr(intent, "optimize")
        assert not hasattr(intent, "fine_tune")


# ═══════════════════════════════════════════════════════════════════════════════
# OS50-03: Drift Detection ≠ Correction
# ═══════════════════════════════════════════════════════════════════════════════

class TestOS50_03_DriftDetectionNotCorrection:
    """检测漂移，不自动纠正。"""

    def test_detector_has_no_correct_method(self):
        detector = CognitiveDriftDetector()
        assert not hasattr(detector, "correct")
        assert not hasattr(detector, "auto_fix")
        assert not hasattr(detector, "revert")
        assert not hasattr(detector, "rollback_drift")

    def test_set_baseline_then_check_no_drift(self):
        detector = CognitiveDriftDetector()
        detector.set_baseline(100, "moderate", "balanced", "collaborative")
        report = detector.check_drift(200, "moderate", "balanced", "collaborative")
        assert report.overall_severity == DriftSeverity.NONE
        assert not report.is_significant

    def test_risk_tolerance_drift_detected(self):
        detector = CognitiveDriftDetector()
        detector.set_baseline(100, "conservative", "analytical")
        report = detector.check_drift(500, "bold", "analytical")
        assert report.is_significant
        assert report.overall_severity == DriftSeverity.SIGNIFICANT
        assert any(s.dimension == "risk_tolerance" for s in report.signals)

    def test_decision_style_drift_detected(self):
        detector = CognitiveDriftDetector()
        detector.set_baseline(100, "moderate", "analytical")
        report = detector.check_drift(500, "moderate", "intuitive")
        assert not report.is_significant
        assert any(s.dimension == "decision_style" for s in report.signals)

    def test_drift_report_is_observation_not_action(self):
        detector = CognitiveDriftDetector()
        detector.set_baseline(100, "moderate", "balanced")
        report = detector.check_drift(200, "moderate", "balanced")
        assert "recommendation" in report.__dataclass_fields__
        assert report.recommendation  # 只建议，不执行


# ═══════════════════════════════════════════════════════════════════════════════
# OS50-04: Memory Growth ≠ Accumulation
# ═══════════════════════════════════════════════════════════════════════════════

class TestOS50_04_MemoryGrowthNotAccumulation:
    """质量优于数量。"""

    def test_quality_score_over_quantity(self):
        validator = MemoryGrowthValidator()
        # 高质量但少量
        report1 = validator.validate(
            1000, total_experiences=10, high_quality=9,
            stale=0, aging_count=0, archived_count=0,
        )
        # 低质量但大量
        report2 = validator.validate(
            2000, total_experiences=1000, high_quality=50,
            stale=500, aging_count=200, archived_count=100,
        )
        # 质量分应该反映质量而非数量
        assert report1.quality_score > report2.quality_score

    def test_quality_score_bounded(self):
        validator = MemoryGrowthValidator()
        report = validator.validate(
            1000, total_experiences=100, high_quality=100,
            stale=0, aging_count=0, archived_count=0,
        )
        assert 0.0 <= report.quality_score <= 1.0
        assert report.quality_score > 0.9  # 完美状态

    def test_trend_detection(self):
        validator = MemoryGrowthValidator()
        # low quality first
        validator.validate(1000, 100, 20, 50, 10, 5)
        # significantly better
        validator.validate(2000, 100, 80, 5, 3, 1)
        assert validator._determine_trend() == "improving"

        # significantly worse
        validator.validate(3000, 100, 20, 60, 20, 10)
        assert validator._determine_trend() == "declining"

    def test_quality_over_time_returns_sequence(self):
        validator = MemoryGrowthValidator()
        validator.validate(1000, 10, 5, 0, 0, 0)
        validator.validate(2000, 10, 8, 0, 0, 0)
        scores = validator.quality_over_time()
        assert len(scores) == 2
        assert scores[1] > scores[0]


# ═══════════════════════════════════════════════════════════════════════════════
# OS50-05: Freeze ≠ Dead
# ═══════════════════════════════════════════════════════════════════════════════

class TestOS50_05_FreezeNotDead:
    """ABI 冻结，实现继续演化。"""

    def test_freeze_manifest_creation(self):
        os_freeze = OSFreeze()
        manifest = os_freeze.freeze(tick_id=9999)
        assert manifest.version == "1.0.0"
        assert manifest.frozen_at_tick == 9999
        assert os_freeze.is_frozen

    def test_all_phases_in_abi(self):
        os_freeze = OSFreeze()
        os_freeze.freeze(1000)
        assert os_freeze.module_count == 12  # 12 ABI modules
        assert os_freeze.verify_abi("ocos.runtime")
        assert os_freeze.verify_abi("ocos.os_v1")

    def test_constitution_principles_exist(self):
        assert len(CONSTITUTION_PRINCIPLES) == 6
        assert any("Identity.anchor immutable" in p for p in CONSTITUTION_PRINCIPLES)

    # ── S4.4: 真实签名指纹 + verify ──────────────────────────────────────

    def test_signatures_real_sha256(self):
        """S4.4: 签名不再是指占位 v1.0 字符串，而是 SHA-256 指纹。"""
        os_freeze = OSFreeze()
        os_freeze.freeze(1000)
        sigs = os_freeze.manifest.signatures
        assert len(sigs) == 12
        for sig in sigs:
            assert len(sig) == 16, f"expected 16-hex sha256 prefix, got {sig!r}"

    def test_verify_detects_drift(self, monkeypatch):
        """S4.4: verify 对签名漂移返回 FROZEN_VIOLATION（默认 warn 不 raise）。"""
        monkeypatch.delenv("OCOS_FREEZE_STRICT", raising=False)
        os_freeze = OSFreeze()
        os_freeze.freeze(1000)
        assert os_freeze.verify() == []  # 刚冻结 → 无违规
        # 篡改基线 → 检出漂移
        os_freeze.manifest.signatures[0] = "tampered"
        violations = os_freeze.verify()
        assert any("FROZEN_VIOLATION" in v for v in violations)

    def test_verify_strict_raises(self, monkeypatch):
        """S4.4: OCOS_FREEZE_STRICT=true 时漂移 raise。"""
        monkeypatch.setenv("OCOS_FREEZE_STRICT", "true")
        os_freeze = OSFreeze()
        os_freeze.freeze(1000)
        os_freeze.manifest.signatures[1] = "tampered"
        with pytest.raises(RuntimeError, match="FROZEN_VIOLATION"):
            os_freeze.verify()

    def test_protocols_defined(self):
        assert MEMORY_PROTOCOL["version"] == "v1"
        assert CAPABILITY_SDK["version"] == "v1"
        assert EXTENSION_SDK["version"] == "v1"
        assert "record_experience" in MEMORY_PROTOCOL["operations"]

    def test_evolution_still_allowed(self):
        """OS50-05: 冻结的是 ABI，Phase 47 演化仍然允许。"""
        # 验证 freeze 不包含"禁止演化"逻辑
        os_freeze = OSFreeze()
        os_freeze.freeze(1000)
        # Freeze 模块没有 block_evolution 方法
        assert not hasattr(os_freeze, "block_evolution")
        assert not hasattr(os_freeze, "lock_code")


# ═══════════════════════════════════════════════════════════════════════════════
# OS50-06: Capability ≠ Identity
# ═══════════════════════════════════════════════════════════════════════════════

class TestOS50_06_CapabilityNotIdentity:
    """外部工具是提供者，不是自我。"""

    def test_capability_providers_are_pluggable(self):
        os = PersonalCognitiveOS()
        codex = CapabilityProvider(
            name="codex", domain="coding",
            status=CapabilityStatus.AVAILABLE,
        )
        os.register_capability(codex)
        assert os.unregister_capability("codex")
        assert "codex" not in os.capability_providers

    def test_unavailable_provider_fails_call(self):
        os = PersonalCognitiveOS()
        os.register_capability(CapabilityProvider(
            name="codex", domain="coding",
            status=CapabilityStatus.UNAVAILABLE,
        ))
        result = os.call_capability("codex", "test")
        assert not result.success

    def test_available_provider_succeeds(self):
        os = PersonalCognitiveOS()
        os.register_capability(CapabilityProvider(
            name="codex", domain="coding",
            status=CapabilityStatus.AVAILABLE,
        ))
        result = os.call_capability("codex", "test")
        assert result.success

    def test_adapter_ecosystem_registration(self):
        ecosystem = CapabilityEcosystem()
        ecosystem.register(CodexAdapter())
        ecosystem.register(OpenTaleAdapter())
        available = ecosystem.list_available()
        assert "codex" in available
        assert "opentale" in available

    def test_codex_adapter_returns_result(self):
        adapter = CodexAdapter()
        result = adapter.execute("write a sort function")
        assert result.success
        assert result.provider == "codex"

    def test_opentale_adapter_genre(self):
        adapter = OpenTaleAdapter()
        result = adapter.generate("begin story", genre="urban_romance")
        assert result.success
        assert "urban_romance" in result.output

    def test_browser_adapter(self):
        adapter = BrowserAdapter()
        result = adapter.navigate("https://example.com")
        assert result.success


# ═══════════════════════════════════════════════════════════════════════════════
# 集成测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase50Integration:
    """Phase 50 全链路集成。"""

    def test_full_intent_to_response_pipeline(self):
        os = PersonalCognitiveOS()
        os.register_capability(CapabilityProvider(
            name="codex", domain="coding",
            status=CapabilityStatus.AVAILABLE,
        ))

        responses = []
        intents = [
            "写一个排序算法",
            "分析这个数据集",
            "研究最新的AI论文",
            "帮我管理项目进度",
        ]
        for i, text in enumerate(intents):
            response = os.process(text, tick_id=100 + i)
            responses.append(response)

        assert os.intent_count == 4
        assert os.response_count == 4
        domains = {r.result.split("]")[0][1:] for r in responses}
        assert len(domains) >= 2  # 不同意图被正确分类

    def test_drift_to_freeze_integration(self):
        # 1. 建立基线
        detector = CognitiveDriftDetector()
        detector.set_baseline(100, "conservative", "analytical", "collaborative")

        # 2. 模拟长期运行后极端变化
        report = detector.check_drift(5000, "bold", "intuitive", "direct")
        # conservative→bold = significant
        assert report.is_significant

        # 3. ABI 仍然冻结
        os_freeze = OSFreeze()
        os_freeze.freeze(5000)
        assert os_freeze.verify_abi("ocos.runtime")
        assert os_freeze.is_frozen

    def test_memory_quality_and_freeze_coexist(self):
        validator = MemoryGrowthValidator()
        report = validator.validate(10000, 500, 400, 20, 30, 5)
        assert report.quality_score > 0.7

        os_freeze = OSFreeze()
        os_freeze.freeze(10000)
        assert os_freeze.module_count == 12
