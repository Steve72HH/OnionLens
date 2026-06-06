#!/usr/bin/env bash
set -euo pipefail

SERVICE="onionlens-workers_crawler"
STATS_URL="http://127.0.0.1:8000/stats"
LOG_FILE="/var/log/onionlens-autoscale.log"
STATE_FILE="/var/run/onionlens-autoscale.state"
LOCK_FILE="/var/run/onionlens-autoscale.lock"

MAX_SWARM=4
NORMAL_SWARM=2
MIN_SWARM=0

exec 9>"$LOCK_FILE"
flock -n 9 || exit 0

log() {
  echo "$(date -Is) $*" | tee -a "$LOG_FILE"
}

stats_json="$(curl -fsS --max-time 10 "$STATS_URL")"

read -r retry fetching queued sites < <(
  python3 -c '
import json, sys
d=json.load(sys.stdin)
f=d.get("frontier", {})
print(f.get("retry", 0), f.get("fetching", 0), f.get("queued", 0), d.get("sites", 0))
' <<< "$stats_json"
)

db_cpu_raw="$(docker stats --no-stream --format '{{.CPUPerc}}' onionlens-db 2>/dev/null | head -1 | tr -d '%')"
db_cpu="${db_cpu_raw:-0}"

current="$(docker service inspect "$SERVICE" --format '{{.Spec.Mode.Replicated.Replicas}}' 2>/dev/null || echo 0)"

green_count=0
hot_count=0
if [ -f "$STATE_FILE" ]; then
  # shellcheck disable=SC1090
  source "$STATE_FILE" || true
fi

target="$current"
reason="hold"

too_hot=$(python3 - <<PY
retry=$retry
db=float("$db_cpu")
print("1" if retry >= 1000 or db >= 350 else "0")
PY
)

warm=$(python3 - <<PY
retry=$retry
fetching=$fetching
db=float("$db_cpu")
print("1" if retry >= 400 or fetching >= 250 or db >= 180 else "0")
PY
)

green=$(python3 - <<PY
retry=$retry
fetching=$fetching
db=float("$db_cpu")
print("1" if retry < 50 and fetching < 180 and db < 80 else "0")
PY
)

if [ "$too_hot" = "1" ]; then
  hot_count=$((hot_count + 1))
  green_count=0

  if [ "$hot_count" -ge 2 ]; then
    target="$MIN_SWARM"
    reason="too_hot_confirmed"
  else
    target="$NORMAL_SWARM"
    reason="too_hot_wait"
  fi
elif [ "$warm" = "1" ]; then
  hot_count=0
  green_count=0
  target="$NORMAL_SWARM"
  reason="warm"
elif [ "$green" = "1" ]; then
  hot_count=0
  green_count=$((green_count + 1))

  if [ "$green_count" -ge 3 ]; then
    target="$MAX_SWARM"
    reason="green_boost"
  else
    target="$current"
    reason="green_wait"
  fi
else
  hot_count=0
  green_count=0
fi

if [ "$target" -gt "$MAX_SWARM" ]; then
  target="$MAX_SWARM"
fi

cat > "$STATE_FILE" <<STATE
green_count=$green_count
hot_count=$hot_count
STATE

log "sites=$sites queued=$queued retry=$retry fetching=$fetching db_cpu=${db_cpu}% current=$current target=$target reason=$reason green_count=$green_count hot_count=$hot_count"

if [ "$target" != "$current" ]; then
  docker service scale "$SERVICE=$target" >> "$LOG_FILE" 2>&1
  log "scaled $SERVICE from $current to $target"
fi
