import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from conftest import ROOT, Policy, request
from vllm_hust_utility_victim import plugin
from vllm_hust_utility_victim.selector import ModVictimSelector


def test_disabled_import_is_runtime_free():
    code = """
import sys
from vllm_hust_utility_victim import register
register()
assert not any(x == 'vllm' or x.startswith(('vllm.', 'vllm_ascend', 'torch')) for x in sys.modules)
assert 'vllm_hust_utility_victim.historical' not in sys.modules
"""
    # pytest's pythonpath setting affects only this process, not its children.
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    subprocess.run([sys.executable, "-c", code], check=True, env=env)


def test_kill_precedes_enable(monkeypatch):
    monkeypatch.setenv(plugin.PREFIX + "ENABLE", "invalid")
    monkeypatch.setenv(plugin.PREFIX + "KILL_SWITCH", "1")
    plugin.register()


def test_register_disabled_does_not_import(monkeypatch):
    def fail(*args):
        pytest.fail("host imported while disabled")
    monkeypatch.setattr(plugin.importlib, "import_module", fail)
    plugin.register()


def test_factory_alias_idempotence_and_kill(host, monkeypatch, capsys):
    alias = host.UnifiedVictimSelector
    original = alias.from_vllm_config
    monkeypatch.setenv(plugin.PREFIX + "ENABLE", "1")
    monkeypatch.setenv(plugin.PREFIX + "EVIDENCE", "1")
    assert plugin.install(host)
    assert not plugin.install(host)
    cfg = SimpleNamespace(additional_config={})
    selector = alias.from_vllm_config(cfg)
    assert isinstance(selector, ModVictimSelector)
    running = [request('large', 1000), request('small', 1)]
    assert selector.pick_victim(running, Policy.FCFS) is running[0]
    selector.pick_victim(running, Policy.FCFS)
    log = capsys.readouterr().err
    assert log.count('LEGACY017_EVIDENCE installed') == 1
    assert log.count('LEGACY017_EVIDENCE runtime_effective') == 1
    assert '"selection_changed": true' in log
    assert '"actual_kv_freed_verified": false' in log
    monkeypatch.setenv(plugin.PREFIX + "KILL_SWITCH", "1")
    assert selector.pick_victim(running, Policy.FCFS) is running[-1]
    assert type(alias.from_vllm_config(cfg)) is type(original(cfg))


def test_unknown_source_rejected_without_mutation(host, monkeypatch):
    original = host.UnifiedVictimSelector.from_vllm_config
    monkeypatch.setattr(plugin.inspect, "getsource", lambda x: "x = 123")
    with pytest.raises(RuntimeError, match="fingerprint"):
        plugin.install(host)
    assert host.UnifiedVictimSelector.from_vllm_config == original


def test_live_monkey_patch_rejected(host):
    host.UnifiedVictimSelector.pick_victim = lambda *a, **kw: None
    with pytest.raises(RuntimeError, match="patched host method"):
        plugin.install(host)


def test_source_unavailable_rejected(host, monkeypatch):
    def unavailable(obj):
        raise OSError("unavailable")
    monkeypatch.setattr(plugin.inspect, "getsource", unavailable)
    with pytest.raises(RuntimeError, match="cannot verify"):
        plugin.install(host)


@pytest.mark.parametrize('key', ['enable_utility_victim_selection', 'utility_kill_switch'])
def test_native_conflict(host, monkeypatch, key):
    monkeypatch.setenv(plugin.PREFIX + "ENABLE", "1")
    plugin.install(host)
    with pytest.raises(RuntimeError, match="native"):
        host.UnifiedVictimSelector.from_vllm_config(SimpleNamespace(additional_config={key: True}))
