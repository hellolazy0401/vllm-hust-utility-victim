# vllm-hust-utility-victim 项目报告

> 核验日期：2026-10-05（Asia/Shanghai）。
> 权威源码目录：`D:/Desktop/mining/vllm_hust_utility_victim-0.1.0.dev2`。
> 数据批次：`results/utility-c1-c16-m65`；环境及部署补证：`evidences/utility-c1-c16-m65`；历史来源与测试记录：`evidence/`。
> 范围：只使用 C1/C2/C4/C8/C16 的 r1 正式实验，共 10 组；20 秒 probe 单列为协议证据。r2 和旧项目目录的数据均不纳入。
> 状态：candidate，已证实当前批次的机制可达性及无触发对照，未通过性能准入。

## 0. 摘要与本次纠错

之前报告使用了另一个目录、另一批同名 r1 数据。其数值并非当前批次的结果，不能仅按相同文件名拼接。本报告已根据当前原件重新计算，原始实验文件保持不变。

| 旧报告内容 | 本次核验后的修正 |
|---|---|
| 源码位于 vllm-hust-utility-victim | 以用户指定的 vllm_hust_utility_victim-0.1.0.dev2 为准 |
| 仅有一个 C16 r1 对照、负例未完成 | 当前有 C1/2/4/8/16 五个并发格子；C1～C8 均无抢占 |
| C16 吞吐 172.52 → 146.997 tok/s | 本批次为 **175.024 → 151.368 tok/s，下降 13.52%** |
| C16 抢占 311 → 188 | 本批次含 drain 的增量为 **398 → 191，减少 52.01%** |
| TTFT P95 下降 39.23% | 本批次下降 **29.37%** |
| TPOT 均值/P95 增加 20.33%/86.46% | 本批次增加 **17.50%/82.09%** |
| 未初始化 Git、无远程仓库记录 | 已有 Git 仓库；远程 main 已核验，与本地 83a2464 一致 |
| server_metadata=null、OFF 硬件文件缺失 | 新批次正式 config 均带 metadata，OFF/ON 各有硬件快照 |
| 宿主 diff、已安装插件身份未提供 | 已提供；Core diff 与补丁参考吻合，10 个安装源码/配置哈希全部匹配 |

结论：C16 上 utility 确实改变过选人；抢占次数和 TTFT 降低，但吞吐与 TPOT/E2E 恶化。C1～C8 不触发 utility，不能把这些格子的差异归功于它。每个并发仅一对 r1，尚无重复性或置信区间结论。

## 1. 来源

| 项 | 内容 |
|---|---|
| 算法 PR | Ascend #39，`Feat/bidkv victim selector item1 2`，作者 cybber695 |
| 固定 merge SHA | `76d8939d7e21d17a295adf99e9dda17bde5a88cc` |
| 原始文件 | `evidence/ascend-pr39-victim_selector.py`；PR 元数据及 files diff 同目录归档 |
| 相关 Core 接口 | #171 / `5536d0873fb41c4925d0e6e9112a1ea70faeeb3a`；非第二个算法来源 |
| 历史 Core 上下文 | `1aa7cd10b7b16e82fdb29fcc47d3a3cd93bd01dc`；不是当前部署 HEAD |
| 打包模板 | vllm-hust-vSpec，采用双 entry point、src 布局和 manifest 约定 |
| 包 | `vllm-hust-utility-victim==0.1.0.dev2`；扩展 ID `org.vllm-hust.utility-victim` |

不把 A2A 的证据编号、EPLB 的成绩或正式 BidKV 的保护机制套用于本包。来源明细见 docs/MAPPING.md；旧映射中的本地 legacy 主机说明须与当前 Core contract 接入区分。

## 2. 基础改造思路

### 2.1 原机制

在宿主已进入抢占选人路径后，以 utility 排序选出 victim。默认公式：

```text
U = max(computed_tokens, 0)
    / max(1 + 0.5 * completion + 0.3 * preemptions + 1e-6, 1e-6)
completion = clamp(output_tokens / max_tokens, 0, 1)
```

