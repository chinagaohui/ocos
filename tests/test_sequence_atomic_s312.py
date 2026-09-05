"""S3.12: sequence 原子化 + kernel EVENT_SCHEMA 去重回归（白皮书 P2）。"""

from __future__ import annotations

import threading

import pytest


class TestSequenceAtomicity:
    def test_concurrent_append_no_duplicate_sequence(self, tmp_path):
        """多线程并发 append：sequence 无重复（原 SELECT MAX/INSERT 分离
        会撞号，撞 event_id 时事件被静默丢弃）。"""
        from ocos.storage.event_store import SQLiteEventStore

        db = str(tmp_path / "t.db")
        store = SQLiteEventStore(db)
        errors: list[Exception] = []

        def worker(w: int):
            try:
                for i in range(50):
                    store.append(
                        event_type=f"w{w}.evt",
                        payload={"w": w, "i": i},
                        event_id=f"ev-{w}-{i}")
            except Exception as e:  # pragma: no cover
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(w,))
                   for w in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        total = store.count()
        assert total == 8 * 50, f"事件丢失: {total}/400"
        # sequence 无重复
        seqs = [r["sequence"] for r in store.load_all()] \
            if hasattr(store, "load_all") else None
        # 用 replay 全量取回核对
        rows = store.replay(limit=1000)
        seq_list = sorted(r["sequence"] for r in rows)
        assert len(seq_list) == len(set(seq_list)), "sequence 存在重复"


class TestKernelSchemaDedupe:
    def test_goal_events_single_registration(self):
        """GOAL_SET/GOAL_UPDATED/GOAL_COMPLETED 不再重复注册
        （后值覆盖前值致 required 字段弱化）。"""
        import ast
        from pathlib import Path
        src = Path("ocos/kernel/event_schema.py").read_text()
        for key in ("GOAL_SET", "GOAL_UPDATED", "GOAL_COMPLETED"):
            count = src.count(f"EventType.{key}:")
            assert count == 1, f"{key} 在 EVENT_SCHEMA 注册了 {count} 次"
