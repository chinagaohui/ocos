"""OCOS CLI — autonomy 命令实现（L0-3: 自主行为总闸）。

用法:
    ocos autonomy          # 显示当前级别
    ocos autonomy 0        # 切换级别（写覆盖文件，daemon 下个 tick 即时生效+审计）
"""

from __future__ import annotations

from ocos.execution.autonomy import (
    LEVEL_DESCRIPTIONS, get_autonomy_level, set_autonomy_level)


def cmd_autonomy(args, session) -> int:
    """ocos autonomy [0-3] — 查看/切换自主级别。"""
    if getattr(args, "level", None) is None:
        lvl = get_autonomy_level()
        print(f"自主级别: LEVEL={lvl} [{LEVEL_DESCRIPTIONS.get(lvl, '?')}]")
        print("级别表:")
        for k, desc in LEVEL_DESCRIPTIONS.items():
            mark = "→" if k == lvl else " "
            print(f"  {mark} {k} = {desc}")
        print("切换: ocos autonomy <0-3>  （daemon 运行期即时生效，全程审计）")
        return 0
    try:
        lvl = set_autonomy_level(args.level)
    except ValueError as e:
        print(f"切换失败: {e}")
        return 1
    print(f"自主级别已切换: LEVEL={lvl} [{LEVEL_DESCRIPTIONS.get(lvl, '?')}]")
    print("  daemon 若在运行：下个 tick 自动检测并写入 audit episode；")
    print("  未运行：下次启动读取该级别。")
    return 0
