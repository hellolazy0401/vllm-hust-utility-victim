# vllm-hust-utility-victim 项目报告

> 日期：2026-10-05（Asia/Shanghai）  
> 对象：Qwen3.5-35B-A3B，2 × Ascend 910B2，TP2 + 专家并行，vLLM `0.23.0+empty` / vLLM-Ascend `0.23.0.post1`，Mod `0.1.0.dev2`。Ascend 版本依据 r1 ON 的 versions.txt，不沿用早期口述的 0.23.0。  
> 状态：候选（candidate），已完成打包、CPU 验证及 r1 真机机制可达性验证，**未通过性能准入**。  
> 范围：按用户要求，只分析 `off-m65-c16-r1` 与 `on-m65-c16-r1`；r2、r3 不纳入数据、统计和结论。采用 EPLB 项目报告的结构，不继承其性能数据或验收结果。
> 本次重生成依据：`evidence/` 的来源/构建/测试原件，以及 `results/` 的 r1 请求明细、配置、汇总、服务日志和监控快照。旧实验笔记、Excel 汇总不作为覆盖原始记录的依据。

---

## 0. 摘要

这是将历史 Ascend #39 的 utility victim selection 抽取为独立 Python Mod 的项目。在宿主已经决定需要抢占时，Mod 改变被抢占请求的选择；实际释放、重算和恢复仍由宿主执行。

| 问题 | 当前结论 |
|---|---|
| 机制是否运行 | 是。r1 ON 的 EngineCore 报告一次首次 `runtime_effective`，`selection_changed=true`；宿主抢占计数增加 188 |
| 吞吐是否提升 | 否。r1 两卡合计 172.52 → 147.00 tok/s，下降 **14.79%** |
| 首 token 延迟 | TTFT P95 9.829 → 5.973 秒，下降 **39.23%**；仅一次对照，不声称稳定收益 |
| 解码与完成延迟 | TPOT 均值增加 **20.33%**，P95 增加 **86.46%**；E2E P95 增加 **3.97%** |
| 抢占次数 | 整轮含 drain：311 → 188，减少 **39.55%**；不能据此断言重算成本或真实 KV 释放量减少 |
| 项目价值 | 可追溯的单机制抽取、严格宿主适配及消融实验；当前数据不支持作为吞吐优化推广 |
| 未完成 | 重复实验、无触发负例、真实释放/重算/公平性观测、远程发布记录和正式性能准入 |

本报告区分“机制确实参与决策”与“机制提升性能”。r1 表现为吞吐及解码延迟损失与 TTFT 改善并存，不能用某一个好指标覆盖其他代价。

### 0.1 证据分层与取舍

| 证据层 | 实际文件（相对项目根目录） | 能证明什么 / 不能证明什么 |
|---|---|---|
| 来源原件 | `evidence/vllm-ascend-hust-legacy-20260831-pr-39.json`、对应 `-files.json`、`ascend-pr39-victim_selector.py` | 固定历史算法与 PR 身份；不代表当前容器代码 |
| 相关接口与去重 | `evidence/vllm-hust-legacy-20260831-pr-171*.json`、`bidkv-reference.json`、`bidkv-selector-reference.py` | 区分历史算法、接口、后续 BidKV 路线；不是本实验成绩 |
| 历史本地验证 | `evidence/pytest.txt`、`pytest-linux-dev1.txt`、`pytest-linux-dev2.txt`、`ruff.txt` | 对应版本的 CPU/静态检查；不证明真机性能 |
| 构建与隔离安装 | `evidence/build.txt`、`wheel-install.txt` | 初始版本的构建/安装记录；不能冒充 dev2 新构建日志 |
| r1 实验定义 | 两组 `results/*-m65-c16-r1/config.json`、同名前缀 `.server.log` | 客户端负载身份和服务实际启动参数 |
| r1 请求原件 | 两组 `results/*-m65-c16-r1/requests.jsonl` | 重算窗口 tokens、延迟、覆盖；无 victim ID 对应，不足以归因重算成本 |
| r1 服务监控 | 两组 `.before.prom`、`.after.prom` | 含 drain 的计数差；不能恢复瞬时峰值和每次抢占细节 |
| r1 环境 | `results/on-m65-c16-r1.versions.txt`、`.hardware.txt` | ON 的版本/设备快照；OFF 缺失对应文件，不能借用其他轮次补填 |
| 协议预检 | `results/off-smoke/` | 60 秒 C1 基本协议通过；不纳入 r1 性能对照 |

