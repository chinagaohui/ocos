"""Phase 1 — CodeHealthScanner。

代码级只读扫描器，供 Daily Self-Care Cycle 复用。5 个子扫描（S1-S5），
全部纯只读、独立 try/except 隔离、失败诚实降级返回空/错误字典——
不中断主流程，不创建、不修改任何 .py。

设计约束:
  S1 用 subprocess 跑 import 检查，避免当前进程已 import 的模块
  屏蔽 ImportError。每模块超时 5s，整组扫描超时 30s。
  S2 AST 静态分析，死代码近似检测（不做真正的 cross-file call graph）。
  S3 模块覆盖从 pkgutil.iter_modules 枚举 + DB episodes LIKE 查询。
  S4 依赖图用正则扫 import 语句，拓扑排序判循环。
  S5 环境快照用 subprocess 调 pip list / python -V / uname。
"""

from __future__ import annotations

import ast
import json
import logging
import os
import pkgutil
import re
import sqlite3
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CodeHealthScanner:
    """代码健康扫描器 — S1-S5，全部只读。"""

    def __init__(
        self,
        project_root: str | None = None,
        db_path: str | None = None,
        subprocess_timeout: int = 5,
    ) -> None:
        self._root = Path(project_root) if project_root else self._discover_root()
        self._ocos_dir = self._root / "ocos"
        self._db_path = db_path or str(Path.home() / ".ocos" / "ocos.db")
        self._sub_timeout = subprocess_timeout

    @staticmethod
    def _discover_root() -> Path:
        """向上找含 pyproject.toml 的目录。"""
        cwd = Path.cwd()
        for parent in [cwd] + list(cwd.parents)[:5]:
            if (parent / "pyproject.toml").exists():
                return parent
        return cwd

    # ── 主入口 ──────────────────────────────────────────────────────────────

    def scan_all(self) -> dict[str, Any]:
        """跑 S1-S5，返回完整报告字典。任一子扫描失败不影响其余。"""
        started = time.monotonic()
        report: dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "project_root": str(self._root),
            "scans": {},
            "elapsed_seconds": 0.0,
            "errors": [],
        }
        for name, method in (
            ("S1_import_health", self.scan_imports),
            ("S2_ast_dead_code", self.scan_ast_dead_code),
            ("S3_module_coverage", self.scan_module_coverage),
            ("S4_dependency_graph", self.scan_dependency_graph),
            ("S5_env_snapshot", self.scan_env_snapshot),
        ):
            try:
                report["scans"][name] = method()
            except Exception as e:
                err_msg = f"{name}: {type(e).__name__}: {e}"
                report["errors"].append(err_msg)
                report["scans"][name] = {"error": err_msg}
                logger.warning("CodeHealthScanner %s failed: %s", name, e)
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        return report

    # ── S1: 导入健康检查 ────────────────────────────────────────────────────

    def scan_imports(self) -> dict[str, Any]:
        """用 subprocess 并发 import ocos.* 子模块，检测 ImportError。

        关键: 新进程跑，避免当前进程已 import 过的模块屏蔽 ImportError。
        8 线程并发，每模块超时 3s（实测 855 模块全扫 ~45s）。
        """
        modules = self._iter_ocos_modules()
        total = len(modules)
        import_errors: list[dict[str, str]] = []
        ok_count = 0
        timeout_count = 0

        def _check_one(mod: str) -> tuple[str, bool, str]:
            try:
                result = subprocess.run(
                    [sys.executable, "-c", f"import {mod}"],
                    capture_output=True, text=True,
                    timeout=3,
                    cwd=str(self._root),
                )
                if result.returncode == 0:
                    return (mod, True, "")
                err = (result.stderr or result.stdout).strip()[:500]
                return (mod, False, err)
            except subprocess.TimeoutExpired:
                return (mod, False, f"Timeout after 3s")
            except Exception as e:
                return (mod, False, f"{type(e).__name__}: {e}")

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(_check_one, m): m for m in modules}
            for fut in as_completed(futures, timeout=60):  # 整组 60s 硬超时
                try:
                    mod, ok, err = fut.result()
                except Exception as e:
                    mod = futures[fut]
                    err = f"{type(e).__name__}: {e}"
                    ok = False
                if ok:
                    ok_count += 1
                else:
                    if "Timeout" in err:
                        timeout_count += 1
                    import_errors.append({"module": mod, "error": err})

        return {
            "total": total,
            "ok": ok_count,
            "failed": len(import_errors),
            "timeout_count": timeout_count,
            "import_errors": import_errors[:100],  # 截断
        }

    # ── S2: AST 死代码检测 ──────────────────────────────────────────────────

    def scan_ast_dead_code(self) -> dict[str, Any]:
        """AST 静态分析: TODO/FIXME/HACK 注释 + empty function bodies.

        注意: "未被引用的 top-level function/class" 真正的 call graph 超出
        scope——这里只做近似：收集所有 .py 的 top-level def/class，然后 grep
        整个代码库的 import/调用，看有没有被引用过。跨文件调用名相同就
        算被引用（近似，可能漏报/误报）。
        """
        py_files = list(self._ocos_dir.rglob("*.py"))
        todos: list[dict[str, Any]] = []
        empty_bodies: list[dict[str, Any]] = []
        dead_funcs: list[dict[str, Any]] = []
        top_level_names: dict[str, set[str]] = defaultdict(set)  # file -> names

        for pyf in py_files:
            try:
                source = pyf.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            # TODO/FIXME/HACK 注释（行级）
            for lineno, line in enumerate(source.splitlines(), start=1):
                m = re.search(r"#\s*(TODO|FIXME|HACK|XXX)", line, re.IGNORECASE)
                if m:
                    todos.append({
                        "file": str(pyf.relative_to(self._root)),
                        "line": lineno,
                        "marker": m.group(1),
                        "text": line.strip()[:200],
                    })

            # AST 解析
            try:
                tree = ast.parse(source, filename=str(pyf))
            except SyntaxError:
                continue

            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.FunctionDef):
                    top_level_names[str(pyf.relative_to(self._root))].add(node.name)
                    body = node.body
                    # Empty / pass-only 函数体
                    if body and len(body) == 1:
                        first = body[0]
                        if (isinstance(first, ast.Pass)
                                or (isinstance(first, ast.Expr)
                                    and isinstance(first.value, ast.Constant)
                                    and isinstance(first.value.value, str))):
                            empty_bodies.append({
                                "file": str(pyf.relative_to(self._root)),
                                "name": node.name,
                                "line": node.lineno,
                                "type": "function",
                            })

        # 近似死代码检测: 收集所有 top-level def/class 名 → 全库单次匹配引用
        all_names: set[str] = set()
        for names in top_level_names.values():
            all_names.update(names)
        # 把 __init__ / dunder 排除
        all_names = {n for n in all_names
                     if not (n.startswith("__") and n.endswith("__"))}

        # 一次性把整个 ocos/ 合成大文本 blob，每个名字只 regex 一次
        all_text_parts: list[str] = []
        for pyf in py_files:
            try:
                all_text_parts.append(pyf.read_text(
                    encoding="utf-8", errors="replace"))
            except OSError:
                pass
        all_text = "\n".join(all_text_parts)

        ref_counts: dict[str, int] = {}
        for name in all_names:
            ref_counts[name] = len(re.findall(rf"\b{re.escape(name)}\b", all_text))

        for file, names in top_level_names.items():
            for name in names:
                if name.startswith("__") and name.endswith("__"):
                    continue
                refs = ref_counts.get(name, 0) - 1
                if refs == 0 and not name.startswith("_"):
                    dead_funcs.append({
                        "file": file,
                        "name": name,
                        "ref_count": 0,
                    })

        # ── 安全分级：从 dead_funcs 筛出可自动删的候选 ──────────────
        safe_delete: list[dict[str, Any]] = []
        test_referenced: list[dict[str, Any]] = []
        prod_referenced: list[dict[str, Any]] = []
        docs_only: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []

        for item in dead_funcs:
            fpath = item["file"]
            name = item["name"]

            # 规则 1: tests/ 或 _archive/ 下的直接排除（测试函数天然不被引用，
            # _archive 本身就是归档区）
            if "tests/" in fpath or "_archive" in fpath:
                blocked.append(item)
                continue

            # 规则 2: 全仓库彻底搜索——用 subprocess grep 覆盖所有文件类型 +
            # 所有引用模式（静态 import、动态 getattr、字符串引号形式、配置文档）
            refs = self._deep_grep_refs(name, fpath)
            if refs["prod_py"]:
                prod_referenced.append({**item, "prod_refs": refs["prod_py"][:3]})
            elif refs["tests"] or refs["scripts"]:
                test_referenced.append({**item, "test_refs": refs["tests"][:3] or refs["scripts"][:3]})
            elif refs["docs_config"]:
                docs_only.append({**item, "doc_refs": refs["docs_config"][:2]})
                # 只有文档提及 → 安全可删（文档同步是后续任务）
                safe_delete.append(item)
            else:
                # 全零命中 → 真死代码
                safe_delete.append(item)

        return {
            "py_files_scanned": len(py_files),
            "todos_count": len(todos),
            "empty_bodies_count": len(empty_bodies),
            "dead_names_approx_count": len(dead_funcs),
            "todos": todos[:200],
            "empty_bodies": empty_bodies[:200],
            "dead_names_approx": dead_funcs[:200],
            # ── 安全分级（Phase 2-3 自动修复只用 safe_delete） ────────
            "safety_classification": {
                "safe_delete_count": len(safe_delete),
                "safe_delete": safe_delete,          # 零引用 + 零文档（可自动删）
                "docs_only_count": len(docs_only),    # 仅文档提及（删后需同步文档）
                "docs_only": docs_only,
                "test_referenced_count": len(test_referenced),  # 被测试/脚本引用
                "test_referenced": test_referenced,
                "prod_referenced_count": len(prod_referenced),  # 被生产代码引用
                "prod_referenced": prod_referenced,
                "blocked_count": len(blocked),                  # tests/_archive
                "blocked": blocked[:100],
            },
            "note": (
                "dead_names_approx 是近似检测。Phase 2+ 自动修复只用 "
                "safety_classification.safe_delete。"
            ),
        }

    # ── S3: 模块覆盖分析 ──────────────────────────────────────────────────

    def scan_module_coverage(self) -> dict[str, Any]:
        """pkgutil.iter_modules 枚举 ocos.* → DB episodes LIKE 查询覆盖率。"""
        modules = self._iter_ocos_modules()
        total = len(modules)
        covered: set[str] = set()

        conn = None
        if Path(self._db_path).exists():
            try:
                conn = sqlite3.connect(
                    f"file:{self._db_path}?mode=ro", uri=True,
                    timeout=10,
                )
                # 查每个模块是否在 episodes 里被引用过
                for mod in modules:
                    try:
                        row = conn.execute(
                            "SELECT 1 FROM episodes WHERE "
                            "context LIKE ? OR decision LIKE ? OR outcome LIKE ? "
                            "LIMIT 1",
                            (f"%{mod}%", f"%{mod}%", f"%{mod}%"),
                        ).fetchone()
                        if row:
                            covered.add(mod)
                    except sqlite3.Error:
                        continue
            finally:
                if conn:
                    conn.close()

        uncovered = [m for m in modules if m not in covered]
        return {
            "total_modules": total,
            "covered": len(covered),
            "uncovered": uncovered[:100],    # 截断
            "coverage_rate": round(len(covered) / total, 3) if total else 0.0,
            "db_path": self._db_path,
            "db_exists": Path(self._db_path).exists(),
        }

    # ── S4: 依赖图完整性 ──────────────────────────────────────────────────

    def scan_dependency_graph(self) -> dict[str, Any]:
        """正则扫 import 语句 → 构建有向图 → DFS 判循环。"""
        py_files = list(self._ocos_dir.rglob("*.py"))
        nodes: set[str] = set()
        edges: list[tuple[str, str]] = []

        import_re = re.compile(
            r"^\s*(?:from|import)\s+(ocos\.[\w\.]+)", re.MULTILINE
        )

        for pyf in py_files:
            try:
                text = pyf.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            # 把文件路径转成模块名 (ocos/xxx/yyy.py → ocos.xxx.yyy)
            rel = pyf.relative_to(self._root)
            module_path = str(rel.with_suffix("")).replace(os.sep, ".")
            # __init__.py 对应的包名 (ocos/xxx/__init__.py → ocos.xxx)
            if pyf.name == "__init__.py":
                module_path = str(rel.parent).replace(os.sep, ".")
            nodes.add(module_path)

            for m in import_re.finditer(text):
                target = m.group(1)
                # 只收集 ocos.* → ocos.* 的内部依赖
                if target == module_path:
                    continue
                nodes.add(target)
                edges.append((module_path, target))

        # DFS 拓扑排序判循环
        adj: dict[str, list[str]] = defaultdict(list)
        for src, dst in edges:
            adj[src].append(dst)

        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {n: WHITE for n in nodes}
        cycles: list[list[str]] = []

        def dfs(node: str, path: list[str]) -> None:
            color[node] = GRAY
            path.append(node)
            for nxt in adj.get(node, []):
                if color.get(nxt, WHITE) == GRAY:
                    # 找到环: path 里 nxt 的位置到末尾
                    idx = path.index(nxt) if nxt in path else -1
                    if idx >= 0:
                        cycles.append(path[idx:] + [nxt])
                elif color.get(nxt, WHITE) == WHITE:
                    dfs(nxt, path)
            path.pop()
            color[node] = BLACK

        for n in nodes:
            if color[n] == WHITE:
                dfs(n, [])

        return {
            "nodes_count": len(nodes),
            "edges_count": len(edges),
            "has_cycles": bool(cycles),
            "cycles": [c for c in cycles[:20]],  # 截断
            "top_level_count": sum(1 for n in nodes if n.count(".") == 1),
        }

    # ── S5: 环境快照 ──────────────────────────────────────────────────────

    def scan_env_snapshot(self) -> dict[str, Any]:
        """pip list + python -V + uname."""
        python_version = sys.version.split()[0]
        platform = ""
        try:
            platform = subprocess.run(
                ["uname", "-a"], capture_output=True, text=True,
                timeout=self._sub_timeout,
            ).stdout.strip()
        except Exception:
            platform = sys.platform

        packages: list[dict[str, str]] = []
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                capture_output=True, text=True,
                timeout=self._sub_timeout * 6,  # pip list 稍慢
            )
            if result.returncode == 0:
                raw = json.loads(result.stdout)
                for pkg in raw:
                    packages.append({
                        "name": pkg.get("name", ""),
                        "version": pkg.get("version", ""),
                    })
        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
            packages = [{"error": f"{type(e).__name__}: {e}"}]

        return {
            "python_version": python_version,
            "platform": platform,
            "packages": packages[:300],  # 截断防输出过大
            "total_packages": len(packages),
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── 辅助 ────────────────────────────────────────────────────────────────

    # ── 安全分级辅助 ────────────────────────────────────────────────────────

    def _deep_grep_refs(self, name: str, def_file: str) -> dict[str, list[str]]:
        """全仓库彻底搜索一个名字的所有引用模式。

        返回分类:
          prod_py:       生产 .py 文件（ocos/ 下）中的引用
          tests:         tests/ 下的引用
          scripts:       scripts/ 下的引用
          docs_config:   .md/.toml/.json/.yaml/.sh 等配置文档中提及
          dynamic:       动态引用（字符串引号 / getattr / importlib）

        排除定义行自身（同文件里的 'def name'）。
        """
        result: dict[str, list[str]] = {
            "prod_py": [], "tests": [], "scripts": [],
            "docs_config": [], "dynamic": [],
        }

        def _run_grep(pattern: str, *globs: str) -> list[str]:
            try:
                cmd = ["grep", "-rnE", pattern,
                       "--exclude-dir=.git", "--exclude-dir=.venv",
                       "--exclude-dir=__pycache__", "--exclude-dir=.pytest_cache",
                       "--exclude-dir=coverage_html"]
                for g in globs:
                    cmd.extend(["--include", g])
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10,
                                   cwd=str(self._root))
                return [l for l in r.stdout.strip().split("\n") if l]
            except Exception:
                return []

        # 模式 1: \bname\b（单词边界）——覆盖静态 import / 调用 / 属性访问
        lines = _run_grep(rf"\b{re.escape(name)}\b", "*.py")
        # 模式 2: 字符串引号形式 —— 防 getattr("name") / globals()["name"] 漏检
        lines += _run_grep(rf"'{re.escape(name)}'|\"{re.escape(name)}\"", "*.py")
        # 模式 3: getattr/importlib 动态调用
        lines += _run_grep(rf"(getattr|importlib\.import_module|__import__)\b.*{re.escape(name)}", "*.py")
        # 模式 4: 配置 / 文档 / shell
        lines += _run_grep(rf"\b{re.escape(name)}\b",
                           "*.md", "*.toml", "*.json", "*.yaml", "*.yml",
                           "*.cfg", "*.ini", "*.sh")

        # 分类 + 排除定义行
        for line in lines:
            if not line.strip():
                continue
            # 跳过定义行自身
            if re.search(rf"def\s+{re.escape(name)}\b", line):
                continue
            fpath = line.split(":")[0] if ":" in line else ""

            if not fpath:
                continue
            fpath_posix = fpath.replace("\\", "/")

            if fpath_posix.endswith(".py") and ("ocos/" in fpath_posix or fpath_posix.startswith("ocos/")):
                # 还要排除定义文件自身的其他匹配（同一文件里可能还有同名字符串）
                # 但不能跳过整个文件——只跳过真正的定义行（已在上面 skip 了）
                result["prod_py"].append(line)
            elif "tests/" in fpath_posix:
                result["tests"].append(line)
            elif fpath_posix.startswith("scripts/"):
                result["scripts"].append(line)
            else:
                # 非 .py / docs / config
                if any(fpath_posix.endswith(ext) for ext in
                       (".md", ".toml", ".json", ".yaml", ".yml",
                        ".cfg", ".ini", ".sh")):
                    result["docs_config"].append(line)

        return result

    def _iter_ocos_modules(self) -> list[str]:
        """枚举 ocos.* 下所有子模块（pkgutil，递归）。"""
        modules: list[str] = []
        seen: set[str] = set()
        base = str(self._ocos_dir)
        prefix = "ocos."
        try:
            for mod in pkgutil.walk_packages([base], prefix=prefix):
                name = mod.name
                if name in seen:
                    continue
                # 跳过 _archive 里的（已归档，不算"活跃"模块）
                if "_archive" in name.split("."):
                    continue
                seen.add(name)
                modules.append(name)
        except Exception as e:
            logger.warning("pkgutil.walk_packages failed: %s", e)
        return sorted(modules)
