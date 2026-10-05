# 0.1.0.dev1：WSL / Python 3.11 测试修复

用户运行目录：`D:/Desktop/mining/vllm-hust-utility-victim`（WSL：`/mnt/d/Desktop/mining/vllm-hust-utility-victim`）。修复直接落在该目录；原始交付目录未同步覆盖。

## 原因与修改

1. `ModuleNotFoundError`：pytest 的 `pythonpath=["src"]` 只作用于 pytest 进程，子进程不会继承。源码测试现在显式向子进程传递 `src` 路径；真实安装能力仍由隔离 wheel 测试验证。
2. 指纹误报：Python 3.12 的函数/类 AST 多出 `type_params=[]`，旧版直接散列 `ast.dump()`，因此相同源码在 3.11 和 3.12 得到不同指纹。改为显式规范化 AST，仅省略空 `type_params`；实际字段、非空类型参数、算法变化仍进入指纹。新增兼容及变更拒绝回归测试。
3. manifest 激活值：此目录为 `ENABLE=0`，已恢复为 `1`，表示管理器显式 enable 时注入的环境。`plugin.enabled()` 未设置开关时仍为 0，不会因安装就启用。

指纹仅由固定历史原件生成；`scripts/build_fingerprints.py` 先校验原件 SHA256，再生成跨版本一致的清单，不从未知宿主重新生成“放行”指纹。

## 实测

- 用户 WSL Python 3.11.7：37 passed，1 skipped；skip 是缺少可选 `vllm_hust_ext`。
- Windows Python 3.12.14，安装真实扩展管理器：38 passed，无 skipped。
- Ruff：通过。
- WSL Python 3.11.7 临时干净 venv：dev1 wheel 安装成功，双 entry point、资源、默认关闭导入检查通过；没有向用户 Conda 环境安装插件。

这份记录更新 `VALIDATION.md` 中初版“Linux/Python 3.11 未测试”的范围；仍没有 NPU、完整调度器或模型推理验证。

## 用户复测

```bash
cd /mnt/d/Desktop/mining/vllm-hust-utility-victim
python -m pytest tests/ -q
```

若要实际使用插件或检查 entry points，先用同一个解释器安装：

```bash
python -m pip install -e .
```

日志显示实际解释器为 `/home/hust-fjj/anaconda3/bin/python`。提示符虽为 `(vllm-test)`，仍应以 `python -c "import sys; print(sys.executable)"` 核对，避免装到另一个环境。

修复版为 `0.1.0.dev1`；`dist` 中保留的 dev0 是旧版，不要再安装旧 wheel/旧 ZIP。
修复版归档为 `dist/vllm-hust-utility-victim-0.1.0.dev1-step2.zip`，校验和在 `dist/SHA256SUMS-dev1.txt`。