`results/` 虽保留其他轮次和三次实验汇总表，本报告仍只使用 r1。文件存在不等于用户已确认该轮完成，尤其不以 r2/r3 补足重复次数。

## 1. 来源

| 项 | 内容 |
|---|---|
| 原 PR | `intellistream/vllm-ascend-hust-legacy-20260831` Ascend #39，标题 `Feat/bidkv victim selector item1 2` |
| 作者 | 本地归档 PR 元数据中的 `cybber695` |
| 提交日期 |  |
| merge commit | `76d8939d7e21d17a295adf99e9dda17bde5a88cc` |
| 原文件 | `vllm_ascend/core/victim_selector.py`；完整原件保存在 `evidence/ascend-pr39-victim_selector.py` |
| 用户清单 | 《调度_Prefix_Routing与抢占机制清单》第 6 条 |
| 相关接口 PR | Core #171，`5536d0873fb41c4925d0e6e9112a1ea70faeeb3a`；不是本包算法来源 |
| 历史 Core 上下文 | `1aa7cd10b7b16e82fdb29fcc47d3a3cd93bd01dc`；不是声称与 #39 合并时配套的 commit |
| 对应关系 | `docs/MAPPING.md`、`mapping.json`、`mapping.csv`；`LOCAL-UV-*` 为本地证据编号 |

以上身份取自本地已保存的 PR 元数据、源码及映射文件。本次未重新查询远程状态。

## 2. 基础改造思路

### 2.1 原机制做什么

候选来自正在运行的请求。在通过 KV 门槛、冷却时间和最少运行请求等门控后，以近似公式排序：

```text
U = max(computed_tokens, 0)
    / max(1 + 0.5 × completion + 0.3 × num_preemptions + epsilon, epsilon)
completion = 已输出 tokens / max_tokens，限制到 [0,1]
epsilon = 1e-6
```

选择 U 最大的请求；相同分数按到达时间、请求 ID 确定次序。其思想是优先释放较大的 token 占用，同时对接近完成、已被多次抢占的请求降低选择倾向。这里 computed_tokens 只是释放收益代理，不是实际 KV 字节数，也没有扣除再次计算这些 tokens 的真实成本。

### 2.2 如何抽取与接入

1. `historical.py` 保留历史公式、门控、排序和统计；移除对 vLLM 类型的强依赖，CPU 可独立测试。
2. `selector.py` 增加配置合法性、冲突检查及首次运行证据，不复制宿主抢占执行链。
3. `plugin.py` 提供默认关闭、kill 优先、幂等注册、源码指纹守卫。
4. 最早的 `ascend-legacy` 后端替换已有 selector 工厂；旧本地 Ascend 已内建等价算法，不能称为新增优化。
5. 用户容器的 Source 快照缺少该工厂，dev2 增加 **必要的最小 Core contract 补丁** 与 `core_adapter.py`。算法留在 Mod，补丁只提供工厂和选人调用，并处理任意 victim 删除后的游标与预算回收。
6. 当前 r1 使用 `core-contract-v1`，同步调度；拒绝未知源码、async、自定义不兼容 scheduler、speculative decoding、KV connector 等未适配路径。该接口是本地实验契约，不是上游正式 PreemptionPolicy v1。
7. OFF 和 ON 都安装同一宿主补丁，ENABLE 均为 1，仅 KILL_SWITCH 分别为 1/0。OFF 沿用宿主原有选人分支；不是与完全未修改的上游源码对照。

本包 manifest 的 activation 会在 `vllm-hust-ext run -- ...` 下注入 ENABLE=1。不能照搬 EPLB 模板里“enable 后环境仍为 0”的结论；单独修改管理器状态也不会改变已经运行的服务。

### 2.3 是否符合挑选原则

