#!/usr/bin/env python3
"""OCOS CLI — ocos 命令入口脚本。

安装后可通过 `ocos` 命令直接调用。
开发阶段: python3 -m ocos.interaction.cli.main
"""

import sys
from ocos.interaction.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
