.PHONY: test gate full-gate clean lint coverage e2e

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