| 原则 | 判定 |
|---|---|
| 单机制 | 满足：仅 utility 选人与必需接入，不包含 Prefix Routing、EPLB 或其他优化 |
| 不依赖台账运行 | 满足：运行算法随包交付，不 import 台账仓库 |
| 来源可追溯 | 满足：PR、固定 SHA、原件、映射均保留 |
| 独立 PyPI 结构 | 满足打包结构；**当前容器不能仅装 wheel 就接入，仍依赖 Core 补丁** |
| 宿主适配边界 | 有条件满足：严格源码守卫的实验适配，需要维护；不能称通用稳定插件 |
| 新增性能价值 | 未通过：r1 吞吐下降；不将抽取成功当作性能成功 |

正式 BidKV 已有不同契约及更多保护逻辑，本包不宣称实现其 liveness/cascade 保护，也不另算一条正式 BidKV 产品线。

## 3. 验证与成绩

### 3.1 CPU 与打包验证

| 原始记录 | 直接记录的结果 | 版本与边界 |
|---|---|---|
| `evidence/pytest.txt` | 35 passed，1.35 秒 | 初始 CPU 验证，不能写成当前 dev2 的测试数 |
| `evidence/pytest-linux-dev1.txt` | 37 passed，1 skipped，0.97 秒 | dev1 Linux；不是 NPU 推理测试 |
| `evidence/pytest-linux-dev2.txt` | 47 passed，1 skipped，3.83 秒 | dev2 Linux；可选管理器环境检查未执行 |
| `evidence/ruff.txt` | All checks passed | 保存时的静态检查，不是本次完整代码重新 lint |
| `evidence/build.txt` | 成功生成 wheel 与 sdist | 日志明确为 **0.1.0.dev0**，不是 dev2 |
| `evidence/wheel-install.txt` | version、双入口、manifest、fingerprint、默认关闭导入 PASS | 历史隔离安装自检；不是性能证明 |

另有本次报告前一次本地复核（2026-10-05）：`python -m pytest tests -q` **48 passed**。它是当前会话执行结果，不改写上述旧日志来冒充当时测试。

- 历史算法差分覆盖 2 policies × 6 configurations × 100 决策，共 1,200 次，核对 victim、metrics 和 snapshots。
- Core contract 单测覆盖 OFF 行为、预算回收、游标修正、非法 victim、未知源码拒绝及 patch/restore 往返。它没有执行完整 NPU scheduler。
- 已有 wheel、sdist、双 entry points、manifest 和离线安装交付；这不等于已经上传 PyPI。

协议预检原件显示：C1、60 秒，6 个请求开始、5 个窗口内完成、1 个 drain，valid=true、0 失败，最大 prompt 6628 tokens。这证明基本 token 协议通过，不将其低并发分数与 r1 C16 比较。

### 3.2 r1 真机可达性

OFF 日志中 installed/runtime_effective 均为 0。ON 原始日志中有 **4 条 installed、1 条 runtime_effective**，不是旧实验表格填写的 3 条 installed。installed 多条不代表四个调度器或四次优化。

ON 首次运行事件由 `EngineCore pid=325044` 输出：

```json
{"actual_kv_freed_verified":false,"mechanism":"ascend-utility-victim","scope":"victim_selection_only","selection_changed":true,"tokens_proxy":41308}
```

这证明至少一次 utility 选择与 fallback 不同。每个 selector 仅报告首次事件，不能统计全部选择次数或全部差异。`41308` 不可当作实际释放字节或全部节省量。

### 3.3 组件基准

尚未做独立 selector 耗时微基准，不能给出函数加速倍数。此机制主要改变抢占对象，不是通过减少排序耗时获得收益；CPU 选人更快也不能代替服务指标。

### 3.4 swe-prefix-reuse r1

**设置：** C16，900 秒窗口，2 芯片，BF16，TP2/EP，DP1，max-model-len=262144，max-num-seqs=16，chunk=8192，同步 FCFS，prefix caching 关闭，未配置 MTP。两组均 `gpu-memory-utilization=0.65`，日志报告可用 KV memory 约 4.55 GiB、cache size 460,252 tokens。0.65 是本次压力实验值，不是所有部署的推荐值。

