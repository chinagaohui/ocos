# OCOS Daily Self-Care Cycle — Implementation Plan v1.0

> **创建日期**: 2026-09-09
> **状态**: Phase 0 — 规划完成，未开始编码
> **动机**: OCOS 还不是真正的数字生命——它不会主动扫描自己的代码、不会主动修复自己的问题、不会主动根据大脑思考创造新能力。现有 HealthLoop/repair_link/watchdog 只覆盖了 runtime/DB 层，没有代码级自举。

---

## 1. 核心原则

| # | 原则 | 理由 |
|---|------|------|
| P1 | **薄编排，厚复用** | 不建平行系统。新模块只做调度 + 编排 + 一处真正新逻辑（CodeHealthScanner），其余全调现有模块 |
| P2 | **沙箱优先，失败回滚** | 任何自我修改先走 RepairSandbox/EvolutionSandbox，零直接写操作 |
| P3 | **systemd timer 驱动** | 不嵌 daemon tick（daemon 卡死就停了），走独立 timer 保证执行 |
| P4 | **每日一次，幂等** | 同一天重复跑 → 相同结果，不产生副作用 |
| P5 | **只读扫描先行** | Phase 1-2 只读不写，先把扫描跑通，再加执行逻辑 |

---

## 2. 现有基础设施（**不重建，直接调用**）

```
HealthLoop.run_check()              → 认知体检（记忆/决策/稳态）
repair_link.run_diagnosis_cycle()   → 故障检测 + 白名单修复提案
SelfEvolutionManager.propose()       → 演化提案 → ImpactAnalyzer → Sandbox → MigrationEngine
EvolutionSandbox.validate()         → 修复前隔离验证
EpistemicDrive.suggest_all()        → 探索/成长/修复三种好奇心目标
watchdog.py                          → systemd timer 模式 + DB 备份（复用 _run_daily_backup）
```

### 现有模块的不足（为什么还需要新模块）

| 模块 | 扫描范围 | 缺口 |
|------|---------|------|
| HealthLoop | runtime 状态（内存条数、goal 栈深、决策失败率） | ❌ 不扫代码 |
| repair_link | DB integrity、WAL checkpoint、索引重建 | ❌ 不扫代码 |
| watchdog | 进程存活、DB backup | ❌ 不扫代码 |
| SelfEvolutionManager | 演化提案/迁移/回滚 | ❌ 没有主动扫描触发，靠被动 goal |
| EpistemicDrive | 好奇心目标生成 | ❌ suggest_explore 只看 DB 记录，不看代码结构 |

**唯一真正需要新增的扫描逻辑：CodeHealthScanner（代码级扫描）**

---

## 3. 架构图

```
 systemd timer (ocos-daily-selfcare.timer, 每日 03:00)
        │
        ▼
 ┌──────────────────────────────────────────────────────────┐
 │            daily_self_care.py（薄编排器，~200 行）         │
 │                                                          │
 │  ┌─ Phase 0: 环境快照 ─────────────────────────────────┐ │
 │  │  CodeHealthScanner.S5 (pip list + python -V)       │ │
 │  │  watchdog._run_daily_backup() (复用，不重写)        │ │
 │  └─────────────────────────────────────────────────────┘ │
 │                          │                               │
 │  ┌─ Phase 1: 深度扫描 ─────────────────────────────────┐ │
 │  │  CodeHealthScanner.S1-S4 (唯一新扫描逻辑，~300 行)  │ │
 │  │  HealthLoop.run_check() (认知体检，复用)            │ │
 │  │  repair_link.run_diagnosis_cycle() (DB 诊断，复用)   │ │
 │  └─────────────────────────────────────────────────────┘ │
 │                          │                               │
 │  ┌─ Phase 2: 问题分类 ─────────────────────────────────┐ │
 │  │  classify_findings() → 4 桶：                       │ │
 │  │    桶 A: 紧急修复（ImportError / DB corruption）    │ │
 │  │    桶 B: 优化机会（死代码 / 可简化逻辑）            │ │
 │  │    桶 C: 能力缺口（从未触及的模块 → 好奇心目标）    │ │
 │  │    桶 D: 环境漂移（pip list 与上次不同）            │ │
 │  └─────────────────────────────────────────────────────┘ │
 │                          │                               │
 │  ┌─ Phase 3: 执行（沙箱隔离） ─────────────────────────┐ │
 │  │  桶 A → repair_link 白名单流程（已有的）            │ │
 │  │  桶 B → EvolutionSandbox.validate() → MigrationEngine│ │
 │  │  桶 C → EpistemicDrive.suggest_explore() → 建 goal  │ │
 │  │  桶 D → 仅记录，不自动改环境（危险！）              │ │
 │  └─────────────────────────────────────────────────────┘ │
 │                          │                               │
 │  ┌─ Phase 4: 报告 + 记账 ──────────────────────────────┐ │
 │  │  扫描报告 → ~/.ocos/reports/daily_{date}.json       │ │
 │  │  写入 episodes (action='daily_self_care.run')       │ │
 │  │  触发 vitals_report（已有的）                       │ │
 │  └─────────────────────────────────────────────────────┘ │
 └──────────────────────────────────────────────────────────┘
        │
        ▼
   ocos-daemon.service（触发自我关心 goal）
        │
        ▼
   ChatResponder → DecisionBridge → researcher.execute
   （执行"挑一个从未触及的模块探索它"类 goal）
```

