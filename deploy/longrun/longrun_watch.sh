#!/usr/bin/env bash
# 长跑采样器（升级方案 v1.0 §3.3 第三层 — 24h/7 天无人值守）。
#
# 每 INTERVAL 秒采样一次写入 $OCOS_LONGRUN_DIR/samples.jsonl：
#   {ts, daemon_pid, rss_kb, fd_count, heartbeat:{braked, autonomy_level, age}}
# 采样自 ~/.ocos/daemon_heartbeat.json 的 pid 定位 daemon 进程；
# 心跳缺失/进程消失照常记样（verify 阶段据原始数据判存活率）。
#
# 用法: longrun_watch.sh [INTERVAL_SEC] [DURATION_SEC]
#   默认 300s 采样、86400s（24h）时长。
# 长跑期不重启、不干预 — 只观测。verify_24h.sh 消费 samples 做门禁判定。
set -u

INTERVAL="${1:-300}"
DURATION="${2:-86400}"
LONGRUN_DIR="${OCOS_LONGRUN_DIR:-$HOME/.ocos/longrun}"
HEARTBEAT="${OCOS_HEARTBEAT_PATH:-$HOME/.ocos/daemon_heartbeat.json}"

mkdir -p "$LONGRUN_DIR"
SAMPLES="$LONGRUN_DIR/samples.jsonl"
END=$(( $(date +%s) + DURATION ))

echo "{\"event\":\"watch_start\",\"interval\":$INTERVAL,\"duration\":$DURATION,\"ts\":\"$(date -Iseconds)\"}" >> "$SAMPLES"

sample_once() {
    local pid="" rss_kb="" fd_count="" braked="" level="" hb_age=""
    local now_ts; now_ts=$(date +%s)

    if [ -f "$HEARTBEAT" ]; then
        pid=$(_json_field "$HEARTBEAT" pid)
        braked=$(_json_field "$HEARTBEAT" braked)
        level=$(_json_field "$HEARTBEAT" autonomy_level)
        local hb_ts; hb_ts=$(_json_field "$HEARTBEAT" ts)
        if [ -n "$hb_ts" ]; then
            hb_age=$(( now_ts - $(date -d "$hb_ts" +%s 2>/dev/null || echo 0) ))
        fi
    fi

    if [ -n "$pid" ] && [ -d "/proc/$pid" ]; then
        rss_kb=$(awk '/VmRSS/{print $2}' "/proc/$pid/status" 2>/dev/null)
        fd_count=$(ls "/proc/$pid/fd" 2>/dev/null | wc -l)
    fi

    printf '{"ts":"%s","daemon_pid":%s,"rss_kb":%s,"fd_count":%s,"braked":%s,"autonomy_level":%s,"heartbeat_age_sec":%s}\n' \
        "$(date -Iseconds)" "${pid:-null}" "${rss_kb:-null}" "${fd_count:-null}" \
        "${braked:-null}" "${level:-null}" "${hb_age:-null}" >> "$SAMPLES"
}

_json_field() {
    # 轻量 JSON 取字段（json 文件单层、字段名唯一 — 心跳文件即此形态）
    python3 - "$1" "$2" <<'PYEOF'
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
    v = data.get(sys.argv[2])
    if v is None:
        print("")
    elif isinstance(v, str):
        print(v)
    else:
        print(json.dumps(v))   # bool/number → 合法 JSON 字面量
except Exception:
    print("")
PYEOF
}

while [ "$(date +%s)" -lt "$END" ]; do
    sample_once
    sleep "$INTERVAL"
done
sample_once
echo "{\"event\":\"watch_end\",\"ts\":\"$(date -Iseconds)\"}" >> "$SAMPLES"
