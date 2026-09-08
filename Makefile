.PHONY: test gate full-gate clean lint coverage e2e vitals-check longrun-start longrun-verify

# 快速测试
test:
	python3 -m pytest -q

# 完整 Gate 检查
gate:
	python3 scripts/check_version_consistency.py
	python3 scripts/phase24_gate.py
	python3 scripts/phase25_gate.py
	python3 scripts/phase27_28_gate.py
	python3 scripts/verify_freeze.py

# Gate + 全量测试
full-gate: gate test
	@echo "All gates + tests passed"

# 升级方案 v1.0 §3.4: 生命体征阈值 Gate（不达标 exit 2）
#   make vitals-check              — 默认 L4 阶段、7 天窗
#   make vitals-check PHASE=L2     — 按阶段验收
#   make vitals-check WINDOW=30    — 自定义聚合窗口
PHASE ?= L4
WINDOW ?= 7
vitals-check:
	python3 -m ocos.interaction.cli.main vitals --check --phase $(PHASE) --window $(WINDOW)

# 升级方案 v1.0 §3.3 第三层: 24h/7 天无人值守长跑（LEVEL=2 挂机）
#   make longrun-start              — LEVEL=2 → 重启双服务 → 启动采样器（默认 24h）
#   make longrun-start HOURS=168    — 7 天连续长跑
#   make longrun-verify             — 终验门禁（存活/异常/泄漏/体征，不过 exit 2）
HOURS ?= 24
INTERVAL_SEC ?= 300
longrun-start:
	python3 -m ocos.interaction.cli.main autonomy 2
	python3 -m ocos.interaction.cli.main restart
	mkdir -p $(HOME)/.ocos/longrun
	nohup bash deploy/longrun/longrun_watch.sh $(INTERVAL_SEC) $$(( $(HOURS) * 3600 )) \
		>> $(HOME)/.ocos/longrun/watch.log 2>&1 & \
		echo "longrun watcher started — $$! h 后运行 make longrun-verify 验收（HOURS=$(HOURS)）"

longrun-verify:
	bash deploy/longrun/verify_24h.sh

# Behavioral Delta（AGI 落地计划 P0/ER-2 基座）
behavior-delta:
	python3 scripts/behavior_delta.py --task host-analysis --json
	python3 scripts/behavior_delta.py --task file-write --json

# E2E 端到端测试
e2e:
	python3 -m pytest tests/test_e2e/ -v

# 代码覆盖率
coverage:
	python3 -m pytest --cov=ocos --cov-report=term -q

# 清理 __pycache__
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true

# Lint (如果有工具)
lint:
	python3 -m py_compile ocos/__init__.py
	@echo "compile check OK"
