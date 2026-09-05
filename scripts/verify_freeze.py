#!/usr/bin/env python3
"""S4.4: Scope Freeze 签名校验（白皮书 P4）。

对 12 个 ABI_MODULES 逐个收集公开签名（函数/类 + inspect.signature）
并 SHA-256 指纹，与冻结清单基线比对；不一致 → FROZEN_VIOLATION。

用法:
  python3 scripts/verify_freeze.py            # 校验（不一致退出码 1）
  python3 scripts/verify_freeze.py --baseline # 基线化：以当前代码生成 manifest
                                              # （首次启用/有意变更签名后运行）

注意（评审版 S4.4-3）：首次启用存在存量 diff 属预期——先跑一次 --baseline
固化首份签名，后续变更才触发比对。OCOS_FREEZE_STRICT=true 时校验失败 raise。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "ocos" / "os_v1" / "freeze_manifest.json"


def _build_freeze() -> object:
    """构建 OSFreeze 实例（复用 freeze 模块实现）。"""
    sys.path.insert(0, str(ROOT))
    from ocos.os_v1.freeze import OSFreeze
    return OSFreeze()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="store_true",
                        help="以当前代码生成冻结基线（--baseline 固化）")
    args = parser.parse_args()

    freeze = _build_freeze()

    if args.baseline:
        manifest = freeze.freeze(tick_id=0)
        MANIFEST_PATH.write_text(
            json.dumps(manifest.__dict__, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"基线已固化 → {MANIFEST_PATH}（{len(manifest.signatures)} 模块指纹）")
        return 0

    if not MANIFEST_PATH.exists():
        print(f"无基线文件 {MANIFEST_PATH} — 先运行 --baseline 固化。")
        return 1

    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    from ocos.os_v1.os_types import FreezeManifest
    freeze.manifest = FreezeManifest(**raw)

    violations = freeze.verify()
    if violations:
        for v in violations:
            print(f"  [VIOLATION] {v}")
        print("ABI 签名漂移 — 若为有意变更，重跑 --baseline 更新基线。")
        return 1
    print(f"Freeze 校验通过：{len(freeze.manifest.abi_modules)} 个 ABI 模块签名一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