工具版本 0.1.2。两组配置记录相同 prepared SHA256 与 tokenizer fingerprint（第 9 节）。均 valid、0 失败；valid 只证明工具协议/形状检查通过，不证明回答语义正确。

| 指标 | OFF-r1 | ON-r1 | ON 相对 OFF |
|---|---:|---:|---:|
| 窗口内完成请求 | 319 | 288 | -9.72% |
| 两卡合计输出 tok/s | 172.520 | 146.997 | **-14.79%** |
| 每卡输出 tok/s | 86.260 | 73.498 | **-14.79%** |
| decode speed P90，tok/s | 19.119 | 19.158 | +0.21% |
| TTFT P50，ms | 1520.99 | 1369.73 | -9.94% |
| TTFT P95，ms | 9829.22 | 5973.18 | **-39.23%** |
| TPOT 均值，ms | 82.15 | 98.85 | **+20.33%** |
| TPOT P95，ms | 153.90 | 286.97 | **+86.46%** |
| E2E P95，ms | 112872.77 | 117356.59 | +3.97% |
| 抢占计数增量，含 drain | 311 | 188 | -39.55% |
| 完整会话完成数，含 drain | 6 | 4 | — |
| 实际最大 prompt tokens | 40244 | 40244 | — |
| prompt tokens 中位数 | 13086 | 11911.5 | 负载进度混合不同 |
| 最大 turn index | 29 | 29 | — |
| full client concurrency 占比 | 99.886% | 99.904% | — |
| drain，秒 | 160.36 | 153.77 | 不计入吞吐分母 |

吞吐、decode P90、TTFT P95 来自原始 summary；TTFT P50、TPOT、E2E 从窗口内成功完成的 requests.jsonl 重算，分别 319/288 条，并与原始汇总计数对账。TPOT 使用 `(E2E−TTFT)/(N−1)`，不是 P90 decode speed 的倒数。统计程序和机器可读结果随报告交付。

### 3.5 解读与限定

1. 当前单对实验出现明确的数值取舍：首 token 更快、抢占次数更少，但吞吐更低、TPOT 更差。不能报告“整体提升”。
2. decode speed P90 描述较快一端的请求速度，不代表慢请求的尾部行为；它近似持平与 TPOT P95 变差不矛盾。
3. 抢占对象的大小和重算代价可能不同，因此次数减少不等于成本减少。**这只是可能解释，尚无逐次重算/释放观测证明根因。**
4. 两组完成会话数和 prompt 中位数不同；虽然输入文件相同，固定窗口内实际覆盖的轮次混合并不相同。
5. 只有一对结果，没有同组重复波动或置信区间，不能定量证明稳定退化/提升，更不能推广到其他硬件和流量。
6. 配置允许 256K，但实际 prompt 最大只有 40,244 tokens；不能称完成了 256K 满上下文压力验证。

### 3.6 服务端监控与客户端原件交叉核验

两组 before/after 的 `process_start_time_seconds` 分别保持不变，降低了取到另一个 API 服务进程快照的疑虑；这不能单独证明内部所有 worker 从未重启。监控值按相同实验前后差计算：

| 项目 | OFF-r1 | ON-r1 | 客户端核对 |
|---|---:|---:|---|
| 成功请求数（含 drain） | 335 | 304 | 分别等于 requests.jsonl 行数；319+16、288+16 |
| prompt tokens（含 drain） | 4,748,411 | 4,087,683 | 分别等于所有请求的 prompt_tokens 之和 |
| generation tokens（含 drain） | 184,619 | 149,024 | 分别等于所有请求实际 token_ids 数之和 |
| 窗口内收到的输出 tokens | 155,268 | 132,297 | 按每个 chunk 的时间重算，与 summary 一致 |
| 抢占计数 | 0 → 311 | 0 → 188 | 宿主计数，不能由 installed/runtime 日志条数代替 |
| prefix cache queries / hits 增量 | 0 / 0 | 0 / 0 | 与两组关闭 prefix caching 的参数一致 |
| KV usage 快照 | 0 → 0 | 0 → 0 | 首尾空闲快照不表示运行中无压力；实际抢占已发生 |

