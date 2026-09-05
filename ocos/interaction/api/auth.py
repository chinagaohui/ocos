"""OCOS API 认证 — Bearer Token 中间件（S1.2，白皮书 P1-2）。

Token 存放于 ~/.ocos/config.json 的 api.token 段；未配置时首次访问
自动生成（secrets.token_urlsafe）并写回，文件权限 0600。

豁免路径（供监控探针与 Web UI 静态页）：
    /ocos/health  /  /ui  /ocos/openapi.json  /ocos/docs  /ocos/redoc

显式关闭开关（仅限开发环境）：OCOS_API_AUTH_DISABLED=true。
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from pathlib import Path

logger = logging.getLogger(__name__)

# 豁免认证的路径（健康探针 / UI 静态页 / OpenAPI 自描述）
EXEMPT_PATHS = frozenset({
    "/ocos/health",
    "/",
    "/ui",
    "/ocos/openapi.json",
})
_EXEMPT_PREFIXES = ("/ocos/docs", "/ocos/redoc")


def auth_disabled() -> bool:
    """开发环境显式关闭认证（启动方负责打印警告）。"""
    return os.environ.get("OCOS_API_AUTH_DISABLED", "").strip().lower() == "true"


_TOKEN_CACHE: str | None = None


def get_api_token(config_path: str | None = None,
                  force_reload: bool = False) -> str:
    """读取（必要时生成）API Bearer Token。

    配置优先级：环境变量 OCOS_API_TOKEN > config.json api.token >
    自动生成并写回。测试用 OCOS_CONFIG_PATH 指向临时文件。
    """
    global _TOKEN_CACHE
    env_token = os.environ.get("OCOS_API_TOKEN", "").strip()
    if env_token:
        return env_token
    if _TOKEN_CACHE and not force_reload:
        return _TOKEN_CACHE
    path = Path(config_path
                or os.environ.get("OCOS_CONFIG_PATH", "~/.ocos/config.json")
                ).expanduser()
    cfg: dict = {}
    if path.exists():
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("config.json unreadable (%s) — token 段将重建", e)
            cfg = {}
    api_cfg = cfg.get("api") if isinstance(cfg.get("api"), dict) else {}
    token = str(api_cfg.get("token") or "").strip()
    if not token:
        token = secrets.token_urlsafe(32)
        cfg["api"] = {**api_cfg, "token": token}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
        logger.warning("API token 已自动生成并写入 %s (api.token) — "
                       "客户端需携带 Authorization: Bearer <token>", path)
    _TOKEN_CACHE = token
    return token


def reset_token_cache() -> None:
    """测试辅助：清空进程内 token 缓存。"""
    global _TOKEN_CACHE
    _TOKEN_CACHE = None


async def _json_send(send, status: int, message: str) -> None:
    import json as _json
    body = _json.dumps({"success": False, "message": message,
                        "timestamp": ""}).encode("utf-8")
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json")]})
    await send({"type": "http.response.body", "body": body})


class AuthMiddleware:
    """纯 ASGI Bearer Token 中间件（无第三方依赖）。

    401 = 缺失 Authorization；403 = Token 不匹配。
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or auth_disabled():
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path in EXEMPT_PATHS or path.startswith(_EXEMPT_PREFIXES):
            await self.app(scope, receive, send)
            return
        headers = {k.lower(): v for k, v in scope.get("headers") or []}
        auth_header = headers.get(b"authorization", b"").decode("latin-1")
        if not auth_header:
            await _json_send(send, 401, "missing bearer token")
            return
        if auth_header.strip() != f"Bearer {get_api_token()}":
            await _json_send(send, 403, "invalid bearer token")
            return
        await self.app(scope, receive, send)
