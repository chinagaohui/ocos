# Control Plane Ownership Matrix (Phase15)

**Frozen**: 2026-07-23
**Audit Gate**: Phase15 Freeze Audit
**Update Rule**: Any modification requires triple-approval: Positioning Review + Contract Change + Freeze Audit.

## §0 — OCOS Four-Layer Architecture

```
┌──────────────────────────────────────────┐
│  Control Plane (Phase15)                 │  ← 决策与编排
│  Director · Quality Gate · Orchestrator  │
│  Meta Control · Signal Registry          │
├──────────────────────────────────────────┤
│  Capability Plane (Phase14.5)            │  ← 能力执行
│  Writer · Character · World Builder      │
├──────────────────────────────────────────┤
│  Knowledge Plane (Phase14)            │  ← 知道什么
│  Pattern Discovery · Principle Registry  │
├──────────────────────────────────────────┤
│  Observation Plane (Phase13)             │  ← 观察与感知
│  Reality · Evidence · Relation           │
└──────────────────────────────────────────┘
```

## §1 — Module Responsibility Matrix

| Module | Phase | **Only Responsible For** | **Never Does** |
|---|---|---|---|
| **Principle Registry** | 14.4 | Store / retrieve principle records | Inference, recommendation, generation |
| **Mapping (Principle→Signal)** | 15.2.2 | Transform principle constraints into Control Signals | Recommend, rank, evaluate signals |
| **Signal Validation** | 15.2.3 | Validate Control Signal structure & purity | Modify signals, add/remove fields |
| **Signal Registry** | 15.2.0 | Persist/find historical signals | Analyze, recommend, generate |
| **Adapter Contract** | 15.2.4 | Map ControlSignal→AdaptedConstraint for runtime | Modify runtime state, write to Registry |
| **Director** | 15.3 | Arbitrate signals, allocate budget, produce ExecutionPlan | Generate text, call models, modify Registry, produce knowledge |
| **Quality Gate** | 15.4 | Verify ExecutionPlan compliance against Contracts | Evaluate quality, score story, repair violations |
| **Runtime Orchestrator** | 15.5 | Map ExecutionPlan→Runtime consumable objects | Make decisions, plan narrative, direct story |
| **Meta Control** | 15.6 | Cross-signal conflict resolution, budget rebalancing, global policy | Generate content, write prompts, evaluate output |
| **Writer** | 14.5 | Execute control signals to produce narrative text | Direct story, evaluate quality, modify Contracts |

## §2 — Data Flow Ownership

```
Cognitive Plane (Pattern + Principle)
       │
       ▼
Mapping Layer (Principle→ControlSignal)
       │
       ▼
  ╔══════════════════════════════════════╗
  ║        Control Plane                 ║
  ║                                      ║
  ║  Signal Validation ──► Director      ║
  ║       │                   │           ║
  ║       │                   ▼           ║
  ║       │            ExecutionPlan      ║
  ║       │                   │           ║
  ║       │              Quality Gate     ║
  ║       │              (PASS? ──► FAIL) ║
  ║       │                   │           ║
  ║       │                   ▼           ║
  ║       │          Runtime Orchestrator ║
  ║       ▼                   │           ║
  ║  Signal Registry          ▼           ║
  ║                    AdaptedConstraint  ║
  ╚══════════════════════════════════════╝
                │
                ▼
         OpenTale Runtime
```

## §3 — Boundary Rules (Frozen)

### §3.1 — Control Plane → Capability Plane

- Control Plane produces **control signals and plans**, NOT text.
- Capability Plane (Writer) consumes signals to produce text.
- Control Plane **never calls** Writer directly — only through Orchestrator.

### §3.2 — Control Plane → Knowledge Plane

- Control Plane **reads** Pattern and Principle records.
- Control Plane **never writes** to Pattern or Principle Registry.
- Knowledge Plane produces **patterns and principles**, not commands.

### §3.3 — Quality Gate Boundaries

- Quality Gate is a **pure function** — same input → same output.
- Quality Gate **never** writes to Registry, Cache, or Runtime.
- Quality Gate **never** calls models.
- Quality Gate **never** generates, edits, or rewrites content.

### §3.4 — Director Boundaries

- Director **arbitrates and allocates**, NOT generates.
- Director **never** modifies Registry entries.
- Director **never** produces text, prompts, or instructions.

### §3.5 — Orchestrator Boundaries

- Orchestrator **maps** ExecutionPlan → Runtime consumable objects.
- Orchestrator is NOT a Workflow engine.
- Orchestrator is NOT a Planner.
- Orchestrator is NOT a Director.
- Orchestrator **never** makes narrative decisions.

### §3.6 — Meta Control Boundaries

- Meta Control manages **policy-level** conflicts, NOT per-plan arbitration.
- Meta Control **never** generates content.
- Meta Control **never** evaluates narrative quality.
- See [META_CONTROL_OWNERSHIP.md](./META_CONTROL_OWNERSHIP.md) for complete ownership contract.

## §4 — Verification Protocol

| Check | Scope | Frequency |
|---|---|---|
| Import boundary | No vertical leak across planes | Per Phase commit |
| Module isolation | No cross-plane calls outside ABI | Per Phase commit |
| Purity audit | No forbidden operations (text gen, model call, eval) | Per Freeze Audit |
| Determinism | Same input → same output for pure modules | Per Freeze Audit |
| Side-effect audit | No Registry/Cache/Model writes from pure modules | Per Freeze Audit |

## §5 — Changelog

| Date | Change | Approver |
|---|---|---|
| 2026-07-23 | Initial freeze — Phase15.0 through 15.3 | System freeze audit |
| 2026-07-23 | Added Quality Gate ownership (Phase15.4) | System freeze audit |
| 2026-07-23 | Added Runtime Certification (Phase15.5) | Hermes Agent Automated Audit |
| 2026-07-23 | Added Meta Control Ownership (Phase15.6) — 4 questions fully answered | Hermes Agent Freeze Audit |