上述 prompt 总数是请求输入统计，不能当作包括所有重算在内的计算量。generation 全程总量包含 drain，也不能直接除以 900 后冒充窗口吞吐。

按 requests.jsonl 的 chunk 时间，每 150 秒窗口的输出 tokens 如下。这是描述同一条运行轨迹，不是六次独立重复：

| 时间窗（秒） | OFF-r1 | ON-r1 |
|---|---:|---:|
| 0–150 | 31,647 | 31,616 |
| 150–300 | 35,057 | 35,065 |
| 300–450 | 28,474 | 24,277 |
| 450–600 | 16,476 | 12,515 |
| 600–750 | 22,965 | 9,454 |
| 750–900 | 20,649 | 19,370 |

前 300 秒两组输出量近似，后续窗口出现差距。这支持进一步检查长会话演进后的请求混合、抢占与重算代价；没有逐次事件时间对齐，不能断言差距从某次 utility 选择开始，更不能从此表直接推出因果。

## 4. 优势

1. 单机制来源清楚，历史算法与新接入层分离，便于审阅和消融。
2. 无需 NPU 即可运行历史差分和宿主适配测试。
3. 默认关闭、kill 优先、严格源码守卫，支持宿主补丁显式恢复。
4. r1 已证明真机入口可达，且首次选择确实改变 victim。
5. 保留原始请求、汇总、服务日志和指标；可复核吞吐与延迟，而不是只有截图。
6. r1 TTFT/抢占次数有正向观测，但它们伴随吞吐/解码代价，不作为普遍性能优势。

## 5. 劣势与局限

1. r1 吞吐下降 14.79%，不满足吞吐优化目标。
2. TPOT 尾部明显增加，尚无公平性、饥饿、逐请求重算成本解释。
3. 默认 utility 以 computed tokens 作为收益代理，无法代表混合模型的实际可释放 KV/Mamba 状态。
4. 依赖实验性 Core 补丁及精确源码守卫，不是安装即用的通用插件。
5. 两组都有 Core 补丁，没有 pristine Core 第三组，尚未量化接入本身的开销。
6. 无前缀缓存开启、无抢占负例、其他并发/模型/拓扑对照。
7. installed/首次 runtime 事件不足以测量整个实验的决策差异率；内部按 request ID 累计历史的长期内存增长也需验证。
8. r1 的 server_metadata 为 null；宿主/model 精确 revision、服务端文件指纹及工具 commit 未完整随配置记录。OFF-r1 缺少独立 versions/hardware 文件；不能把其他轮次文件冒充 r1。
9. 本地未发现 prepared/qwen35.json 的随结果归档副本；目前其身份依据 config 中记录的 SHA256，完整输入重建仍需取回该文件。
10. 性能仅一对，本报告不考虑 r2/r3，不使用其他项目的成绩填补缺口。

## 6. 对照验收门槛

以下沿用模板的 G1–G5 分类组织缺口，不声称已重新核验台账对本候选的最新正式规则。

| 门槛 | 本项目状态 |
|---|---|
| G1 历史效果与统计证据 | 未执行历史分支基准；r1 无重复或 CI |
| G2 机制正负例 | 正例入口可达；无触发负例未完成；可达不等于收益准入 |
| G3 提炼保真度 | CPU 算法差分通过；没有与历史完整服务的吞吐保真对照，不能宣称 ≤3% |
| G4 当前迁移价值 | 未通过：当前唯一格子的吞吐下降，未证明多个格子提升 ≥5% |
| G5 Pareto 声明 | 已提交；TTFT/吞吐取舍不自动构成合格非支配点 |

## 7. 适用场景与后续建议

候选场景是确实存在 KV 压力、需要选择抢占对象的同步调度部署。低压力下可能完全不触发；Prefix Routing 和正式 BidKV 的其他保护机制不在本项目范围。

后续优先补证据，再调整算法：先重做有完整指标的重复对照，确认取舍是否稳定；再测逐次被抢占请求大小、重算量和完成时间，解释为什么次数减少但吞吐下降。不要在同一实验中同时改权重、内存预算和 prefix caching。

