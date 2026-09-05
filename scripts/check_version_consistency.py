#!/usr/bin/env python3
"""S3.4: 版本声明一致性检查（白皮书 P5 漂移项）。

核对三处版本声明一致：
  1. pyproject.toml  [project].version
  2. ocos/__init__.py __version__
  3. requirements.lock 的 editable ocos 安装行

用法: python3 scripts/check_version_consistency.py   （一致退出码 0）
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def pyproject_version() -> str | None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return m.group(1) if m else None


def package_version() -> str | None:
    text = (ROOT / "ocos" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    return m.group(1) if m else None


def lock_version() -> str | None:
    lock = ROOT / "requirements.lock"
    if not lock.exists():
        return None
    for line in lock.read_text(encoding="utf-8").splitlines():
        # 形如: -e /path/to/ocos (ocos==0.2.0)
        m = re.search(r"\(ocos==([0-9.]+)\)", line)
        if m:
            return m.group(1)
    return None


def main() -> int:
    versions = {
        "pyproject.toml": pyproject_version(),
        "ocos/__init__.py": package_version(),
        "requirements.lock (editable)": lock_version(),
    }
    ok = True
    known = [v for v in versions.values() if v]
    for source, v in versions.items():
        status = "OK" if v and v == known[0] else ("MISSING" if not v else "MISMATCH")
        print(f"  [{status}] {source}: {v}")
        if status != "OK":
            ok = False
    if not ok:
        print("版本声明不一致 — 统一为 pyproject.toml 的版本后重跑。")
        return 1
    print(f"All version declarations consistent: {known[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
