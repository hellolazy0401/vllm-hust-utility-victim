# 筛选原则核对

日期：2026-10-01。以用户指定《操作记录.MD》第 1–2 步为范围。`#173` 是示例编号，不是强制选择。

## 结论

选择清单第 6 条 **Ascend #39 utility victim selection**，作为单机制独立封装与消融候选。
当前目标已内建等价算法，因此当前实现处置为 `builtin`；本次交付处置为 `packaged_extraction_for_ablation`。
两者不是两项性能优化。若验收条件另要求“必须为当前宿主带来新算法/新增收益”，本项**不满足该额外条件**，不能仅凭打包通过宣布迁移价值准入。

## 9 条机制的比较

| 清单项 / PR | 本次处置 | 理由 |
|---|---|---|
| common-prefix skip / Core #37 | 排除 | 原资料明确排除；Ascend 消费能力谓词未解决 |
| Prefix Routing / Core #173（#80/#154/#170/#172 演进） | 不选 | 完整路由、事件目录、请求处理、代理生命周期耦合，超出本轮最小单入口抽取；不把历史四条各算新优化 |
| 路由恢复 / Core #225 | 不选 | 依赖完整路由状态机，属于正确性加固 |
| 负载感知并列选择 / Core #258 | 不选 | 需要 /load、轮询、TTL 与 routing 主线配合，不单搬比较函数冒充完整机制 |
| victim 插件接口 / Core #171 | 相关非来源 | 是接口而非 utility 算法；保持独立，不重复计功 |
| utility victim / Ascend #39 | 选择 | 独立纯 Python selector + 已有工厂，保留原执行链，可 CPU 差分验证 |
| 队头阻塞恢复 / Core #150/#164 | 不选 | 主循环活性修复；不做整个 schedule 方法的源码替换 |
| SimLLM / Ascend #66/#70/#80 | 不选 | 多处耦合、近似复用质量风险、正文与源码存在证据缺口 |
| layered prefill / Ascend #272 | 不选 | scheduler/runner/模型层状态共同变更，不符合本轮小型独立插件范围 |
| Core #236 + Ascend #216 | 不记作机制 | 仅抢占恢复观测配套，不能作为额外性能收益 |

以上未选项主要依据用户提供清单；本次重新联网核对的 PR 为 Ascend #39、Core #171，不能称为重新审计了所有 PR。

## 操作记录要求逐项核对

| 原则 | 结论 / 证据 |
|---|---|
| 一个包一个机制 | 通过：仅选人排序、门控及必需接入；不搬调度主循环、抢占执行、prefix 路由 |
| 不依赖台账仓库 | 通过：runtime 仅标准库，不 import legacy017-perf、BidKV、vSpec；算法随本包发布 |
| 来源 commit 固定 | 通过：保存 GitHub PR 元数据、files diff、固定 SHA 原始 selector，mapping.json 记录角色与 hash |
| 能独立打包 | 有条件通过：需要已有 Ascend 工厂契约；用原 class 的 classmethod 替换，不改源码文件，不改 C++/数据结构 |
| 当前实现去重 | 已完成：#39 固定源码与本地 Ascend selector AST 完全一致；Core #171 是另一个接口文件；没有把它们当成两份算法 |
| 版本 / ID / manifest 一致 | 自动化测试核对；两个 entry-point 组与 package-data 齐全 |
| 默认关闭 / kill | 自动化测试；disabled 不 import vLLM/Ascend/torch；kill 优先；原生开关冲突拒绝 |
| 宿主不匹配拒绝 | 全模块 + 活体方法 AST 指纹；不可读取源码、未知修改或已有非本插件 patch 时拒绝 |
| 幂等 / 已导入别名 | 同一 class 原位工厂替换；重复 register 不叠加，单测覆盖 |
| 证据事件 | installed 与 utility 首次选人分开；明确不是实际 KV 释放确认 |
| 无真机测试 | 使用原始历史文件加最小类型 stub；算法、配置和 metrics 差分无需 torch/NPU |
| 准入如实披露 | 第 2 步 CPU 包装验证，不声明 G1–G5 或九级门禁通过，不继承历史吞吐数字 |

## 与文档原则的取舍

《Legacy017 历史性能包：背景、设计、实现与验收》倾向稳定版本化 hook，不应任意 monkey patch；《操作记录.MD》明确允许已核对宿主上的子类替换/monkey patch。本轮按后者做严格源码指纹限制的实验性工厂适配，承认它仍是私有 ABI，不冒充通用稳定协议。后续生产准入应切换正式扩展协议。

双周会 PDF 的目标是独立交付、可启停、可追溯；本次新增独立包，不删除宿主现有代码。源码目录不是 Git checkout，无法给出可靠当前 HEAD；记录实际文件哈希与 upstream_version.json，而不冒充 upstream anchor 就是 fork HEAD。

E038/E039/E049 属于操作记录的 A2A 示例，不移植成本机制证据。这里的 `LOCAL-UV-*` 是本次自建本地编号，非原台账 E 编号。

## 与第三份 BidKV 实现去重

还读取了 `vLLM-HUST/vllm-hust-bidkv@edb7f090a9fe3698f68d755c36f793d71f9a460d` 的 `src/bidkv/adapters/vllm_hust/selector.py`（见 evidence 原件）。它仍含相同 utility 公式，但已改为不可变 `PreemptionContext`、`select_victim(context) -> str | None` 的 v1 契约，还包含 liveness abstention、cascade guard 与多种策略。它不是 #39 的逐行等价实现，也不能把本包当成它的改进版。

双周会 PDF 第 7–9 页的图也显示该正式 BidKV/PreemptionPolicy 路线。当前用户本地 Core 不存在 `vllm/v1/core/sched/preemption.py`，Ascend 四条路径仍使用旧 `UnifiedVictimSelector` 工厂。因此本包是针对所给旧契约目标的历史抽取实验，不重复建设正式 BidKV 产品线；未来切换正式宿主契约时应优先复用已有 BidKV Mod。

本轮比较四者的结论：Core #171 是旧接口；Ascend #39 是算法；本地目标等价内建；正式 BidKV 已演进为不同契约与更多保护逻辑。性能价值准入保持未通过。