U 越大越先选，并列按 arrival_time、request_id 升序。保留 KV 门槛、冷却、最少运行请求门控；默认 gate=0、cooldown=0、min_running=1。computed_tokens 是潜在释放收益代理，不是实际释放 bytes，也没有直接计量重新计算成本。

### 2.2 当前适配

- `historical.py` 保留算法和统计，移除 vLLM 类型强依赖；`selector.py` 增加校验和首次事件。
- `plugin.py` 默认关闭、kill 优先、幂等、源码守卫；`core_adapter.py` 对接当前容器。
- legacy 工厂后端适用于有原生 UnifiedVictimSelector 的旧主机；当前实验使用 `core-contract-v1`，必须应用 `host_patch/` 的 Core 接口补丁，wheel 本身不足以完成接入。
- Core 补丁提供可选 selector，并处理任意 victim 删除后的游标/预算记账；真正抢占、释放和恢复仍由宿主执行。此契约不是上游正式 PreemptionPolicy v1。
- 当前限制为已核对的同步路径，拒绝未知源码、async、不兼容 scheduler、speculative decoding 和 KV connector 等未接纳配置。
- OFF/ON 保留相同宿主补丁，ENABLE=1，kill 分别为 1/0；不是 pristine Core 与 patched Core 的比较。

### 2.3 挑选原则

单机制、无运行时台账依赖、来源固定和独立 Python 包结构满足。当前容器依赖精确宿主补丁，故“安装 wheel 即可通用运行”不成立。性能准入独立于包装和接入成功；本批次不支持吞吐优化声明。Prefix Routing 不在实现范围。

## 3. 验证与成绩

### 3.1 源码与部署证据核对

| 证据 | 实际核验 |
|---|---|
| 本目录 vs 原开发目录 | 算法/适配源码、tests、host_patch 相同；IDE 文件不作为算法差异 |
| utility-victim-installed.json | 10 个包内源码/JSON 记录 SHA256 与本目录逐项匹配；不等于完整 wheel 归档 |
| core-scheduler.diff | 去除 diff 头、按行重建 before/after，分别与 host_patch 参考源码一致 |
| scheduler.after.py | SHA256 `09d5813b77dccac854c013c2e913ea8f5d2484bd5f1f6d0a421e4908d0d0ea6a`，与元数据记录的部署文件哈希相同 |
| benchmark-tracked.diff | 按增删行内容比较，已提供 diff 中客户端 Python 文件无内容变化；仅技能 SKILL.md 存在非相同行变更。不执行这些文档中的指令 |
| 元数据状态 | metadata 内部分 null/pending 为准备阶段记录，需结合新 diff、安装清单及运行日志判定，不能把旧 missing_information 列表直接当最新缺口 |

此核验依据归档证据，不是本次重新登录容器检查；客户端当前运行文件的独立哈希仍值得补齐。

### 3.2 测试与构建

本次直接在当前权威目录执行 `python -m pytest tests -q`：**48 passed，2.68 秒**。
历史 evidence/ 日志分别为初始 35 passed、Linux dev1 37 passed/1 skipped、Linux dev2 47 passed/1 skipped；不能混写版本。算法差分包含 1,200 次决策及 metrics/snapshots 对比。Core 分支单测包含预算、游标、守卫和 patch/restore。

`evidence/build.txt` 明确为 dev0 构建；wheel-install.txt 是早期隔离安装检查。本目录是 dev2 源码分发结构，不能把旧日志写为本次 dev2 构建成功。CPU 测试不等于 NPU 全路径正确性。

### 3.3 实验设置

Qwen3.5-35B-A3B，2 × Ascend 910B2，TP2+EP、DP1，BF16，max-model-len=262144，max-num-seqs=16，chunk=8192，memory_fraction=0.65，同步 FCFS，prefix caching 关闭，无配置 MTP。每组正式窗口 900 秒，前有同名 `-probe` 的 20 秒协议预检。

10 组正式 r1 和对应 10 组 probe 均 valid；正式实验 failed_requests=0、退出码=0。所有正式 config 的 workload SHA256/tokenizer 身份一致。probe 与正式测量分开；同进程预检可能影响编译/运行时状态，不能称全新服务冷启动测量。新 session salt 仅保证按客户端策略隔离不同 play 的缓存。

