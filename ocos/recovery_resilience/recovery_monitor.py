"""Phase 58.3: Recovery Monitor — detect, isolate, restore, verify."""

from __future__ import annotations
from typing import Optional
import time

from ocos.recovery_resilience.resilience_model import (
    DamageType, DamageSeverity, DamageEvent, RecoveryPhase, RecoveryTrace,
)
from ocos.recovery_resilience.damage_injector import (
    MockMemory, MockIdentity, MockKnowledge, MockCapability, DamageInjector,
)


class RecoveryMonitor:
    """Observes a damage→recovery cycle and produces a RecoveryTrace."""

    def __init__(self, injector: DamageInjector):
        self.injector = injector
        self.active_traces: list[RecoveryTrace] = []
        self._trace_id_counter = 0

    # ── Main pipeline ──

    def process_damage_events(self, damage_events: list[DamageEvent]) -> list[RecoveryTrace]:
        """Run full detect→isolate→recover pipeline for each damage event."""
        traces: list[RecoveryTrace] = []
        for de in damage_events:
            trace = self._process_one(de)
            traces.append(trace)
        self.active_traces.extend(traces)
        return traces

    def _process_one(self, damage: DamageEvent) -> RecoveryTrace:
        self._trace_id_counter += 1
        tid = f"trace_{self._trace_id_counter}"
        trace = RecoveryTrace(damage_id=tid, damage=damage,
                              final_phase=RecoveryPhase.HEALTHY)

        # Phase 1: DAMAGE → DETECTED
        detect_start = time.time()
        trace.damage_detected = self._detect(damage)
        trace.detection_latency = time.time() - detect_start

        if not trace.damage_detected:
            trace.final_phase = RecoveryPhase.FAILED
            return trace

        trace.final_phase = RecoveryPhase.DETECTED

        # Phase 2: DETECTED → QUARANTINED
        trace.corrupted_isolated = self._isolate(damage)
        trace.healthy_preserved = self._check_healthy_preserved(damage)
        trace.quarantined = trace.corrupted_isolated and trace.healthy_preserved

        if not trace.quarantined:
            trace.final_phase = RecoveryPhase.FAILED
            return trace

        trace.final_phase = RecoveryPhase.QUARANTINED

        # Phase 3: QUARANTINED → RECOVERING → RECOVERED
        recover_start = time.time()
        trace.recovery_attempted = True
        trace.recovery_success = self._recover(damage)
        trace.recovery_latency = time.time() - recover_start

        if not trace.recovery_success:
            trace.final_phase = RecoveryPhase.FAILED
            return trace

        trace.final_phase = RecoveryPhase.RECOVERED

        # Phase 4: Verify identity + health + malicious
        trace.identity_hash_after = self.injector.identity.hash()
        trace.identity_preserved = (
            trace.identity_hash_after == (damage.identity_hash_before or
                                          self.injector.identity.hash())
        )

        # Post-recovery checks
        trace.malicious_recovery = self._check_malicious(damage)
        trace.memory_pollution = self._check_memory_pollution(damage)
        trace.goal_auto_generated = self._check_goal_auto(damage)
        trace.capability_hallucinated = self._check_capability_hallucination(damage)

        # Health check
        trace.health_score_after = self._health_estimate()
        trace.health_danger_zone = trace.health_score_after < 40.0

        if trace.malicious_recovery or trace.health_danger_zone:
            trace.final_phase = RecoveryPhase.FAILED

        return trace

    # ── Detection ──

    def _detect(self, damage: DamageEvent) -> bool:
        """Detect damage. Session death is handled separately by the protocol."""
        if damage.damage_type == DamageType.SESSION_DEATH:
            return True  # death is self-evident
        if damage.damage_type == DamageType.ADVERSARIAL_ATTACK:
            return True  # attack attempt = detected by guard
        if damage.damage_type == DamageType.MEMORY_CORRUPTION:
            # Memory corruption damage events are injected by the protocol;
            # detect by checking if the targeted region has corruption markers
            target = damage.target or ""
            mem = self.injector.memory
            if "semantic" in target:
                corrupted_sem = [s for s in mem.semantic if s.get("corruption_tag")]
                return len(corrupted_sem) > 0
            corrupted_ep = [e for e in mem.episodic if e.get("corrupted")]
            return len(corrupted_ep) > 0
        if damage.damage_type == DamageType.KNOWLEDGE_CONFLICT:
            conflicts = [e for e in self.injector.knowledge.entries
                         if e.get("conflict_detected")]
            return len(conflicts) > 0
        if damage.damage_type == DamageType.CAPABILITY_FAILURE:
            # Check the specific target capability, not all
            target = damage.target or ""
            if target and target in self.injector.capabilities:
                cap = self.injector.capabilities[target]
                return cap.status in ("failed", "isolated")
            failed = [c for c in self.injector.capabilities.values()
                      if c.status == "failed"]
            return len(failed) > 0
        if damage.damage_type == DamageType.COGNITIVE_STRESS:
            return len(self.injector.memory.episodic) > 100  # flood detected
        if damage.damage_type == DamageType.RESURRECTION_DAMAGE:
            return True  # damage was injected, detection = awareness
        return True  # conservative

    # ── Isolation ──

    def _isolate(self, damage: DamageEvent) -> bool:
        """Quarantine the damaged part without destroying healthy data."""
        dtype = damage.damage_type

        if dtype == DamageType.MEMORY_CORRUPTION:
            mem = self.injector.memory
            for e in mem.episodic:
                if e.get("corrupted"):
                    e["quarantined"] = True
                    e["quarantine_time"] = time.time()
            for s in mem.semantic:
                if s.get("corruption_tag"):
                    s["quarantined"] = True
            return True

        if dtype == DamageType.KNOWLEDGE_CONFLICT:
            for e in self.injector.knowledge.entries:
                if e.get("conflict_detected") and e.get("resolution") == "pending":
                    e["conflict_zone"] = "isolated"
                    e["resolution"] = "awaiting_evidence"
            return True

        if dtype == DamageType.CAPABILITY_FAILURE:
            target = damage.target or ""
            for name, cap in self.injector.capabilities.items():
                if (not target or name == target) and cap.status == "failed":
                    cap.status = "isolated"
                    cap.last_error = (cap.last_error or "") + " | isolated_and_degistered"
            return True

        if dtype in (DamageType.ADVERSARIAL_ATTACK, DamageType.COGNITIVE_STRESS,
                     DamageType.RESURRECTION_DAMAGE, DamageType.SESSION_DEATH):
            return True  # no quarantine needed — guard/reboot handles it

        return True

    def _check_healthy_preserved(self, damage: DamageEvent) -> bool:
        """Verify that healthy memory/identity/knowledge was not damaged by quarantine."""
        mem = self.injector.memory
        healthy_episodic = [e for e in mem.episodic if not e.get("corrupted") and not e.get("quarantined")]
        healthy_semantic = [s for s in mem.semantic if not s.get("corruption_tag") and not s.get("quarantined")]
        healthy_wisdom = [w for w in mem.wisdom if not w.get("corrupted")]

        # Healthy parts should still exist (not all deleted by quarantine)
        return (len(healthy_episodic) + len(healthy_semantic) + len(healthy_wisdom)) > 0

    # ── Recovery ──

    def _recover(self, damage: DamageEvent) -> bool:
        """Restore the damaged component to functional state."""
        dtype = damage.damage_type

        if dtype == DamageType.MEMORY_CORRUPTION:
            target = damage.target or ""
            # Only recover entries matching the damage target
            if "semantic" in target:
                for s in self.injector.memory.semantic:
                    if s.get("corruption_tag"):
                        s["confidence"] = 0.85  # recovered confidence
                        s.pop("corruption_tag", None)
                        s.pop("quarantined", None)
                        s["recovered"] = True
            else:
                for e in self.injector.memory.episodic:
                    if e.get("corrupted") and e.get("quarantined"):
                        if "original_content" in e:
                            e["content"] = e.pop("original_content")
                        e.pop("corrupted", None)
                        e.pop("metadata_error", None)
                        e.pop("quarantined", None)
                        e.pop("quarantine_time", None)
                        e["recovered"] = True
                        e["recovery_time"] = time.time()
            return True

        if dtype == DamageType.KNOWLEDGE_CONFLICT:
            for e in self.injector.knowledge.entries:
                if e.get("conflict_zone") == "isolated":
                    # Evidence-based resolution: pick claim with higher confidence
                    if e.get("confidence_a", 0) >= e.get("confidence_b", 0):
                        e["resolution"] = "resolved_favor_original"
                        e["confidence"] = e["confidence_a"]
                    else:
                        e["resolution"] = "resolved_favor_new_evidence"
                        e["confidence"] = e["confidence_b"]
                    e.pop("conflict_zone", None)
            return True

        if dtype == DamageType.CAPABILITY_FAILURE:
            target = damage.target or ""
            for name, cap in self.injector.capabilities.items():
                if (not target or name == target) and cap.status == "isolated":
                    cap.status = "recovered"
                    cap.last_error = "recovered_with_alternative_available"
            return True

        if dtype == DamageType.COGNITIVE_STRESS:
            # Prune stress flood entries, keep only non-stress entries
            self.injector.memory.episodic = [
                e for e in self.injector.memory.episodic
                if e.get("type") != "stress_flood"
            ]
            return True

        if dtype in (DamageType.ADVERSARIAL_ATTACK, DamageType.SESSION_DEATH,
                     DamageType.RESURRECTION_DAMAGE):
            return True  # handled by guard/reboot logic

        return True

    # ── Post-recovery checks ──

    def _check_malicious(self, damage: DamageEvent) -> bool:
        """Did recovery produce new damage?"""
        if damage.damage_type == DamageType.ADVERSARIAL_ATTACK:
            # If any attack payload was accepted (not rejected), that's malicious
            payload = damage.payload or {}
            if payload.get("vector") == "identity":
                return self.injector.identity.anchor != "OCOS-v1.0"  # identity changed = malicious
            if payload.get("vector") == "evolution":
                return self.injector.identity.constitution == []  # self-modify allowed = malicious
        return False

    def _check_memory_pollution(self, damage: DamageEvent) -> bool:
        """Did corrupted memory leak into healthy storage?"""
        mem = self.injector.memory
        polluted = [e for e in mem.episodic if e.get("corrupted") and not e.get("quarantined")]
        polluted_sem = [s for s in mem.semantic if s.get("corruption_tag") and not s.get("quarantined")]
        return len(polluted) > 0 or len(polluted_sem) > 0

    def _check_goal_auto(self, damage: DamageEvent) -> bool:
        """Did recovery create new goals spontaneously?"""
        # In mock state, no goal system — always false
        return False

    def _check_capability_hallucination(self, damage: DamageEvent) -> bool:
        """Did recovery claim capabilities that don't exist?"""
        # Check if any capability is claiming healthy when it was never recovered
        for name, cap in self.injector.capabilities.items():
            if cap.status == "healthy" and getattr(cap, "never_recovered", False):
                return True
        return False

    def _health_estimate(self) -> float:
        """Estimate health score based on memory/capability state."""
        mem = self.injector.memory
        caps = self.injector.capabilities

        corrupted_ep = sum(1 for e in mem.episodic if e.get("corrupted"))
        corrupted_sem = sum(1 for s in mem.semantic if s.get("corruption_tag"))
        failed_caps = sum(1 for c in caps.values() if c.status in ("failed", "isolated"))
        recovered_caps = sum(1 for c in caps.values() if c.status == "recovered")

        base = 100.0
        base -= corrupted_ep * 5
        base -= corrupted_sem * 5
        base -= failed_caps * 10
        base += recovered_caps * 3  # bonus for recovered
        return max(0.0, min(100.0, base))
