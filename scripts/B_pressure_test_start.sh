# 设置同一实验点
ARM=off
C=2
R=2
NAME="${ARM}-m65-c${C}-r${R}"

CLIENT="$BENCH/.venv-bench/bin/swe-prefix-reuse"
OUT="$BENCH/results/$CAMPAIGN"
META="$BENCH/evidence/$CAMPAIGN/server-metadata-${ARM}.json"

# 短预检
"$CLIENT" run \
  --workload "$BENCH/prepared/qwen35.json" \
  --endpoint http://127.0.0.1:18180/v1/completions \
  --model qwen3.5-35b-a3b \
  --server-max-context 262144 \
  --concurrency "$C" --duration 20 --chips 2 --seed 0 \
  --server-metadata "$META" \
  --output "$OUT/${NAME}-probe"

# 采集运行前证据
npu-smi info > "$OUT/${NAME}.hardware.txt"

curl -fsS http://127.0.0.1:18180/metrics \
  > "$OUT/${NAME}.before.prom"

# 正式压测
  "$CLIENT" run \
  --workload "$BENCH/prepared/qwen35.json" \
  --endpoint http://127.0.0.1:18180/v1/completions \
  --model qwen3.5-35b-a3b \
  --server-max-context 262144 \
  --concurrency "$C" --duration 900 --chips 2 --seed 0 \
  --server-metadata "$META" \
  --output "$OUT/$NAME"

RUN_EXIT=$?
printf '%s\n' "$RUN_EXIT" > "$OUT/${NAME}.exit-code.txt"

curl -fsS http://127.0.0.1:18180/metrics \
  > "$OUT/${NAME}.after.prom"

# 快速检查单点
python -m json.tool "$OUT/$NAME/summary.json"

grep -E 'LEGACY017_EVIDENCE.*(installed|runtime_effective)' \
  "$OUT/${NAME}.server.log"

grep '^vllm:num_preemptions_total{' \
  "$OUT/${NAME}.before.prom" \
  "$OUT/${NAME}.after.prom"

sha256sum "$OUT/$NAME/requests.jsonl"