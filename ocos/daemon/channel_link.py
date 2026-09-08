"""L2-3: 出站多通道链路 — TUI 之外的第二个出口（hermes-gateway 对接点）。

升级方案 v1.0 §L2: channel 多通道上电 — daemon 主动消息除 outbox
（TUI 对话流）外，可分发到注册的外部通道（hermes-gateway 消息平台网关
已在 systemd 运行，经 webhook URL 对接）。

诚实性约束（继承既有 Hard Constraint）:
  - 外发只投递**结果/报告类**消息（goal 结果、成长叙事、自检告警、
    参与度提议），非结果闲聊仍只进 outbox 日志视图，绝不外发
  - outbox 是主出口：通道分发是**附加**出口，任何失败不影响 outbox
  - 分发失败记录 health（ChannelHealth），连续失败通道自动失活（降级）
  - 异步分发（worker 线程 + 队列），绝不阻塞 daemon tick

配置源:
    OCOS_OUTBOUND_WEBHOOK_URL 环境变量（可选 OCOS_OUTBOUND_WEBHOOK_SECRET
    签名密钥），或 ~/.ocos/config.json:
        "channels": [{"type": "webhook", "name": "hermes",
                      "url": "http://127.0.0.1:PORT/webhooks/ocos",
                      "secret": "<per-route HMAC secret>", "enabled": true}]
    配置 secret 时 POST 携带 X-Hub-Signature-256（sha256 HMAC，hermes
    webhook 路由校验格式）。
"""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


class OutboundChannelLink:
    """出站通道分发器（fire-and-forget，绝不阻塞主流程）。"""

    def __init__(self, config_path: Path | None = None) -> None:
        self._queue: queue.Queue[tuple[str, int]] = queue.Queue(maxsize=100)
        self._interaction = self._build_interaction(config_path)
        self._dropped = 0
        self._worker: threading.Thread | None = None
        if self._interaction is not None and self._interaction.channel_count > 0:
            self._worker = threading.Thread(
                target=self._work_loop, name="ocos-outbound-channel", daemon=True)
            self._worker.start()

    # ── 装配 ──────────────────────────────────────────────────────────

    @staticmethod
    def _build_interaction(config_path: Path | None):
        """从环境变量/config.json 装配通道。无配置 → None（诚实沉默）。"""
        from ocos.interaction.channel import ExternalInteraction
        interaction = ExternalInteraction()
        targets: list[tuple[str, str, str]] = []   # (name, url, secret)
        env_url = os.environ.get("OCOS_OUTBOUND_WEBHOOK_URL", "").strip()
        env_secret = os.environ.get("OCOS_OUTBOUND_WEBHOOK_SECRET", "").strip()
        if env_url:
            targets.append(("webhook-env", env_url, env_secret))
        path = config_path or (Path.home() / ".ocos" / "config.json")
        try:
            if path.exists():
                cfg = json.loads(path.read_text(encoding="utf-8"))
                for ch in cfg.get("channels", []) or []:
                    if not isinstance(ch, dict):
                        continue
                    if (ch.get("type") == "webhook" and ch.get("enabled", True)
                            and ch.get("url")):
                        targets.append((str(ch.get("name", "webhook")),
                                        str(ch["url"]),
                                        str(ch.get("secret", ""))))
        except (OSError, ValueError) as e:
            logger.debug("channel config read failed: %s", e)
        for name, url, secret in targets:
            try:
                interaction.add_channel(
                    ExternalInteraction.create_webhook_channel(
                        name, url, secret=secret))
            except Exception as e:
                logger.warning("channel %s register failed: %s", name, e)
        return interaction if interaction.channel_count > 0 else None

    # ── 对外接口 ──────────────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return self._interaction is not None

    @property
    def channel_names(self) -> list[str]:
        if self._interaction is None:
            return []
        return list(self._interaction.get_all_status().keys())

    def dispatch(self, message: str, priority: int = 3) -> bool:
        """结果类消息入分发队列。无通道/队列满 → 丢弃（计数，不阻塞）。"""
        if not self.enabled:
            return False
        try:
            self._queue.put_nowait((message[:4000], priority))
            return True
        except queue.Full:
            self._dropped += 1
            logger.debug("outbound channel queue full, dropped (%d total)",
                         self._dropped)
            return False

    def status(self) -> dict:
        if self._interaction is None:
            return {"enabled": False, "channels": {}, "dropped": self._dropped}
        return {"enabled": True,
                "channels": self._interaction.get_all_status(),
                "dropped": self._dropped}

    # ── worker ────────────────────────────────────────────────────────

    def _work_loop(self) -> None:
        while True:
            message, priority = self._queue.get()
            try:
                self._interaction.send(message, priority)
            except Exception as e:   # 通道崩溃不杀死 worker
                logger.debug("channel dispatch failed: %s", e)
            finally:
                self._queue.task_done()


__all__ = ["OutboundChannelLink"]