环境记录：Core `0.23.0+empty`，Ascend `0.23.0.post1`；Core HEAD `0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665`（dirty），Ascend HEAD `1cdb8c4db6e50f36f1fb3283b3e3dd618f6821e8`。客户端 base HEAD `6861242dbd9f17b707003191e4200b7752911d7c`，版本 0.1.2。CANN 文件证据包含 9.1.0/9.1.0.B150 组件，不能仅据安装文件证明进程实际加载库版本。

### 3.4 r1 并发矩阵

吞吐为两卡合计 tok/s；TTFT 为秒；抢占为正式运行前后差，含 drain。

| C | OFF 吞吐 | ON 吞吐 | 变化 | OFF/ON TTFT P95 | OFF/ON 抢占 | ON runtime 事件 |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 39.449 | 40.314 | +2.19% | 1.876 / 1.889 | 0 / 0 | 0 |
| 2 | 66.357 | 66.410 | +0.08% | 2.515 / 2.534 | 0 / 0 | 0 |
| 4 | 108.340 | 107.703 | -0.59% | 2.685 / 2.657 | 0 / 0 | 0 |
| 8 | 162.376 | 158.621 | -2.31% | 2.748 / 2.713 | 0 / 0 | 0 |
| 16 | 175.024 | 151.368 | -13.52% | 9.238 / 6.525 | 398 / 191 | 1 |

C1～C8 的 ON 均出现 4 条 installed、0 条 runtime；所有 OFF 均为 0 条 installed/runtime。说明无触发对照已存在，低并发差异不应归因于 utility 分支。C16 ON 有 1 条首次 runtime，selection_changed=true、tokens_proxy=41302、actual_kv_freed_verified=false。不能把 installed 次数当作实例数或抢占次数。

### 3.5 C16 延迟与覆盖

| 指标 | OFF | ON | 变化 |
|---|---:|---:|---:|
| 每卡吞吐 tok/s | 87.512 | 75.684 | -13.52% |
| decode P90 tok/s | 19.307 | 19.225 | -0.42% |
| TTFT P50 ms | 1519.065 | 1377.110 | -9.34% |
| TTFT P95 ms | 9237.753 | 6525.030 | -29.37% |
| TPOT 均值 ms | 81.314 | 95.548 | +17.50% |
| TPOT P95 ms | 151.693 | 276.225 | +82.09% |
| E2E P95 ms | 110545.961 | 117480.764 | +6.27% |

窗口内完成请求为 323/296，含 drain 总请求为 339/312；完整会话为 6/4。C16 最大 prompt 均为 40,244；整个 r1 矩阵最大 prompt 为 C8 的 55,491，仍不足以声称 256K 满上下文测试。只有一个 r1 对照/格子，没有重复噪声区间。

### 3.6 服务端与客户端对账

10 组均验证：窗口完成数与明细一致，窗口 chunk tokens 与 summary 一致，TTFT P95 可复算；前后 process_start_time_seconds 相同；服务端成功数、输入/输出 tokens 的增量与全部请求明细之和一致。

C16 全程输入为 OFF 4,790,664 / ON 4,254,238 tokens，全程输出 187,450 / 161,695 tokens。它们含 drain，不能除以 900 冒充窗口吞吐；输入计数也不是包含所有重算的计算量。首次事件不记录所有 victim，不能还原逐次抢占成本。更少抢占但更低吞吐的可能解释是 victim 大小/重算代价及请求混合不同，尚未证实因果。

## 4. 优势

1. 来源与适配边界清晰，单机制可启停，历史差分及严格源码守卫可审阅。
2. 新补证将已安装包源码、部署 scheduler 与本目录建立哈希对应。
3. 同一批次已获得无触发格子与 C16 触发格子，机制可达性证据比旧报告完整。
4. C16 首 token 延迟和抢占次数降低是实测现象；伴随吞吐与解码代价，不宣称普遍优势。

## 5. 劣势与局限

