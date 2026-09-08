"""D2（2026-09-07）: WebhookChannel HMAC 签名测试。

hermes-gateway webhook 路由强制校验 X-Hub-Signature-256
（GitHub 风格: "sha256=" + HMAC-SHA256(raw_body, secret)）。
OCOS 外发通道配置 secret 后必须携带同格式签名头。

验证:
  1. 配置 secret → 本地 HTTP server 捕获请求头，重算 HMAC 一致
  2. 未配置 secret → 不带签名头（向后兼容旧目标）
  3. channel_link 从 config.json 读 secret 并透传
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from ocos.interaction.channel import ExternalInteraction


_SECRET = "test-route-secret-0123"


class _CaptureHandler(BaseHTTPRequestHandler):
    """捕获最近一次 POST 的头与 body。"""
    last: dict = {}

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        _CaptureHandler.last = {
            "path": self.path,
            "signature": self.headers.get("X-Hub-Signature-256", ""),
            "body": body,
        }
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status": "delivered"}')

    def log_message(self, *args):   # 静默
        pass


@pytest.fixture()
def server():
    httpd = HTTPServer(("127.0.0.1", 0), _CaptureHandler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/webhooks/ocos"
    httpd.shutdown()


def test_signed_post_carries_valid_hmac(server):
    ch = ExternalInteraction.create_webhook_channel(
        "hermes", server, secret=_SECRET)
    assert ch.send("目标 A 完成：测试签名") is True
    captured = _CaptureHandler.last
    assert captured["signature"].startswith("sha256=")
    expected = "sha256=" + hmac.new(
        _SECRET.encode("utf-8"), captured["body"], hashlib.sha256
    ).hexdigest()
    assert captured["signature"] == expected
    # 载荷包含 message 字段（hermes 路由 --prompt "{message}" 消费）
    assert json.loads(captured["body"])["message"] == "目标 A 完成：测试签名"


def test_unsigned_post_has_no_signature_header(server):
    ch = ExternalInteraction.create_webhook_channel("plain", server)
    assert ch.send("无签名消息") is True
    assert _CaptureHandler.last["signature"] == ""


def test_wrong_secret_fails_hmac(tmp_path, server):
    ch = ExternalInteraction.create_webhook_channel(
        "hermes", server, secret="other-secret")
    assert ch.send("x") is True   # 发送成功（server 不校验）
    captured = _CaptureHandler.last
    expected = "sha256=" + hmac.new(
        _SECRET.encode("utf-8"), captured["body"], hashlib.sha256
    ).hexdigest()
    assert captured["signature"] != expected


def test_channel_link_reads_secret_from_config(tmp_path):
    """channel_link._build_interaction 应从 config.json 透传 secret。"""
    from ocos.daemon.channel_link import OutboundChannelLink

    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "channels": [{"type": "webhook", "name": "hermes",
                      "url": "http://127.0.0.1:1/webhooks/ocos",
                      "secret": _SECRET, "enabled": True}],
    }), encoding="utf-8")
    link = OutboundChannelLink(config_path=cfg)
    assert link.enabled is True
    assert link.channel_names == ["hermes"]
