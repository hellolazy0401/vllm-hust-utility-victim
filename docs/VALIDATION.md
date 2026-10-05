# 第 2 步验证记录

> 本页保留 dev0 初始记录。dev1 的 WSL Python 3.11 与 Windows 3.12 新验证结果见 [修复记录](PYTHON311_FIX.md)。

日期：2026-10-01（Asia/Shanghai）。环境：Windows，Python 3.12.14；独立开发 venv 和独立 wheel 验证 venv。

| 检查 | 已执行结果 | 限定 |
|---|---|---|
| GitHub PR 身份 | #39 merge=`76d8939d7e21d17a295adf99e9dda17bde5a88cc`；#171 merge=`5536d0873fb41c4925d0e6e9112a1ea70faeeb3a` | 保存 API 元数据及文件 diff，不只读 PR 正文 |
| 历史/当前去重 | 原始 #39 selector 与本地 Ascend selector AST 一致 | 原生已经有算法，不是新增能力 |
| 接入点静态检查 | 四个 Ascend scheduler 路径均调用 selector 工厂 | 未执行这些 scheduler 的完整真实主循环 |
| CPU 测试 | **35 passed**，无 skipped | 包括 1,200 个与原始历史实现的差分决策 |
| Ruff | All checks passed | src、tests、scripts |
| 包构建 | wheel + sdist 成功 | 纯 Python，py3-none-any；没有发布到 PyPI |
| wheel 隔离安装 | 新 venv 仅 pip + 本包，安装成功 | 未安装 torch/vLLM/Ascend |
| wheel 自检 | 双 entry point、版本、manifest、host fingerprint 均存在；默认 register 无 runtime 导入 | `python -I scripts/verify_wheel.py` |
| 扩展管理器真实解析 | `org.vllm-hust.utility-victim 0.1.0.dev0 in_process_plugin` | 静态 discover_bundles，无 enable、无状态修改 |

扩展管理器测试固定为 `vLLM-HUST/extension-manager@ff144b469ad8cf7a1109610b3a6a4e3528bc40ee`，版本 `0.2.0.dev0`。PyPI 查询无该 distribution，因此从固定 GitHub 源码 ZIP 安装进开发 venv。没有改用户全局 Python。

## 可重现命令

在本项目根目录使用独立 Python 环境：

```bash
python -m pip install -e ".[test]"
python -m pytest tests -q
python -m ruff check src tests scripts
python -m build
```

`tests/test_manager.py` 在无 `vllm_hust_ext` 的普通测试环境会明确 skip；本次开发环境实际安装了它，35 项全部执行。

源码审计：

```powershell
python scripts/audit_sources.py --workspace 'D:\Desktop\mining\vllm-hust' --documents 'D:\Desktop\mining\文档' --template 'D:\Desktop\mining\vllm-hust-vSpec'
```

新 venv 安装 wheel 后运行 `python -I scripts/verify_wheel.py`。结果证明 wheel 自包含，不依赖 editable 安装和源码路径。

测试原件在 `evidence/pytest.txt`、`evidence/ruff.txt`、`evidence/build.txt`、`evidence/wheel-install.txt`。归档与最终产物哈希在 `dist/SHA256SUMS.txt`，该哈希文件本身不计入自身。

## 尚未验证，不能声称完成

- 没有 k8s/NPU 启动、真实模型生成、真实抢占、KV 释放量或 OFF/ON 压测。
- 没有证明历史吞吐收益或当前版本迁移价值；没有证明正式 BidKV 的 liveness/cascade 保护效果。
- 本地 Core metadata 为 0.23.1 / upstream 0.23.1rc0；Ascend metadata 为 0.19.1 / upstream 0.19.1rc1。它们只是所给源码的版本信息，**不是已验证可运行的配对**。
- 两个宿主目录无 Git 元数据，因此没有可核实当前 fork HEAD；文件哈希已记录，不虚填 commit。
- `runtime_effective` 单测通过仅说明证据逻辑正确，不能声称真实 NPU 已发生该事件。
- Python 3.11 及 Linux 的安装/运行未在本机实测；`requires-python>=3.11` 是源码语法/模板边界。

用户指定止于操作记录第 2 步。本报告不将任何全量历史包门禁、性能门禁或生产部署门禁标为通过。
