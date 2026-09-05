"""S3.7: 代理变量线程安全回归（白皮书 P3）。

原缺陷：generate 前 pop 全部 *proxy* 环境变量、finally 恢复——进程级
全局状态无锁，多线程并发 LLM 调用互相踩踏。现代理隔离下沉到 provider
（AsyncOpenAI trust_env=False），不再触碰进程环境。
"""

from __future__ import annotations

import asyncio
import os
import threading

import pytest


@pytest.fixture
def clean_proxy_env():
    saved = {k: v for k, v in os.environ.items() if "proxy" in k.lower()}
    for k in list(saved):
        os.environ.pop(k, None)
    yield
    os.environ.update(saved)


class TestProxyIsolation:
    def test_generate_does_not_touch_process_env(self, clean_proxy_env,
                                                 monkeypatch):
        """generate 全程不修改进程环境变量。"""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-s37")
        os.environ["HTTP_PROXY"] = "http://127.0.0.1:3128"
        from ocos.engines.text_generator import OpenaiProvider

        provider = OpenaiProvider(api_key="sk-test-s37",
                                  base_url="http://127.0.0.1:9/v1",
                                  model="m")
        try:
            asyncio.run(provider.generate("hi", max_tokens=8))
        except Exception:
            pass  # 网络/SDK 错误不影响断言
        assert os.environ.get("HTTP_PROXY") == "http://127.0.0.1:3128", \
            "generate 不得 pop 进程代理变量"

    def test_concurrent_generate_env_stable(self, clean_proxy_env):
        """10 线程并发调用后环境变量保持不变。"""
        os.environ["HTTPS_PROXY"] = "http://127.0.0.1:3128"
        from ocos.engines.text_generator import OpenaiProvider

        provider = OpenaiProvider(api_key="sk-x",
                                  base_url="http://127.0.0.1:9/v1",
                                  model="m")

        def worker():
            try:
                asyncio.run(provider.generate("hi", max_tokens=8))
            except Exception:
                pass

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert os.environ.get("HTTPS_PROXY") == "http://127.0.0.1:3128"
