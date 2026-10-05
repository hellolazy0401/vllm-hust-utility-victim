tar -xzf utility-victim-container-dev2.tar.gz
cd utility-victim-container-dev2

python -m pip install --no-index --find-links ./wheels --upgrade \
  vllm-hust-ext==0.2.0.dev0 vllm-hust-utility-victim==0.1.0.dev2

# 检查源码是否匹配
python scripts/apply_core_contract.py --core-root /vllm-workspace/vllm

# 匹配后应用补丁，自动保留备份
python scripts/apply_core_contract.py --core-root /vllm-workspace/vllm --apply

vllm-hust-ext extension enable org.vllm-hust.utility-victim
bash scripts/start_qwen35_utility.sh