---

## 4. CodeHealthScanner — 唯一新扫描逻辑

**文件**: `ocos/monitoring/code_scanner.py`（~300 行）

### S1: 导入健康检查
```
扫描目标: 所有 ocos.* 子模块
方法: importlib.import_module 逐个 import
输出: {
  "total": N,
  "ok": N,
  "import_errors": [{"module": "ocos.xxx", "error": "ImportError: ...", "trace": "..."}],
  "circular_deps": ["ocos.a → ocos.b → ocos.a"]  # 近似检测
}
```
**关键**: 必须在新进程里跑（避免当前进程已 import 过的模块屏蔽 ImportError）。用 subprocess 启动 `python3 -c "import ocos.xxx"`。

### S2: AST 死代码检测
```
扫描目标: ocos/ 下所有 .py 文件
方法: ast.parse + 静态分析
检测:
  - 未被引用的 top-level function/class（近似：grep 所有 .py 的 import/调用）
  - TODO/FIXME/HACK 注释标记（计数 + 位置）
  - 空函数体 / pass-only 的函数
输出: {
  "dead_functions": [{"file": "...", "name": "...", "line": L}],
  "todos": [{"file": "...", "line": L, "text": "..."}],
  "empty_bodies": [...]
}
```

### S3: 模块覆盖分析
```
扫描目标: ocos.* 所有模块 + DB episodes 表
方法: pkgutil.iter_modules → DB LIKE '%ocos.XXX%'
检测: 哪些模块从未被实践引用过（goal/decision/context 里提过）
输出: {
  "total_modules": N,
  "covered": N,
  "uncovered": ["ocos.digital_world", "ocos.evolution", ...],
  "coverage_rate": 0.73
}
```

### S4: 依赖图完整性
```
扫描目标: ocos/ 下所有 .py 的 import 语句
方法: 正则匹配 `^(from|import) ocos\.` → 构建有向图
检测: 循环依赖（DAG 拓扑排序失败）
输出: {
  "nodes": [...],
  "edges": [...],
  "has_cycles": true/false,
  "cycles": [["ocos.a", "ocos.b", "ocos.a"]]
}
```

### S5: 环境快照
```
扫描目标: pip list + python -V + 系统信息
方法: subprocess 调 pip list / uname
输出: {
  "python_version": "3.12.3",
  "platform": "Linux ...",
  "packages": [{"name": "...", "version": "..."}],
  "total_packages": N
}
```
**用途**: 每日对比 → 检测环境漂移（桶 D）

---

## 5. 文件变更清单

### Phase 1（只读扫描）

| 文件 | 变更 | 行数 | 说明 |
|------|------|------|------|
| `ocos/monitoring/code_scanner.py` | 🆕 | ~300 | CodeHealthScanner S1-S5 |
| `ocos/daemon/daily_self_care.py` | 🆕 | ~80 | 编排器骨架（只跑 Phase 0-1，出 JSON） |
| `ocos/cli/commands/daily_self_care.py` | 🆕 | ~30 | CLI 入口 `ocos daily-self-care scan` |
| `ocos/cli/commands/self.py` | ✏️ | +5 | 注册子命令 |

### Phase 2（完整扫描 + 报告）

| 文件 | 变更 | 行数 | 说明 |
|------|------|------|------|
| `ocos/daemon/daily_self_care.py` | ✏️ | +80 | 加 Phase 2-4（分类 + 报告 + 记账） |
| `ocos/daemon/watchdog.py` | ✏️ | +10 | 暴露 `_run_daily_backup()` 函数 |

### Phase 3（沙箱执行 + goal 创建）

| 文件 | 变更 | 行数 | 说明 |
|------|------|------|------|
| `ocos/daemon/daily_self_care.py` | ✏️ | +100 | 加 Phase 3（桶 A/B/C 执行） |

