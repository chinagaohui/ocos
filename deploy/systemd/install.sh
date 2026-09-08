#!/usr/bin/env bash
# L0-4: OCOS systemd 用户服务一键部署（新机一条命令部署三服务中的 OCOS 两件；
# hermes-gateway 属独立项目，如已配置见其自身安装方式）。
#
# 用法:
#   bash deploy/systemd/install.sh            # 自动探测项目与 venv 路径
#   PROJECT_DIR=... VENV_DIR=... bash deploy/systemd/install.sh
#
# 行为:
#   1. 渲染 deploy/systemd/user/*.service 的 @PROJECT_DIR@/@VENV_*@ 占位符
#   2. 安装到 ~/.config/systemd/user/
#   3. systemctl --user daemon-reload && enable --now
#   4. 健康检查: is-active + API 端口 8900 就绪探测
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
VENV_DIR="${VENV_DIR:-$PROJECT_DIR/.venv}"
VENV_PY="$VENV_DIR/bin/python"
VENV_BIN="$VENV_DIR/bin"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
API_PORT="${API_PORT:-8900}"

if [ ! -x "$VENV_PY" ]; then
  echo "错误: 未找到 venv python: $VENV_PY （可用 VENV_DIR=... 指定）" >&2
  exit 1
fi

echo "项目目录 : $PROJECT_DIR"
echo "venv     : $VENV_DIR"
mkdir -p "$SYSTEMD_USER_DIR"

for unit in ocos-daemon.service ocos-server.service; do
  sed -e "s|@PROJECT_DIR@|$PROJECT_DIR|g" \
      -e "s|@VENV_PY@|$VENV_PY|g" \
      -e "s|@VENV_BIN@|$VENV_BIN|g" \
      "$SCRIPT_DIR/user/$unit" > "$SYSTEMD_USER_DIR/$unit"
  echo "已安装   : $SYSTEMD_USER_DIR/$unit"
done

systemctl --user daemon-reload
# 重启顺序（项目约定）: server → daemon（daemon 重连新 API server）
systemctl --user enable --now ocos-server.service
systemctl --user enable --now ocos-daemon.service

# 健康检查
fail=0
for unit in ocos-server.service ocos-daemon.service; do
  if systemctl --user is-active --quiet "$unit"; then
    echo "✓ $unit active"
  else
    echo "✗ $unit 未处于 active — 查看日志: journalctl --user -u $unit -n 50" >&2
    fail=1
  fi
done

# API 端口就绪探测（最多 15s）
for _ in $(seq 1 15); do
  if (exec 3<>"/dev/tcp/127.0.0.1/$API_PORT") 2>/dev/null; then
    exec 3>&- 3<&- || true
    echo "✓ API 端口 $API_PORT 就绪"
    break
  fi
  sleep 1
done

if [ "$fail" -ne 0 ]; then
  exit 1
fi
echo "OCOS 服务部署完成。"
