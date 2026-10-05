"""Generate a reviewable exact-snapshot patch; never modify Source originals."""

import ast
import difflib
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from vllm_hust_utility_victim.plugin import fingerprint  # noqa: E402


def method_sources(source, class_name):
    cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == class_name)
    return {n.name: "\n".join(source.splitlines()[min([n.lineno] + [d.lineno for d in n.decorator_list])-1:n.end_lineno])
            for n in cls.body if isinstance(n, ast.FunctionDef)}


def main():
    source_root = Path(sys.argv[1])
    path = source_root / "vllm/vllm/v1/core/sched/scheduler.py"
    before = path.read_text(encoding="utf-8")
    after = before.replace("class Scheduler(SchedulerInterface):\n", "class Scheduler(SchedulerInterface):\n    hust_victim_selector_api_version = 1\n    _hust_victim_selector_factory = None\n\n", 1)
    anchor = "        self.vllm_config = vllm_config\n"
    after = after.replace(anchor, anchor + "        factory = type(self)._hust_victim_selector_factory\n        self._hust_victim_selector = factory(self) if factory else None\n", 1)
    old = '''                    if self.policy == SchedulingPolicy.PRIORITY:
                        preempted_req = max(
                            self.running,
                            key=lambda r: (r.priority, r.arrival_time),
                        )
'''
    new = '''                    if (
                        self._hust_victim_selector is not None
                        or self.policy == SchedulingPolicy.PRIORITY
                    ):
                        if self._hust_victim_selector is not None:
                            preempted_req = self._hust_victim_selector.pick_victim(
                                self.running,
                                self.policy,
                                kv_utilization=self.kv_cache_manager.usage,
                                now_s=scheduled_timestamp,
                            )
                            if not any(r is preempted_req for r in self.running):
                                raise RuntimeError("Invalid victim selector result")
                            victim_index = self.running.index(preempted_req)
                            if (
                                victim_index < req_index
                                and preempted_req not in scheduled_running_reqs
                            ):
                                req_index -= 1
                        else:
                            preempted_req = max(
                                self.running,
                                key=lambda r: (r.priority, r.arrival_time),
                            )
'''
    assert after.count(old) == 1
    after = after.replace(old, new, 1)
    ast.parse(after)
    out = ROOT / "host_patch"
    out.mkdir(exist_ok=True)
    (out / "scheduler.before.py").write_text(before, encoding="utf-8")
    (out / "scheduler.after.py").write_text(after, encoding="utf-8")
    (out / "core-0.23-victim-contract.patch").write_text("".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile="a/vllm/v1/core/sched/scheduler.py", tofile="b/vllm/v1/core/sched/scheduler.py")), encoding="utf-8")
    balance = (source_root / "vllm-ascend/vllm_ascend/patch/platform/patch_balance_schedule.py").read_text(encoding="utf-8")
    (out / "balance.reference.py").write_text(balance, encoding="utf-8")
    metadata = {"source": str(path), "before_sha256": hashlib.sha256(before.encode()).hexdigest(),
                "after_sha256": hashlib.sha256(after.encode()).hexdigest(),
                "methods": {k: fingerprint(v) for k, v in method_sources(after, "Scheduler").items()
                            if k in {"__init__", "schedule", "_preempt_request"}},
                "balance_module": fingerprint(balance),
                "balance_methods": {k: fingerprint(v) for k, v in method_sources(balance, "BalanceScheduler").items() if k in {"__init__", "schedule"}}}
    swa = (source_root / "vllm-ascend/vllm_ascend/patch/platform/patch_async_swa_kv_lifetime.py").read_text(encoding="utf-8")
    (out / "swa.reference.py").write_text(swa, encoding="utf-8")
    node = next(n for n in ast.parse(swa).body if isinstance(n, ast.FunctionDef) and n.name == "_patched_scheduler_init")
    start = min([node.lineno] + [d.lineno for d in node.decorator_list]) - 1
    metadata["swa_init_wrapper"] = fingerprint("\n".join(swa.splitlines()[start:node.end_lineno]))
    (ROOT / "src/vllm_hust_utility_victim/core_contract.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (out / "identity.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print("Generated reviewable host patch and guards; Source untouched")


if __name__ == "__main__":
    main()