### Phase 4（systemd timer）

| 文件 | 变更 | 说明 |
|------|------|------|
| `~/.config/systemd/user/ocos-daily-selfcare.service` | 🆕 | Service 定义 |
| `~/.config/systemd/user/ocos-daily-selfcare.timer` | 🆕 | Timer 定义（每日 03:00） |
| `scripts/install_daily_selfcare.sh` | 🆕 | 一键安装脚本 |

---

## 6. 稳定性保障

| 风险 | 防线 |
|------|------|
| daemon 挂了 daily cycle 不跑 | systemd timer 是独立进程，不依赖 daemon |
| 扫描本身崩溃 | Phase 1 每个子扫描 try/except 独立隔离 |
| 修复操作搞坏系统 | 所有写操作先过 Sandbox → Validation → ImpactAnalyzer → 人工批准 |
| 修复引入回归 | Phase 3 后自动跑 `.venv/bin/python3 -m pytest -x -q`（2681 tests 基线）。回归 → 自动 rollback |
| 环境漂移（pip 包被改了） | 桶 D 只记录不自动改——环境变更是人类决策 |
| 每日重复执行产生副作用 | 编排器开头检查 `~/.ocos/reports/daily_{today}.json` 存在 → 跳过。幂等 |
| 扫描耗时太久阻塞 | Phase 0-1 加总超时 60s（超过截断，写报告说"部分扫描未完成"） |
| 自我修改自己的文件 | CodeHealthScanner 只读 .py；修复走 EvolutionSandbox 文件修改 → MigrationEngine 完整 diff |

---

## 7. systemd timer 配置

### `ocos-daily-selfcare.service`
```ini
[Unit]
Description=OCOS Daily Self-Care Cycle
After=network-online.target

[Service]
Type=oneshot
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/laogao/Documents/trae_projects/ocos/.venv/bin/python3 \
  -m ocos.cli daily-self-care run
WorkingDirectory=/home/laogao/Documents/trae_projects/ocos
```

### `ocos-daily-selfcare.timer`
```ini
[Unit]
Description=Run OCOS daily self-care every day at 03:00

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true
AccuracySec=1min

[Install]
WantedBy=timers.target
```

### 安装
```bash
cp ocos-daily-selfcare.* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable ocos-daily-selfcare.timer
systemctl --user start ocos-daily-selfcare.timer
systemctl --user list-timers ocos-daily-selfcare.timer
```

---

## 8. 执行流示例（完整走一遍）

```
03:00  systemd timer 触发
  ↓
03:00  daily_self_care.run()
  ↓
Phase 0: 环境快照
  → CodeHealthScanner.S5: pip list 47 packages, python 3.12.3
  → watchdog._run_daily_backup(): ocos.db → ocos_20260909.db (第 5 份)
  ↓
Phase 1: 深度扫描
  → S1 import 检查: 全部 ocos.* 模块 OK（零 ImportError）
  → S2 AST 死代码: 发现 12 个未引用函数（agent/_archive/ 里的）
  → S3 模块覆盖: 发现 ocos/digital_world/ 从未被 episodes 引用
  → S4 依赖图: 无循环依赖 ✅
  → HealthLoop.run_check(): 记忆膨胀正常, 认知稳态正常 ✅
  → repair_link.run_diagnosis_cycle(): DB integrity OK, 零修复需要 ✅
  ↓
Phase 2: 分类
  → 桶 A: 空（无紧急修复）
  → 桶 B: 1 项优化（12 个死代码函数）
  → 桶 C: 1 项能力缺口（digital_world 从未触及）
  → 桶 D: 空（pip 无变化）
  ↓
Phase 3: 执行
  → 桶 B: EvolutionSandbox.validate("删除 _archive/ 死代码")
     → SandboxReport: PASS（前后 diff 无行为变化）
     → MigrationEngine: 创建 snapshot → 删除 12 函数 → pytest 2681 passed ✅
     → 失败了会自动 rollback
  → 桶 C: EpistemicDrive.suggest_explore() → 
     自动建 goal "探索 ocos.digital_world 模块——它提供 API_ops/db_ops/search_ops，
     从未在实践中被触及，让我用 researcher 读它的代码，产出能力笔记"
  ↓
Phase 4: 报告
  → 写入 ~/.ocos/reports/daily_20260909.json
  → 写入 episodes action='daily_self_care.run'
  → vitals_report 汇总：1 优化已执行，1 探索 goal 已创建
```

---

## 9. 阶段交付计划