1. C16 吞吐下降 13.52%，TPOT P95 增加 82.09%，不支持默认开启作为吞吐优化。
2. 每格仅一对 r1；C2 实际先 ON 后 OFF，不能把文件排序当执行顺序。未构成重复 ABBA 实验。
3. utility 的 token 代理不代表混合模型的实际释放量；重算、饥饿、公平性与长期字典增长未验证。
4. 依赖本地 Core 实验契约，未适配路径被拒绝；没有 pristine Core 第三组。
5. 模型权重 revision/manifest、prepared 文件本体、已加载 CANN 版本及全量运行时身份仍未完全归档。
6. metadata 的准备态字段未全部回填；需记录补证结论，不能修改原始实验事实。
7. 本报告不继承旧批次负载时间序列、请求哈希或性能数字，也不纳入 r2。

## 6. 对照验收门槛

沿用模板 G1～G5 的分类，而非声称已重新审核台账最新规则：

| 门槛 | 当前状态 |
|---|---|
| G1 历史效果与统计证据 | 未做历史完整引擎基准；当前每格无重复 CI |
| G2 机制正负例 | 已有 C1～C8 无触发与 C16 改变选人证据；性能正收益准入未通过 |
| G3 提炼保真度 | CPU 算法差分通过，未验证历史服务吞吐差 ≤3% |
| G4 当前迁移价值 | 未通过；触发格子吞吐下降，无两个提升 ≥5% 的格子 |
| G5 Pareto | 未作正式非支配声明或排行榜提交 |

## 7. 适用场景与后续建议

仅在宿主实际需要抢占时策略才参与。本批次 C16 属于触发场景，C1～C8 为无触发对照。先增加同配置重复、解释重算与延迟代价，再考虑调整 utility 权重；权重、缓存、并发改变应作为独立实验格子，不能回写成原 r1 结果。

## 8. 产出

### 8.0 代码仓库

