# Source 容器 0.23 适配（dev2）

## 根因与交付范围

读取 `D:/Desktop/mining/Source/vllm` 与 `vllm-ascend`。容器 Core 直接在 `schedule()` 中以 FCFS 尾部 / PRIORITY 最大值选人，无旧 Ascend selector、无正式 PreemptionPolicy。dev1 依赖的工厂在这份宿主中不存在。**dev2 wheel 本身不能补齐宿主接口，必须同时应用下面的最小 Core 补丁。**

Source 原件保持不变。`host_patch/core-0.23-victim-contract.patch` 是可审阅 diff，before/after 原件与 identity.json 记录完整哈希。补丁仅增加可选 selector 工厂与调用；算法留在 Mod。selector 未安装时沿用原始 FCFS / PRIORITY 分支。utility 任意选人时复用原 priority 分支的 token/encoder/speculative 预算回收，再调用原 `_preempt_request`。

这是本地实验契约 `hust_victim_selector_api_version=1`，不是上游正式 PreemptionPolicy v1；不得混称官方接口。相比原始“仅 wheel”交付，现在多了一项必要宿主前置补丁。

## 启用条件

- Python >=3.11；Core 与提供的 Source 快照严格匹配。
- 默认同步 Scheduler：启动加 `--no-async-scheduling`。
- 已核对的 Ascend BalanceScheduler 仅允许 balance 关闭、无 KV connector 时的转发路径。
- 不接纳 async、自定义 scheduler、speculative decoding、KV connector；这些路径会明确报错。
- 每次注册及 scheduler 构造时复核 Core 活体方法，检测 Ascend 后续 schedule 替换；检测未知 BalanceScheduler。
- 同时核对这份 Ascend 自带的 SWA `__init__` 包装器及其原函数，不因 `functools.wraps` 跳过代码检查。
- 模型 hybrid/Mamba 内存压力下的真实释放和恢复仍需 NPU 验证；CPU 选人和记账测试不能证明模型运行正确性。

## 容器操作

先停止之前的 vLLM 进程，再解压 dev2 离线包并进入目录：

```bash
python -m pip install --no-index --find-links ./wheels --upgrade \
  vllm-hust-ext==0.2.0.dev0 vllm-hust-utility-victim==0.1.0.dev2

# 只读检查，应显示 COMPATIBLE, NOT PATCHED
python scripts/apply_core_contract.py --core-root /vllm-workspace/vllm

# 显式应用，自动创建 scheduler.py.utility-victim.bak
python scripts/apply_core_contract.py --core-root /vllm-workspace/vllm --apply

export VLLM_HUST_UTILITY_VICTIM_BACKEND=core-contract-v1
export VLLM_HUST_UTILITY_VICTIM_KILL_SWITCH=0
export VLLM_HUST_UTILITY_VICTIM_EVIDENCE=1
export VLLM_ASCEND_BALANCE_SCHEDULING=0
vllm-hust-ext extension enable org.vllm-hust.utility-victim
```

原启动命令的开头换为 `vllm-hust-ext run -- vllm serve`，再加 `--no-async-scheduling`；其余模型和资源参数按实际环境设置。可用 `scripts/start_qwen35_utility.sh`，它沿用用户粘贴的 262144 上下文等参数，**这些参数未在 NPU 验证可启动或可容纳**。

首次进入 utility 选人会记录 `runtime_effective`。只看到 `installed` 不代表抢占实际发生；没有缓存压力时可能始终不触发。

## 回滚

停止服务后：

```bash
export VLLM_HUST_UTILITY_VICTIM_KILL_SWITCH=1
vllm-hust-ext extension disable org.vllm-hust.utility-victim
python scripts/apply_core_contract.py --core-root /vllm-workspace/vllm --restore
```

恢复会验证已打补丁文件和原备份哈希，不覆盖另行修改的文件。补丁脚本默认只检查，不写入；Source 与容器文件若不同会拒绝应用。不要跳过哈希守卫。

## 证据

`tests/test_core_contract.py` 编译/执行真实补丁中的选人分支，检查 OFF 等价性、已调度请求的预算回收、非法 victim 拒绝、后续 monkey patch 拒绝、同步限制、真实 Ascend wrapper 准入以及 patch/restore 往返。它没有执行全量 scheduler 依赖或 NPU 服务。

还覆盖“抢占循环游标之前、但本轮没有调度 token 的请求”的游标修正，避免删除后跳过后续请求。Windows Python 3.12 当前为 48 passed；WSL Python 3.11 的结果保存在交付日志中。Source 原件不因测试或生成补丁被修改。

历史算法来源仍为 Ascend #39；当前宿主契约是此次适配新增的 glue，不是 #39 原始提交，也不改变其来源映射。旧文档的“当前已有内建等价算法”只适用于先前 vllm-hust/ 子目录，不适用于这次 Source 容器快照。
