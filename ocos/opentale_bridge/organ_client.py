"""OrganClient — OCOS → OpenTale Organ API 的 HTTP 客户端（S4 落地）。

契约基准：docs/runtime/OPENTALE_ORGAN_API_CONTRACT_20260818.md（固定版）。

职责（S4-③/④/⑤）：
  1. goal/decision → Organ action 提交（generate/resume/rewrite/verify/analyze）
  2. 任务轮询 + 增量事件流（task_id → 状态/事件）
  3. 结果回收（草稿/章节/项目报告）
  4. 确认流（accept/reject，高风险动作须显式确认）
  5. 错误处理（超时/失败/LLM 空响应降级）

实现：urllib（零额外依赖，ocos/opentale 两侧均可运行）。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Optional


class OrganClientError(Exception):
    """Organ API 调用错误（网络/超时/HTTP 非 2xx）。"""


class OrganTaskTimeout(OrganClientError):
    """任务轮询超时。"""


class OrganClient:
    """OpenTale Organ API 客户端（同步 HTTP）。"""

    def __init__(self, base_url: str = "http://127.0.0.1:8000/api/organ",
                 timeout_seconds: float = 30.0,
                 poll_interval_seconds: float = 5.0,
                 task_timeout_seconds: float = 3600.0,
                 trace_context: Any = None,
                 auth_token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.task_timeout_seconds = task_timeout_seconds
        # R1.5：客户端级默认 TraceContext（None = 不注入，向后兼容）
        self._default_tc = trace_context
        # BR-03 修复（2026-08-24）：Bearer token，默认读 OCOS_OPENTALE_TOKEN。
        # 仅 mutation 方法注入（与 OpenTale auth 中间件 mutation 拦截面对齐）
        if auth_token is None:
            import os
            auth_token = os.getenv("OCOS_OPENTALE_TOKEN", "") or None
        self.auth_token = auth_token

    # ── HTTP 基础 ──

    def _request(self, method: str, path: str,
                 body: dict[str, Any] | None = None,
                 trace_context: Any = None) -> Any:
        from ocos.opentale_bridge.ocos_activation import activate
        activate("G1_organ_api")
        url = f"{self.base_url}{path}"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        # BR-03（2026-08-24）：mutation 请求注入 Bearer token（生产模式必需）
        if self.auth_token and method in ("POST", "PUT", "PATCH", "DELETE"):
            req.add_header("Authorization", f"Bearer {self.auth_token}")
        # R1.5：结构化 TraceContext 统一注入（R1.1 契约 §3-4）
        tc = trace_context or self._default_tc
        if tc is not None:
            from ocos.opentale_bridge.trace_context import TraceContext
            if isinstance(tc, TraceContext):
                for k, v in tc.to_headers().items():
                    req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read()
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = json.loads(e.read().decode("utf-8")).get("detail", "")
            except Exception:
                pass
            raise OrganClientError(f"HTTP {e.code} {path}: {detail or e.reason}")
        except urllib.error.URLError as e:
            raise OrganClientError(f"网络错误 {path}: {e.reason}")

    def _get(self, path: str, trace_context: Any = None) -> Any:
        return self._request("GET", path, trace_context=trace_context)

    def _post(self, path: str, body: dict[str, Any] | None = None,
              trace_context: Any = None) -> Any:
        return self._request("POST", path, body, trace_context=trace_context)

    # ── 只读：器官状态 ──

    def health(self) -> dict[str, Any]:
        return self._get("/health")

    def status(self) -> dict[str, Any]:
        return self._get("/status")

    def projects(self) -> list[dict[str, Any]]:
        return self._get("/projects")

    def project(self, title: str) -> dict[str, Any]:
        from urllib.parse import quote
        return self._get(f"/projects/{quote(title)}")

    def chapter(self, title: str, chapter_num: int) -> dict[str, Any]:
        from urllib.parse import quote
        return self._get(f"/projects/{quote(title)}/chapters/{chapter_num}")

    def drafts(self, project: str, chapter: int) -> dict[str, Any]:
        from urllib.parse import quote
        return self._get(f"/drafts/{quote(project)}/{chapter}")

    # ── 写作动作提交（S4-③） ──

    def generate(self, *, title: str, content: str, genre: str = "general",
                 chapters: int = 10, target_words: int = 25000,
                 characters: list[str] | None = None,
                 roles: dict[str, str] | None = None,
                 genders: dict[str, str] | None = None,  # S8: 名字→男/女
                 world: list[str] | None = None,
                 style: str = "commercial", language: str = "zh",
                 trace_context: Any = None) -> dict[str, Any]:
        """新书生成（支持设定契约，防主角漂移）。"""
        return self._post("/actions/generate", {
            "title": title, "content": content, "genre": genre,
            "chapters": chapters, "target_words": target_words,
            "characters": characters or [], "roles": roles or {},
            "genders": genders or {},
            "world": world or [], "style": style, "language": language,
        }, trace_context=trace_context)

    def resume(self, project: str, instruction: str = "",
                 trace_context: Any = None) -> dict[str, Any]:
        return self._post("/actions/resume", {"project": project, "instruction": instruction},
                          trace_context=trace_context)

    def rewrite(self, project: str, chapter: int, instruction: str = "",
                  trace_context: Any = None) -> dict[str, Any]:
        return self._post("/actions/rewrite",
                          {"project": project, "chapter": chapter, "instruction": instruction},
                          trace_context=trace_context)

    def verify(self, project: str, trace_context: Any = None) -> dict[str, Any]:
        return self._post("/actions/verify", {"project": project}, trace_context=trace_context)

    def analyze(self, project: str, trace_context: Any = None) -> dict[str, Any]:
        return self._post("/actions/analyze", {"project": project}, trace_context=trace_context)

    # ── 任务轮询 + 事件流（S4-④） ──

    def task(self, task_id: str, trace_context: Any = None) -> dict[str, Any]:
        return self._get(f"/tasks/{task_id}", trace_context=trace_context)

    def events(self, task_id: str, since: int = 0, trace_context: Any = None) -> dict[str, Any]:
        return self._get(f"/tasks/{task_id}/events?since={since}", trace_context=trace_context)

    def wait(self, task_id: str, timeout_seconds: float | None = None,
             poll_interval: float | None = None) -> dict[str, Any]:
        """轮询直至任务终态（completed/failed/cancelled/rejected）。

        返回最终任务状态；超时抛 OrganTaskTimeout。
        """
        deadline = time.time() + (timeout_seconds or self.task_timeout_seconds)
        interval = poll_interval or self.poll_interval_seconds
        while True:
            t = self.task(task_id)
            if t.get("status") in ("completed", "failed", "cancelled", "rejected"):
                return t
            if time.time() > deadline:
                raise OrganTaskTimeout(
                    f"任务 {task_id} 轮询超时（{(timeout_seconds or self.task_timeout_seconds)/60:.0f} 分钟），"
                    f"当前状态: {t.get('status')}")
            time.sleep(interval)

    def wait_events(self, task_id: str, since: int = 0,
                    timeout_seconds: float | None = None) -> list[dict[str, Any]]:
        """轮询直至终态并回收全部增量事件。"""
        final = self.wait(task_id, timeout_seconds=timeout_seconds)
        collected: list[dict[str, Any]] = []
        cur = since
        while True:
            page = self.events(task_id, since=cur)
            collected.extend(page.get("events", []))
            nxt = page.get("next_since", cur)
            if nxt <= cur:
                break
            cur = nxt
        return collected

    # ── 确认流（S4-⑤） ──

    def accept(self, task_id: str, trace_context: Any = None) -> dict[str, Any]:
        """采纳草稿（写入项目）。高风险动作——调用方须先经用户确认。"""
        return self._post(f"/tasks/{task_id}/accept", trace_context=trace_context)

    def reject(self, task_id: str, trace_context: Any = None) -> dict[str, Any]:
        return self._post(f"/tasks/{task_id}/reject", trace_context=trace_context)

    # ── 结果回收 ──

    def collect_generated(self, title: str, chapters: int = 10) -> dict[str, Any]:
        """回收生成结果：项目报告 + 各章正文（供 OCOS 记忆/学习）。"""
        report = self.project(title)
        chapters_data: dict[int, str] = {}
        n = report.get("chapters") or 0
        for i in range(1, max(1, min(n, chapters)) + 1):
            try:
                chapters_data[i] = self.chapter(title, i).get("content", "")
            except OrganClientError:
                continue
        return {"report": report, "chapters": chapters_data}

    # ── 高阶流程：一次生成并等待 ──

    def generate_and_wait(self, *, title: str, content: str, **kwargs: Any) -> dict[str, Any]:
        """提交生成 → 轮询至终态 → 返回任务结果。"""
        submitted = self.generate(title=title, content=content, **kwargs)
        task_id = submitted["task_id"]
        return self.wait(task_id)