### Phase 1 — 只读扫描器（推荐从这里开始）
- **交付物**: CodeHealthScanner S1-S5 + CLI `ocos daily-self-care scan`
- **验证**: `.venv/bin/python3 -m ocos.cli daily-self-care scan` → 看输出 JSON
- **安全**: 只读，零副作用
- **预估**: 1-2 轮对话

### Phase 2 — 完整链路（扫描 → 报告）
- **交付物**: Phase 0-1-4 完整，不执行任何修复/修改
- **验证**: 跑 → 查 `~/.ocos/reports/daily_{today}.json` + DB episodes 表
- **安全**: 只读 + 记账
- **预估**: 1 轮对话

### Phase 3 — 沙箱执行（优化 + goal 创建）
- **交付物**: Phase 2-3-4 完整，桶 B/C 自动执行
- **验证**: 跑 → 查 EvolutionSandbox 产物 + goals 表新 goal
- **安全**: 沙箱隔离 + 回归测试 + rollback
- **预估**: 2-3 轮对话

### Phase 4 — systemd timer 定时自动运行
- **交付物**: timer + service 文件 + 安装脚本
- **验证**: `systemctl --user list-timers` → 等 timer 触发 → 查 journalctl
- **安全**: Persistent=true 补跑
- **预估**: 1 轮对话

---

## 10. 关键技术事实（新对话必读）

### 入口混淆（低级错误，必须记住）
| 方法 | 作用 | 建 goal |
|------|------|---------|
| `ChatResponder.respond(message, session_id)` | 只生成 LLM 回复 | ❌ |
| `ChatResponder.respond_auto(message, session_id)` | compile_goal → 建 goal → 调 respond | ✅ |

### DB schema
- episodes 表：对话历史在 `action='conversation_reply'` 行，context JSON 结构 `{"content": "...", "sender": "user/bot/system"}`
- goals 表：status=PENDING/ACTIVE/COMPLETED/FAILED，metadata 存 domain/original/session_id
- DB path: `~/.ocos/ocos.db`

### Daemon 配置
- Service: `~/.config/systemd/user/ocos-daemon.service`
- ExecStart: `.venv/bin/ocos run`
- 改了 .py 要清 pycache + `systemctl --user restart ocos-daemon`

### 测试
- 跑: `.venv/bin/python3 -m pytest`
- 基线: 2681 tests passed
- 不能引入回归

### 本轮已完成的修复（不能回退）
| Commit | 内容 |
|--------|------|
| `6017f18` | 数字生命全链路升级（主动交互/自举联网/对抗性思维/跨session记忆） |
| 还没 commit | EpistemicDrive 三种好奇心（explore/growth/repair）— motivation.py 已改但还没 push？**检查一下** |

---

## 11. 验收标准

Phase 4 完成后，跑一个验收 checklist：

- [ ] `ocos daily-self-care scan` 能输出有效 JSON
- [ ] systemd timer 已 enable 并 active
- [ ] 第一次 timer 触发后 episodes 表有 `action='daily_self_care.run'` 行
- [ ] `~/.ocos/reports/daily_{date}.json` 存在且包含 S1-S5 全部扫描结果
- [ ] 下次 EpistemicDrive.suggest_explore() 能产出"从未触及的模块探索"类 goal
- [ ] 2681 tests 全部通过
- [ ] daemon 正常运行（timer 不影响 daemon）

---

## 12. 开放问题（新对话可能需要解决）

1. **桶 B 自动执行边界**：删除 _archive/ 下的死代码是安全的（_archive 本来就是归档），但自动删除活跃模块的死函数风险高。Phase 3 可能需要区分"归档死代码 → 自动删"和"活跃死函数 → 只报告"。
2. **桶 C goal 创建路径**：现在 EpistemicDrive.suggest_explore() 返回 goal 文本列表，需要一个从 goal 文本到实际 goal 表记录的路径。可能需要调 `MotivationHub.propose_goals()` 或直接写 goals 表。
3. **桶 A 紧急修复触发**：ImportError 应该触发 daemon 重启（让 watchdog 处理），而不是等 daily cycle。Phase 3 可能需要桶 A 的修复路径直接走 watchdog 而不是 repair_link。
4. **扫描超时 60s 是否合理**：CodeHealthScanner S1（import 检查）可能因为 pip 包依赖多而慢。60s 可能不够——需要实测。
5. **是否需要 daemon 也能触发 daily cycle**：用户可能想手动触发或让 daemon 每 7 天也跑一次。Phase 4 后可能需要加一个 `ocos daily-self-care run --force` 命令。
