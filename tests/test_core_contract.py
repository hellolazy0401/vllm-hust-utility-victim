import ast
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pytest

from conftest import ROOT, Policy, request
from vllm_hust_utility_victim.core_adapter import install_core
from vllm_hust_utility_victim.historical import UtilityVictimSelectorConfig
from vllm_hust_utility_victim.plugin import PREFIX
from vllm_hust_utility_victim.selector import ModVictimSelector


def choose_block(source):
    tree = ast.parse(source)
    schedule = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "schedule")
    return next(n for n in ast.walk(schedule) if isinstance(n, ast.If)
                and "preempted_req = max" in ast.unparse(n)
                and ("self.policy == SchedulingPolicy.PRIORITY" == ast.unparse(n.test)
                     or "self._hust_victim_selector is not None" in ast.unparse(n.test)))


def execute_selection(patched, running, selector, scheduled, policy=Policy.FCFS):
    source = (ROOT / "host_patch" / ("scheduler.after.py" if patched else "scheduler.before.py")).read_text(encoding="utf-8")
    node = choose_block(source)
    scheduler = SimpleNamespace(running=running[:], policy=policy, _hust_victim_selector=selector,
                                kv_cache_manager=SimpleNamespace(usage=0.95))
    ns = dict(self=scheduler, SchedulingPolicy=Policy, scheduled_running_reqs=scheduled[:],
              num_scheduled_tokens={r.request_id: 7 for r in scheduled}, token_budget=3,
              req_to_new_blocks={r.request_id: object() for r in scheduled},
              scheduled_spec_decode_tokens={r.request_id: [5] for r in scheduled},
              scheduled_encoder_inputs={r.request_id: [0] for r in scheduled},
              encoder_compute_budget=2, req_index=1, scheduled_timestamp=10)
    exec(compile(ast.Module(body=[node], type_ignores=[]), "selection-block", "exec"), ns)
    return ns


def test_utility_reclaims_already_scheduled_budgets(monkeypatch):
    monkeypatch.setenv(PREFIX + "ENABLE", "1")
    a, b = request("large", 1000), request("tail", 1)
    a.get_num_encoder_embeds = lambda i: 11
    selector = ModVictimSelector(UtilityVictimSelectorConfig(enable_utility_victim_selection=True))
    result = execute_selection(True, [a, b], selector, [a])
    assert result["preempted_req"] is a
    assert result["self"].running == [b]
    assert result["token_budget"] == 10
    assert result["encoder_compute_budget"] == 13
    assert result["req_index"] == 0
    for key in ("num_scheduled_tokens", "req_to_new_blocks", "scheduled_spec_decode_tokens", "scheduled_encoder_inputs"):
        assert result[key] == {}
    assert result["scheduled_running_reqs"] == []


@pytest.mark.parametrize("policy", [Policy.FCFS, Policy.PRIORITY])
def test_off_selection_exactly_matches_original(policy):
    a, b = request("a", priority=2), request("b", priority=0)
    a.get_num_encoder_embeds = lambda i: 11
    original = execute_selection(False, [a, b], None, [a], policy)
    patched = execute_selection(True, [a, b], None, [a], policy)
    for key in ("preempted_req", "token_budget", "encoder_compute_budget", "req_index", "scheduled_running_reqs"):
        assert original[key] == patched[key]
    assert original["self"].running == patched["self"].running


def test_invalid_victim_rejected_before_queue_mutation():
    a = request("a")
    invalid = SimpleNamespace(pick_victim=lambda *a, **kw: request("other"))
    with pytest.raises(RuntimeError, match="Invalid victim"):
        execute_selection(True, [a], invalid, [])


def test_earlier_unscheduled_victim_preserves_loop_cursor(monkeypatch):
    monkeypatch.setenv(PREFIX + "ENABLE", "1")
    earlier, current = request("earlier", 1000), request("current", 1)
    selector = ModVictimSelector(UtilityVictimSelectorConfig(enable_utility_victim_selection=True))
    result = execute_selection(True, [earlier, current], selector, [])
    assert result["preempted_req"] is earlier
    assert result["req_index"] == 0
    assert result["self"].running == [current]
    assert result["token_budget"] == 3


@pytest.fixture
def core_host(monkeypatch):
    path = ROOT / "host_patch/scheduler.after.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Scheduler")
    # Only compile the guarded methods, not imports or GPU-dependent constructors.
    cls.body = [n for n in cls.body if not isinstance(n, ast.FunctionDef)
                or n.name in {"__init__", "schedule", "_preempt_request"}]
    module = ModuleType("vllm.v1.core.sched.scheduler")
    module.__file__ = str(path)
    module.SchedulerInterface = object
    module.MULTIMODAL_REGISTRY = None
    monkeypatch.setitem(sys.modules, module.__name__, module)
    # Compile original AST to keep inspect source lines pointing at the real snapshot.
    future = ast.parse("from __future__ import annotations").body[0]
    exec(compile(ast.Module(body=[future, cls], type_ignores=[]), str(path), "exec"), module.__dict__)
    return module


