"""OCOS TUI 入口

Usage:
    python -m ocos.interaction.tui
"""

from ocos.interaction.tui import OCOSTUI


def main():
    app = OCOSTUI()
    app.run()


if __name__ == "__main__":
    main()
