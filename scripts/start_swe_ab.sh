#!/usr/bin/env bash
# Use the serving Python environment, not the benchmark client venv.
set -euo pipefail
MODE=${1:?Usage: bash start_swe_ab.sh off|on /absolute/model/path}
MODEL_PATH=${2:?Missing model directory}
case "$MODE" in
  off) export VLLM_HUST_UTILITY_VICTIM_KILL_SWITCH=1 ;;
  on) export VLLM_HUST_UTILITY_VICTIM_KILL_SWITCH=0 ;;
  *) echo 'Mode must be off or on' >&2; exit 2 ;;
esac
[[ -d "$MODEL_PATH" ]] || { echo "Model directory missing: $MODEL_PATH" >&2; exit 2; }
export VLLM_HUST_UTILITY_VICTIM_ENABLE=1
export VLLM_HUST_UTILITY_VICTIM_BACKEND=core-contract-v1
export VLLM_HUST_UTILITY_VICTIM_EVIDENCE=1
export VLLM_ASCEND_BALANCE_SCHEDULING=0
# If adjusted for a pressure pilot, use exactly the same value in BOTH groups.
KV_MEMORY_FRACTION=${KV_MEMORY_FRACTION:-0.85}
printf 'SWE_AB mode=%s kill_switch=%s memory_fraction=%s model=%s\n' \
  "$MODE" "$VLLM_HUST_UTILITY_VICTIM_KILL_SWITCH" "$KV_MEMORY_FRACTION" "$MODEL_PATH" >&2
CMD=(vllm-hust-ext run -- vllm serve "$MODEL_PATH"
  --served-model-name qwen3.5-35b-a3b --host 127.0.0.1 --port 18180
  --dtype bfloat16 --kv-cache-dtype auto --block-size 128
  --tensor-parallel-size 2 --enable-expert-parallel
  --pipeline-parallel-size 1 --data-parallel-size 1
  --max-model-len 262144 --gpu-memory-utilization "$KV_MEMORY_FRACTION"
  --max-num-seqs 16 --max-num-batched-tokens 8192
  --no-enable-prefix-caching --enable-chunked-prefill --no-enforce-eager
  --no-async-scheduling --seed 0 --scheduling-policy fcfs
  --distributed-executor-backend mp --disable-custom-all-reduce
  --no-trust-remote-code --load-format auto
  --no-enable-log-requests --uvicorn-log-level info
  --compilation-config '{"mode":3,"cudagraph_mode":"FULL_DECODE_ONLY"}'
  --cudagraph-capture-sizes 1 2 4 8 16)
printf 'SWE_AB command:' >&2
printf ' %q' "${CMD[@]}" >&2
printf '\n' >&2
exec "${CMD[@]}"
