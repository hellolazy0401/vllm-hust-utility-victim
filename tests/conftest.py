import importlib.util
import sys
from enum import Enum
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


class Policy(Enum):
    FCFS = "fcfs"
    PRIORITY = "priority"


def request(i, tokens=100, output=0, preemptions=0, arrival=1, priority=0):
    return SimpleNamespace(request_id=str(i), num_computed_tokens=tokens,
                           output_token_ids=list(range(output)), max_tokens=100,
                           num_preemptions=preemptions, arrival_time=arrival, priority=priority)


@pytest.fixture
def host(monkeypatch):
    queue = ModuleType("vllm.v1.core.sched.request_queue")
    queue.SchedulingPolicy = Policy
    req = ModuleType("vllm.v1.request")
    req.Request = object
    monkeypatch.setitem(sys.modules, queue.__name__, queue)
    monkeypatch.setitem(sys.modules, req.__name__, req)
    spec = importlib.util.spec_from_file_location(
        "fixture_ascend_selector", ROOT / "evidence/ascend-pr39-victim_selector.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for suffix in ("ENABLE", "KILL_SWITCH", "EVIDENCE"):
        monkeypatch.delenv("VLLM_HUST_UTILITY_VICTIM_" + suffix, raising=False)
