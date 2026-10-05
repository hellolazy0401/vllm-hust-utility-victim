#!/usr/bin/env bash
# METADATA must describe the already-running server; this script does not start it.
set -euo pipefail
CLIENT=${1:?Usage: bash run_swe_ab.sh CLIENT WORKLOAD METADATA OUTDIR C SECONDS}
WORKLOAD=${2:?Missing prepared workload}
METADATA=${3:?Missing server metadata JSON}
OUT=${4:?Missing NEW output directory}
C=${5:?Missing concurrency}
SECONDS_TO_RUN=${6:?Missing duration}
[[ ! -e "$OUT" ]] || { echo "Output already exists: $OUT" >&2; exit 2; }
[[ -x "$CLIENT" && -f "$WORKLOAD" && -f "$METADATA" ]] || {
  echo 'Check client executable, workload, and metadata paths' >&2; exit 2;
}
curl -fsS --max-time 10 http://127.0.0.1:18180/health >/dev/null
mkdir -p "$OUT"
curl -fsS --max-time 10 http://127.0.0.1:18180/metrics > "$OUT/metrics.before.prom"
(
  while true; do
    date -u '+# snapshot %Y-%m-%dT%H:%M:%SZ'
    curl -fsS --max-time 10 http://127.0.0.1:18180/metrics || echo '# scrape_failed'
    sleep 5
  done
) > "$OUT/metrics.timeline.prom" 2> "$OUT/metrics.errors.log" &
POLL_PID=$!
cleanup() { kill "$POLL_PID" 2>/dev/null || true; wait "$POLL_PID" 2>/dev/null || true; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
set +e
"$CLIENT" run --workload "$WORKLOAD" \
  --endpoint http://127.0.0.1:18180/v1/completions \
  --model qwen3.5-35b-a3b --server-max-context 262144 \
  --concurrency "$C" --duration "$SECONDS_TO_RUN" --chips 2 \
  --seed 0 --timeout 1800 --server-metadata "$METADATA" \
  --output "$OUT/client" > "$OUT/client.log" 2>&1
CLIENT_STATUS=$?
set -e
# End snapshot includes draining; do not label its delta as window-only preemptions.
METRICS_STATUS=0
curl -fsS --max-time 10 http://127.0.0.1:18180/metrics \
  > "$OUT/metrics.after-drain.prom" || METRICS_STATUS=$?
printf 'client_exit=%s\nfinal_metrics_exit=%s\n' "$CLIENT_STATUS" "$METRICS_STATUS" > "$OUT/status.txt"
cat "$OUT/client.log"
if [[ "$CLIENT_STATUS" -ne 0 ]]; then exit "$CLIENT_STATUS"; fi
exit "$METRICS_STATUS"
