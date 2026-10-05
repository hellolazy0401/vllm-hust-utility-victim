ARM=off
C=2
R=2
NAME="${ARM}-m65-c${C}-r${R}"

# 按容器的实际逻辑卡号设置
export ASCEND_RT_VISIBLE_DEVICES=0,1

KV_MEMORY_FRACTION=0.65 \
  bash "$MOD/scripts/start_swe_ab.sh" "$ARM" "$MODEL_PATH" \
  2>&1 | tee "$BENCH/results/$CAMPAIGN/${NAME}.server.log"