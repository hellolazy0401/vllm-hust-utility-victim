#!/usr/bin/env bash
set -euo pipefail
export VLLM_HUST_UTILITY_VICTIM_BACKEND=core-contract-v1
export VLLM_HUST_UTILITY_VICTIM_KILL_SWITCH=0
export VLLM_HUST_UTILITY_VICTIM_EVIDENCE=1
export VLLM_ASCEND_BALANCE_SCHEDULING=0
exec vllm-hust-ext run -- vllm serve /models/Qwen3.5-35B-A3B \
  --served-model-name qwen3.5-35b-a3b \
  --host 127.0.0.1 --port 18180 \
  --dtype bfloat16 --kv-cache-dtype auto --block-size 128 \
  --tensor-parallel-size 2 --enable-expert-parallel \
  --pipeline-parallel-size 1 --data-parallel-size 1 \
  --max-model-len 262144 --gpu-memory-utilization 0.85 \
  --max-num-seqs 16 --max-num-batched-tokens 8192 \
  --no-enable-prefix-caching --enable-chunked-prefill --no-enforce-eager \
  --no-async-scheduling --seed 0 --scheduling-policy fcfs \
  --distributed-executor-backend mp --disable-custom-all-reduce \
  --no-trust-remote-code --load-format auto \
  --no-enable-log-requests --uvicorn-log-level info \
  --compilation-config '{"mode":3,"cudagraph_mode":"FULL_DECODE_ONLY"}' \
  --cudagraph-capture-sizes 1 2 4 8 16