- 远程：[hellolazy0401/vllm-hust-utility-victim](https://github.com/hellolazy0401/vllm-hust-utility-victim)。
- 本次只读 `git ls-remote origin refs/heads/main` 返回 `83a24647dcb93ee51c636188721fe6c47044027c`，与本地 main 一致。
- 该提交为“补充了实验结果results，和evidences”。上传源码/证据已完成，不再列为“尚未初始化 Git”。
- 未核验仓库可见性、PR 或 PyPI 发布状态；没有凭据/页面证据则不虚填。当前报告修订尚未提交/推送。

### 8.1 代码与验证

`src/vllm_hust_utility_victim/`、`host_patch/`、`tests/`、`scripts/apply_core_contract.py`、OFF/ON 启动脚本均在当前目录。新增 `scripts/audit_report.py` 只读 r1 原件、生成 `docs/report-data.json`，不改结果。

### 8.2 数据与文档

- `evidence/`：历史 PR、原始算法、CPU/构建记录。
- `evidences/utility-c1-c16-m65/`：本批次元数据、宿主/客户端 diff、安装文件哈希、硬件与运行环境。
- `results/utility-c1-c16-m65/`：正式/预检的 config、summary、requests，以及日志、Prometheus、退出码、硬件快照。
- `docs/REPORT.md` 与文档目录同名报告：本次修订；`docs/REPORT.previous-input.md` 保留旧报告，仅用于追溯，不能作当前实验结论。
- `docs/report-r1-SHA256SUMS.txt`：当前引用原件指纹。

### 8.3 未产出

无性能准入、无长期公平性/活性证明、无完整历史性能保真结论、无已核验 PyPI 发布或排行榜提交。

## 9. 复现与口径

在当前源码目录执行：

```bash
python scripts/audit_report.py
python -m pytest tests -q
```

复算只依赖标准库；tests 需要 test extra，管理器可选检查在无依赖时跳过。数据输出覆盖 docs/report-data.json，不修改原件。统计范围只含 r1 正式实验，probe 不混入吞吐/延迟；r2 排除。

TTFT P50、TPOT、E2E 从 success 且 end≤900 的明细计算，线性插值分位数。TPOT=(E2E−TTFT)/(N−1)，不是 decode P90 的倒数。吞吐仅计窗口 chunk tokens；monitor 差含 drain，不混用时间分母。

| 输入身份 | 值 |
|---|---|
| prepared SHA256（归档 receipt/config） | `4e62e54ef47497fd916a6c2906b220b3af400f87873ea0784740fed3f61e78c8` |
| tokenizer fingerprint | `319f580a2fc8d2ff1e1f48a26ea0c29eea35798d747e7188ca584e92c014bdf9` |
| off-m65-c16-r1 requests SHA256 | `19234a0e1d8a997e3d811de4ec703cb1f4c5f4a9922e85ef326241d76844b55f` |
| on-m65-c16-r1 requests SHA256 | `0848267caa553a920f5be01e7280d519678b751d8f54e6ece8689c965766e9b2` |

## 10. 尚未完成的事项与操作步骤

### 10.1 发布本次纠错（仓库已存在，无需 git init）

```powershell
Set-Location D:\Desktop\mining\vllm_hust_utility_victim-0.1.0.dev2
python scripts/audit_report.py
git diff --stat
git add docs/REPORT.md docs/report-data.json docs/report-r1-SHA256SUMS.txt scripts/audit_report.py
git diff --cached --check
git diff --cached --stat
git commit -m "Correct report against utility-c1-c16-m65 r1 evidence"
git push origin main
```

上述命令供用户执行，本次未提交/推送。若团队要求 PR，先创建评审分支并推送该分支，再按仓库流程提交 PR；不要覆盖远程历史。旧报告备份不必发布。

### 10.2 补齐剩余身份与归档

1. 从容器取回 prepared/qwen35.json 并核对上述 SHA256；已有 receipt 不等于文件已归档。
2. 保留 model-download-metadata-files.txt 的检索结果，提取能证明模型 revision 的真实值；无法证明时补权重文件 manifest，不以模型路径替代 revision。
3. 保存实际客户端 client.py、prepare.py、runner.py 的哈希和 diff，关联运行日期；本次已检查归档 diff，但不能证明采集后文件从未变化。
4. 如需精确 CANN 身份，归档实际进程加载库路径与对应版本；已有安装目录文件已补齐，不再笼统称“没有任何 CANN 信息”。
5. 在独立审计说明中更新 metadata 的 pending/missing 判定，并引用本报告核验项；不直接伪造重写原始 config。

### 10.3 后续重复与成本观测

现有无触发负例已经完成；尚需重复性。停止旧服务并确认退出后，用相同两卡、同 prepared、相同 0.65 内存配置，重新开展至少三对完整 OFF/ON，交错顺序，每轮新建输出目录，probe/正式时间和指标采样规则固定。

```bash
# 服务终端：使用实际 MOD、MODEL_PATH，保持已成功运行的 Ascend 环境。
KV_MEMORY_FRACTION=0.65 bash "$MOD/scripts/start_swe_ab.sh" off "$MODEL_PATH"
# 客户端终端：填真实路径/元数据，并使用新的结果名。
bash "$MOD/scripts/run_swe_ab.sh"   "$BENCH/.venv-bench/bin/swe-prefix-reuse"   "$BENCH/prepared/qwen35.json"   "$BENCH/evidence/server-metadata-off.json"   "$BENCH/results/off-m65-c16-repeat1" 16 900
```

等待客户端 drain 结束再停服；以 on 和匹配的 metadata 重启，采用同参数压测。辅助脚本的 client 子目录与本次直接 CLI 归档不同；汇总新数据时显式适配路径，不冒充已有 r1。

在独立测量版本对两组加同样的逐次 victim、实际释放 blocks/状态、重算 tokens、等待和恢复耗时观测，先检查探针开销。检查长请求重复抢占与内存增长；目前不能靠一次 runtime 事件回答这些问题。

### 10.4 其余发布与文档

1. README 若仍使用旧批次 172.52/146.997、311/188 或“metadata 缺失、无远程仓库”的内容，需另行与本报告同步；本次以项目报告纠错为范围，未把 README 旧数字当依据。
2. 需要 wheel 发布时重新构建 dev2/后续版本并保存日志；不要以 evidence/build.txt 的 dev0 日志代替。没有要求公开安装时，不必为性能验证发布 PyPI。
3. 性能准入仍未通过，保留 performance_verified=false；公开结果可以报告负结果和取舍，不应宣称吞吐提升。
