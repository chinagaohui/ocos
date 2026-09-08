#!/usr/bin/env bash
# 长跑终验门禁（升级方案 v1.0 §3.3 第三层 24h 段验收）。
#
# 门禁项（任何一项不过 → exit 2，全过 → PASS）:
#   G1 存活: 采样存在且尾段心跳新鲜（age ≤ 3×INTERVAL），
#      systemd 单元 active（无 systemd 环境降级为心跳判活）
#   G2 无未处理异常: journal 窗口内 ocos-daemon 零 Traceback
#   G3 内存无泄漏: 尾段 RSS ≤ max(首段×1.3, 首段+200MB)
#   G4 句柄无泄漏: 尾段 fd ≤ 首段×1.5 + 20
#   G5 体征阈值: ocos vitals --check（PHASE 可指定，默认 L4）
#
# 用法: verify_24h.sh [SAMPLES_JSONL] [JOURNAL_SINCE]
#   默认 samples: $OCOS_LONGRUN_DIR/samples.jsonl；journal 窗口: -24 hours
set -u

SAMPLES="${1:-${OCOS_LONGRUN_DIR:-$HOME/.ocos/longrun}/samples.jsonl}"
JOURNAL_SINCE="${2:--24 hours}"
PHASE="${OCOS_LONGRUN_PHASE:-L4}"
UNIT="${OCOS_DAEMON_UNIT:-ocos-daemon}"

fail=0
note() { printf '%s\n' "$*"; }
gate_fail() { printf '✗ %s\n' "$*"; fail=1; }
gate_pass() { printf '✓ %s\n' "$*"; }

# ── G1 存活 ──────────────────────────────────────────────────────────────
if [ ! -f "$SAMPLES" ]; then
    gate_fail "G1 存活: 无采样文件 $SAMPLES（watcher 未运行?）"
else
    total=$(grep -c '"daemon_pid"' "$SAMPLES" || true)
    last_hb_age=$(grep '"daemon_pid"' "$SAMPLES" | tail -1 \
        | python3 -c 'import json,sys
v = json.loads(sys.stdin.read()).get("heartbeat_age_sec")
print(99999 if v is None else v)' 2>/dev/null || echo 99999)
    interval=$(grep -o '"interval":[0-9]*' "$SAMPLES" | head -1 | cut -d: -f2)
    [ -n "$interval" ] || interval=300
    if [ "$total" -lt 2 ]; then
        gate_fail "G1 存活: 有效采样仅 $total 条"
    elif [ "$last_hb_age" -le $(( interval * 3 )) ]; then
        gate_pass "G1 存活: $total 条采样，尾段心跳 age=${last_hb_age}s"
    else
        gate_fail "G1 存活: 尾段心跳 age=${last_hb_age}s > 3×INTERVAL=${interval}s"
    fi
    if command -v systemctl >/dev/null 2>&1; then
        if systemctl --user is-active --quiet "$UNIT" 2>/dev/null; then
            gate_pass "G1 存活: systemd $UNIT active"
        elif [ "$fail" -eq 0 ]; then
            gate_fail "G1 存活: systemd $UNIT 非 active（ Restart=on-failure 被触发? 查 journalctl --user -u $UNIT）"
        fi
    fi
fi

# ── G2 无未处理异常 ─────────────────────────────────────────────────────
if command -v journalctl >/dev/null 2>&1; then
    tb=$(journalctl --user -u "$UNIT" --since "$JOURNAL_SINCE" 2>/dev/null \
        | grep -c "Traceback (most recent call last)" || true)
    if [ "$tb" -eq 0 ]; then
        gate_pass "G2 异常: journal 窗口内零 Traceback"
    else
        gate_fail "G2 异常: journal 窗口内 $tb 处 Traceback（journalctl --user -u $UNIT --since \"$JOURNAL_SINCE\" | grep -A5 Traceback）"
    fi
else
    note "△ G2 异常: 无 journalctl — 跳过（人工核对日志）"
fi

# ── G3/G4 资源泄漏 ──────────────────────────────────────────────────────
python3 - "$SAMPLES" <<'PYEOF'
import json, sys, os

def note(msg): print(msg)
failed = False
path = sys.argv[1]
rows = []
try:
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("{") and '"rss_kb"' in line:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("rss_kb") is not None:
                    rows.append(r)
except FileNotFoundError:
    note("✗ G3/G4 泄漏: 无采样文件")
    sys.exit(2)
if len(rows) < 2:
    note("✗ G3/G4 泄漏: 有效 RSS 采样不足 2 条")
    sys.exit(2)
first, last = rows[0], rows[-1]
rss0, rss1 = int(first["rss_kb"]), int(last["rss_kb"])
budget = max(int(rss0 * 1.3), rss0 + 200 * 1024)
if rss1 <= budget:
    note(f"✓ G3 内存: RSS {rss0//1024}MB → {rss1//1024}MB（预算 {budget//1024}MB）")
else:
    note(f"✗ G3 内存: RSS {rss0//1024}MB → {rss1//1024}MB 超预算 {budget//1024}MB")
    failed = True
fd0 = first.get("fd_count"); fd1 = last.get("fd_count")
if fd0 is not None and fd1 is not None:
    fd_budget = int(fd0) * 1.5 + 20
    if int(fd1) <= fd_budget:
        note(f"✓ G4 句柄: fd {fd0} → {fd1}（预算 {fd_budget:.0f}）")
    else:
        note(f"✗ G4 句柄: fd {fd0} → {fd1} 超预算 {fd_budget:.0f}")
        failed = True
else:
    note("△ G4 句柄: 采样缺 fd 数据 — 跳过")
sys.exit(2 if failed else 0)
PYEOF
[ $? -ne 0 ] && fail=1

# ── G5 体征阈值 ─────────────────────────────────────────────────────────
if python3 -m ocos.interaction.cli.main vitals --check --phase "$PHASE" >/tmp/vitals_check_out.$$ 2>&1; then
    gate_pass "G5 体征: vitals --check --phase $PHASE 达标"
else
    gate_fail "G5 体征: vitals --check 未达标（PHASE=$PHASE）— $(cat /tmp/vitals_check_out.$$ | tail -5)"
fi
rm -f /tmp/vitals_check_out.$$

if [ "$fail" -eq 0 ]; then
    echo "PASS — 24h 长跑门禁全过"
    exit 0
fi
echo "FAIL — 长跑门禁存在未过项（见上）"
exit 2