def test_core_factory_and_kill(core_host, monkeypatch):
    monkeypatch.setenv(PREFIX + "ENABLE", "1")
    assert install_core(core_host)
    assert not install_core(core_host)
    instance = core_host.Scheduler.__new__(core_host.Scheduler)
    instance.vllm_config = SimpleNamespace(scheduler_config=SimpleNamespace(async_scheduling=False),
                                          speculative_config=None, kv_transfer_config=None, additional_config={})
    factory = core_host.Scheduler._hust_victim_selector_factory
    assert isinstance(factory(instance), ModVictimSelector)
    instance.vllm_config.scheduler_config.async_scheduling = True
    with pytest.raises(RuntimeError, match="synchronous"):
        factory(instance)
    monkeypatch.setenv(PREFIX + "KILL_SWITCH", "1")
    assert factory(instance) is None


def test_core_late_schedule_replacement_rejected(core_host, monkeypatch):
    monkeypatch.setenv(PREFIX + "ENABLE", "1")
    install_core(core_host)
    core_host.Scheduler.schedule = lambda self: None
    with pytest.raises(RuntimeError, match="patched Core"):
        core_host.Scheduler._hust_victim_selector_factory(SimpleNamespace())


def test_actual_swa_init_wrapper_is_verified(core_host, monkeypatch):
    import functools
    monkeypatch.setenv(PREFIX + "ENABLE", "1")
    path = ROOT / "host_patch/swa.reference.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    wrapper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_patched_scheduler_init")
    namespace = {"wraps": functools.wraps, "_original_scheduler_init": core_host.Scheduler.__init__}
    body = [ast.parse("from __future__ import annotations").body[0], wrapper]
    exec(compile(ast.Module(body=body, type_ignores=[]), str(path), "exec"), namespace)
    core_host.Scheduler.__init__ = namespace["_patched_scheduler_init"]
    assert install_core(core_host)
    namespace["_original_scheduler_init"] = lambda *a, **kw: None
    with pytest.raises(RuntimeError, match="patched Core"):
        install_core(core_host)


def test_actual_ascend_balance_wrapper_admission(core_host, monkeypatch):
    monkeypatch.setenv(PREFIX + "ENABLE", "1")
    monkeypatch.setenv("VLLM_ASCEND_BALANCE_SCHEDULING", "0")
    path = ROOT / "host_patch/balance.reference.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    body = [ast.parse("from __future__ import annotations").body[0]]
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_balance_scheduling_enabled":
            body.append(node)
        if isinstance(node, ast.ClassDef) and node.name == "BalanceScheduler":
            node.body = [n for n in node.body if isinstance(n, ast.FunctionDef)
                         and n.name in {"__init__", "schedule"}]
            body.append(node)
    wrapper = ModuleType("vllm_ascend.patch.platform.patch_balance_schedule")
    wrapper.__file__ = str(path)
    wrapper.Scheduler = core_host.Scheduler
    wrapper.MULTIMODAL_REGISTRY = None
    import os
    wrapper.os = os
    monkeypatch.setitem(sys.modules, wrapper.__name__, wrapper)
    exec(compile(ast.Module(body=body, type_ignores=[]), str(path), "exec"), wrapper.__dict__)
    core_host.Scheduler = wrapper.BalanceScheduler
    assert install_core(core_host)
    instance = wrapper.BalanceScheduler.__new__(wrapper.BalanceScheduler)
    instance.vllm_config = SimpleNamespace(scheduler_config=SimpleNamespace(async_scheduling=False),
                                          speculative_config=None, kv_transfer_config=None, additional_config={})
    factory = wrapper.BalanceScheduler._hust_victim_selector_factory
    assert isinstance(factory(instance), ModVictimSelector)
    instance.vllm_config.additional_config["enable_balance_scheduling"] = True
    with pytest.raises(RuntimeError, match="synchronous"):
        factory(instance)


def test_patch_round_trip_and_unknown_source(tmp_path):
    target = tmp_path / "vllm/v1/core/sched/scheduler.py"
    target.parent.mkdir(parents=True)
    original = (ROOT / "host_patch/scheduler.before.py").read_bytes()
    target.write_bytes(original)
    command = [sys.executable, str(ROOT / "scripts/apply_core_contract.py"), "--core-root", str(tmp_path)]
    subprocess.run(command + ["--apply"], check=True)
    assert target.read_bytes() == (ROOT / "host_patch/scheduler.after.py").read_bytes()
    subprocess.run(command + ["--apply"], check=True)
    subprocess.run(command + ["--restore"], check=True)
    assert target.read_bytes() == original
    target.write_text("x=1", encoding="utf-8")
    assert subprocess.run(command + ["--apply"], capture_output=True).returncode != 0
    assert target.read_text() == "x=1"