具体执行步骤见第 10 节；当前不推荐默认开启作为吞吐优化。

## 8. 产出

### 8.0 代码仓库

| 项 | 状态 |
|---|---|
| 本地项目 | `D:/Desktop/mining/vllm-hust-utility-victim` |
| github仓库 | [hellolazy0401/vllm-hust-utility-victim: 从vllm-hust抽取出来的，安装到vllm的机制mod，属于ascend而不是core](https://github.com/hellolazy0401/vllm-hust-utility-victim) |
| PyPI | 有标准 wheel/sdist 结构；没有可核验的 PyPI 发布记录 |
| 许可证 | LICENSE、NOTICE 已存在，pyproject 声明 Apache-2.0 |
| 包与扩展 ID | `vllm-hust-utility-victim==0.1.0.dev2`；`org.vllm-hust.utility-victim` |

### 8.1 代码产出

| 内容 | 位置（项目根目录下） |
|---|---|
| 历史算法、配置及统计 | `src/vllm_hust_utility_victim/historical.py` |
| 适配、守卫及证据 | `plugin.py`、`selector.py`、`core_adapter.py`（同上包目录） |
| 契约补丁与原件 | `host_patch/` |
| 补丁检查/应用/恢复 | `scripts/apply_core_contract.py` |
| OFF/ON 启动与指标采集 | `scripts/start_swe_ab.sh`、`scripts/run_swe_ab.sh` |

### 8.2 验证产出

48 项本地 CPU 测试、历史算法差分、离线打包验证，以及 r1 ON 真机选人运行事件。CPU、协议、机制、性能结论分别记录，不相互替代。

### 8.3 数据产出

本报告引用 `results/off-m65-c16-r1/`、`on-m65-c16-r1/` 下的 summary/config/requests，以及对应 server.log、before/after.prom。派生数据为 `docs/report-data.json`。未采用旧笔记中的手填未知值或 r2 的重复粘贴记录。

### 8.4 文档产出

本报告 `docs/REPORT.md`，文档目录同内容副本 `vllm-hust-utility-victim-项目报告.md`，以及已有 MAPPING、SELECTION、CONTAINER_023、SWE_OFF_ON、VALIDATION 等文档。早期文档的“尚无真机结果”是当时记录，以本报告 r1 审计更新为准；本次没有覆盖历史原始笔记。

### 8.5 结论性产出

已回答：机制来源是什么、如何适配当前容器、是否真正参与选人、r1 吞吐/延迟的代价。尚未回答：取舍是否稳定、退化的因果来源、其他负载是否有收益、长期活性/公平性是否可接受。

### 8.6 未产出

无正式性能准入、无历史完整引擎性能保真结果、无已核验远程发布/排行榜记录、无逐次实际 KV 释放证明、无重复实验统计结论。

## 9. 复现与数据口径

在项目根目录运行（本报告复算仅依赖 Python 标准库）：

```bash
python scripts/summarize_report.py
python -m pytest tests -q
```

数据复算会覆盖派生的 `docs/report-data.json`，不修改原始结果。它核对请求总数、窗口完成数、窗口内 chunk tokens 与 TTFT P95，并核对 Prometheus 前后进程启动时间、全程成功数及输入/输出 token 总数。TPOT 采用请求 E2E 定义，包含首 token 后可能发生的等待，不冒充纯内核耗时。分位数采用线性插值。全套引用原件哈希见 `docs/report-r1-SHA256SUMS.txt`（含 evidence 与 r1 原件，排除字节码缓存）。

吞吐为窗口内实际输出 tokens/900 秒；请求在窗口后结束，其窗口内 tokens 仍计入吞吐。延迟表只选成功且 end≤900 的请求。抢占为 before/after 同标签计数差，**包含 drain**，与吞吐窗口不能直接混同。

| 产物 | SHA256 |
|---|---|
| r1 OFF requests.jsonl | `969af12f161dc5732e846fbb7ec47d346096614cc5e2b1561ca950a34ab3792d` |
| r1 ON requests.jsonl | `d0a36cfb73c996ae8d064268c90bec22f5b0990ce59cf829b25cf4eda451049f` |
| prepared workload（config 记录） | `4e62e54ef47497fd916a6c2906b220b3af400f87873ea0784740fed3f61e78c8` |
| tokenizer fingerprint（config 记录） | `319f580a2fc8d2ff1e1f48a26ea0c29eea35798d747e7188ca584e92c014bdf9` |

## 10. 未完成事项与具体步骤

### 10.1 先补齐 r1 证据（不需要重跑已有数据）

在容器使用真实 BENCH 路径：

```bash
export BENCH="$HOME/workspace/swe-prefix-reuse"
sha256sum "$BENCH/prepared/qwen35.json"
git -C "$BENCH" rev-parse HEAD
git -C /vllm-workspace/vllm rev-parse HEAD
git -C /vllm-workspace/vllm-ascend rev-parse HEAD
sha256sum /vllm-workspace/vllm/vllm/v1/core/sched/scheduler.py
```

1. 把 prepared 文件及上述输出复制回本地项目的证据归档，核对其 SHA 与 r1 config 一致。
2. 如果源码没有 .git，保留失败事实，使用实际源文件 SHA256；不要用 upstream version 冒充 fork commit。
3. 如果能找回 r1 OFF 的版本/硬件原记录，一并补齐；不能用今天重新采集的状态冒充 r1 当时状态。新增记录应注明采集时间及是否可证明未变更。
4. 给 r1 增加独立补充元数据文档，不改写原始 config 的历史事实。记录模型 revision、服务端源码/补丁身份、工具 commit 和负载文件路径。

### 10.2 后续重新开展重复对照（尚未执行，不纳入本报告）

使用现有已完成压力校准的 r1 配置：C16、900 秒、memory_fraction=0.65；每轮重启，其他参数相同。重新建立至少三对，交错 OFF→ON、ON→OFF、OFF→ON，输出目录必须全新。不要把未完成的 r2 当完整样本。

终端 A，原服务端 Python 环境：

```bash
export MOD="$HOME/workspace/vllm-hust-utility-victim"
export BENCH="$HOME/workspace/swe-prefix-reuse"
export MODEL_PATH=/models/Qwen3.5-35B-A3B
export RUN=off-m65-c16-repeat1
vllm-hust-ext extension enable org.vllm-hust.utility-victim
set -o pipefail
KV_MEMORY_FRACTION=0.65 bash "$MOD/scripts/start_swe_ab.sh" off "$MODEL_PATH" \
  2>&1 | tee "$BENCH/results/$RUN.server.log"
```

终端 B，重新设置 MOD、BENCH、RUN；按 `docs/SWE_OFF_ON.md` 的模板填写真实 `$RUN.metadata.json` 后运行：

```bash
curl -f http://127.0.0.1:18180/health
bash "$MOD/scripts/run_swe_ab.sh" \
  "$BENCH/.venv-bench/bin/swe-prefix-reuse" \
  "$BENCH/prepared/qwen35.json" \
  "$BENCH/results/$RUN.metadata.json" \
  "$BENCH/results/$RUN" 16 900
```

客户端含 drain 结束后，终端 A 停服并等待退出，再将 off/RUN/metadata 改为对应 on 重新启动和测试。此辅助脚本输出 summary 在 `$RUN/client/`，与 r1 直接 CLI 输出的目录层级不同；汇总程序若纳入新轮次需显式适配，不能直接混用路径。

验收：每轮 valid、0 失败、配置/负载身份一致、ON 有运行证据、OFF 无 utility 运行事件；记录所有失败轮次而非静默剔除。按完整轮次给均值与范围，若要置信区间需增加独立重复，不能把几百条相关请求当几百次独立实验。

### 10.3 补无触发负例与因果观测

1. 无触发负例：两组都用较低并发（例如 C1）或相同更充足 KV 配置。以实际抢占增量为 0 为准；不能仅凭参数宣称无抢占。预期 ON 可安装但无 utility 运行事件。
2. 实际成本：在独立测量版本中记录每次被选 victim、computed tokens、实际释放 blocks/状态、重新计算 tokens 和恢复时间。OFF/ON 安装相同观测代码，先测探针开销；不要只给 ON 加重日志。
3. 公平性：按请求统计重复抢占次数、最长等待、E2E 尾部，并用有界长时间压力测试检查饥饿和 selector 历史字典增长。现有日志不足以完成此项。
4. 验证 pristine Core：另设第三组，通过补丁脚本 `--restore` 后启动 OFF，以同样协议比较“原始 Core”和“打补丁但关闭策略”的差别。先停服、保留备份，不绕过指纹拒绝；恢复实验结束后重新 `--apply`。
5. 其他并发/缓存/权重实验各自成组；新权重是新策略配置，不能回写成 r1 已验证结果。

### 10.4 上传代码仓库（待办，不会在本次自动上传）

先确定有写权限的 GitHub 组织/账号和仓库名；不能把模板的 EPLB 仓库地址替换后当作已存在仓库。以下在本地 PowerShell 执行，发布地址由 GitHub 新建仓库页面给出。

1. 将本报告、统计脚本、r1 证据整理为可审阅版本。源码带 LICENSE/NOTICE；原始 requests 含生成内容，公开前确认数据许可和内容；大文件可放 Release/单独归档并在仓库保存 SHA256。
2. 补充 `.gitignore` 排除 `.idea/`、模型、venv、凭据和临时文件；当前已忽略 dist。只提交 r1，不提交未完成的其他轮次。
3. 初始化并显式暂存代码及文档（不要直接 `git add .` 把所有 results 加入）：

```powershell
Set-Location D:\Desktop\mining\vllm-hust-utility-victim
git init -b main
git add .gitignore LICENSE NOTICE MANIFEST.in pyproject.toml README.md src tests scripts docs host_patch evidence
git diff --cached --stat
git diff --cached --check
git commit -m "Extract utility victim selector and document r1 evaluation"
```

4. 审核 r1 文件后另行提交。至少保留两份 summary/config、指标快照、运行事件和原始请求的可下载归档与哈希。没有托管 raw 数据时，应明确仓库不能完整复算，不要声称全部复现证据已公开。
5. 在 GitHub 建立目标空仓库，选择团队要求的可见性；复制其 clone URL，然后执行（把占位 URL 换成真实值）：

```powershell
git remote add origin https://github.com/YOUR_OWNER/vllm-hust-utility-victim.git
git push -u origin main
git remote -v
git rev-parse HEAD
```

已有仓库时先 clone 并查看其分支/历史，在评审分支导入代码，不强推覆盖。按团队流程建立 PR；记录实际仓库 URL、commit、PR、可见性到报告 8.0。当前没有理由编造 PR 编号。

### 10.5 PyPI 发布与网站登记

“打包成 PyPI 结构”已经完成；真正发布 PyPI 不是当前性能验收的前提。如果需要公开安装，先完成代码审核和仓库发布，再在干净 Python 环境执行：

```bash
python -m pip install -e '.[test]' twine
python -m pytest tests -q
python -m build
python -m twine check dist/vllm_hust_utility_victim-0.1.0.dev2*
```

确认版本未占用、配置发布权限后，先上传 TestPyPI 并在新环境安装验证两个 entry points/manifest；通过后才上传正式 PyPI。上传命令应显式选择本包两个文件，不使用 `dist/*`（该目录还有其他离线依赖和归档）：

```bash
python -m twine upload --repository testpypi \
  dist/vllm_hust_utility_victim-0.1.0.dev2-py3-none-any.whl \
  dist/vllm_hust_utility_victim-0.1.0.dev2.tar.gz
```

正式发布去掉 `--repository testpypi`；若版本已发布不可覆盖，应按实际修改升版并重新验证。不要把 token 写进报告或命令历史。网站组件登记需先读取目标网站当前 schema/贡献流程，填写实际仓库与 candidate 状态；r1 可作为带限定的负结果，不应提交为吞吐提升纪录。

### 10.6 文档状态同步

提交代码前，在 README、CONTAINER_023 和 VALIDATION 增加指向本报告的日期说明，保留历史记录而非删除；manifest 的 `performance_verified=false` 应继续保留。若将来更新“仅 CPU”准入描述，应使用新版本并明确仅机制已真机可达，不能改成性能已通过。
