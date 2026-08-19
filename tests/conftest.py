"""Phase14 测试基础配置 — 添加项目根到 sys.path 以便 import contracts/reality。"""
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
