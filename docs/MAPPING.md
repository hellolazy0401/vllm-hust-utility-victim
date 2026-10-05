# PR → 机制 → Mod → 验证对应关系

主机制 ID：`ascend-utility-victim-selection`。机器可读完整记录见 [mapping.json](mapping.json) 和 [mapping.csv](mapping.csv)。

| 环节 | 对应项 | 身份与边界 |
|---|---|---|
| 用户清单 | 调度_Prefix_Routing与抢占机制清单.md，第 6 条 | 调度/抢占，不是跨节点 Prefix Routing |
| 算法 PR | intellistream/vllm-ascend-hust-legacy-20260831 #39，cybber695 | 唯一算法来源；已合并 |
| 算法提交 | `76d8939d7e21d17a295adf99e9dda17bde5a88cc` | PR merge SHA，已通过 GitHub API 核对 |
| 原始文件 | `vllm_ascend/core/victim_selector.py` | evidence/ 保存完整原件；包括配置、排序、门控、metrics |
| Mod 算法 | `src/vllm_hust_utility_victim/historical.py` | 只去掉 vLLM 类型导入，policy 用 enum.name 兼容；排序、公式、门控、metrics 保持 |
| Mod 接入 | `plugin.py` + `selector.py` | 默认关闭、工厂替换、源码守卫、原生冲突、额外非法参数校验、证据事件 |
| 宿主接点 | `UnifiedVictimSelector.from_vllm_config` | classmethod 原位替换，先前 import 的 class 别名也可见 |
| 原始消费者 | recompute / dynamic-batch / profiling-chunk / balance | 保留各自 preempt/KV 执行链；不复制 scheduler 实现 |
| 相关 Core PR | #171 / `5536d0873fb41c4925d0e6e9112a1ea70faeeb3a` | 仅相关可插拔接口，不是本包 source_core 算法，不安装第三个 entry point |
| Core 历史 pair | `1aa7cd10b7b16e82fdb29fcc47d3a3cd93bd01dc` | 用户报告的历史上下文；未声称 #39 合并时配对 commit |
| Ascend 历史 pair | `03ae1d03db8049cd2a5c3f824039814459542e25` | 用户报告的历史上下文，与 #39 merge 区分 |
| 模板 | `vllm-hust-vSpec` | 借用打包协议，不包含 speculative decoding |
| 产物 | `vllm-hust-utility-victim==0.1.0.dev2` | wheel + sdist；extension_id=`org.vllm-hust.utility-victim` |
| 保真验证 | `tests/test_selector.py` | 2 policies × 6 gates/configurations × 100 决策，共 1,200 次；victim、metrics、snapshots 逐项对照 |
| 接入验证 | `tests/test_activation.py` | 默认关闭、kill、别名、幂等、宿主不匹配、冲突与事件 |
| 打包验证 | `tests/test_manifest.py` + 隔离 wheel 安装 | 静态 manifest、版本、资源和 entry point |

本地证据编号：

- `LOCAL-UV-001`：evidence 下 #39/#171 API 原件、files diff 和固定 SHA selector。
- `LOCAL-UV-002`：mapping.json 中的宿主/模板/输入文件 SHA256，以及原生算法等价结论。
- `LOCAL-UV-003`：docs/VALIDATION.md、evidence 下测试与构建/安装日志。

本地源码证明 selector 等价；它不证明当前 Core 0.23.1 与 Ascend 0.19.1 源码组合能通过 NPU 服务启动。当前源码来自无 .git 的目录，不编造 fork commit。
