import random
from types import SimpleNamespace

import pytest

from conftest import Policy, request
from vllm_hust_utility_victim.historical import UnifiedVictimSelector, UtilityVictimSelectorConfig
from vllm_hust_utility_victim.plugin import PREFIX
from vllm_hust_utility_victim.selector import ModVictimSelector, config_from_host


@pytest.mark.parametrize('policy', [Policy.FCFS, Policy.PRIORITY])
@pytest.mark.parametrize('options', [
    {}, {'utility_kv_gate': 0.8}, {'utility_cooldown_s': 2},
    {'utility_min_running': 5}, {'utility_kill_switch': True},
    {'utility_completion_weight': 5, 'utility_preempt_weight': 7},
])
def test_differential_against_pr39(host, policy, options):
    values = dict(enable_utility_victim_selection=True, utility_snapshot_enabled=True, **options)
    original = host.UnifiedVictimSelector(host.UtilityVictimSelectorConfig.from_additional_config(values))
    extracted = UnifiedVictimSelector(UtilityVictimSelectorConfig.from_additional_config(values))
    rng = random.Random(39)
    for step in range(100):
        running = [request(i, rng.randrange(5000), rng.randrange(150), rng.randrange(6),
                           rng.randrange(3), rng.randrange(3)) for i in range(rng.randrange(1, 9))]
        kv = rng.choice([None, 0, 0.79, 0.8, 1.0])
        kwargs = dict(kv_utilization=kv, now_s=step * 0.2)
        assert extracted.pick_victim(running, policy, **kwargs) is original.pick_victim(running, policy, **kwargs)
        assert extracted.export_metrics() == original.export_metrics()
        assert extracted.get_recent_snapshots() == original.get_recent_snapshots()


def test_formula_ties_and_gates(monkeypatch, capsys):
    monkeypatch.setenv(PREFIX + 'ENABLE', '1')
    monkeypatch.setenv(PREFIX + 'EVIDENCE', '1')
    selector = ModVictimSelector(UtilityVictimSelectorConfig(
        enable_utility_victim_selection=True, utility_kv_gate=0.8,
        utility_cooldown_s=2, utility_min_running=2))
    a, b = request('a', 100, arrival=1), request('b', 100, arrival=1)
    running = [a, b]
    for kv in [None, 0.79]:
        assert selector.pick_victim(running, Policy.FCFS, kv_utilization=kv, now_s=0) is b
    assert 'runtime_effective' not in capsys.readouterr().err
    assert selector.pick_victim(running, Policy.FCFS, kv_utilization=0.8, now_s=0) is a
    assert selector.pick_victim(running, Policy.FCFS, kv_utilization=1, now_s=1) is b
    assert selector.pick_victim(running, Policy.FCFS, kv_utilization=1, now_s=2) is a
    u, _ = selector._compute_utility(tokens_freed=100, completion=1, num_preemptions=2)
    assert u == pytest.approx(100 / (1 + 0.5 + 0.6 + 1e-6))


@pytest.mark.parametrize('values', [
    {'utility_epsilon': 0}, {'utility_kv_gate': 2}, {'utility_cooldown_s': -1},
    {'utility_min_running': 0}, {'utility_completion_weight': float('nan')},
    {'utility_preempt_weight': float('inf')}, {'utility_min_running': 1.2},
    {'utility_snapshot_enabled': 'false'}, {'wrong_key': 1},
    {'enable_utility_victim_selection': True},
])
def test_invalid_configuration(values):
    with pytest.raises(ValueError):
        config_from_host(SimpleNamespace(additional_config={'utility_victim_mod': values}))


def test_runtime_input_boundaries(monkeypatch):
    monkeypatch.setenv(PREFIX + 'ENABLE', '1')
    selector = ModVictimSelector(config_from_host(SimpleNamespace(additional_config={})))
    with pytest.raises(ValueError, match='empty'):
        selector.pick_victim([], Policy.FCFS)
    with pytest.raises(ValueError, match='duplicate'):
        selector.pick_victim([request('x'), request('x')], Policy.FCFS)
    with pytest.raises(ValueError, match='finite'):
        selector.pick_victim([request('x')], Policy.FCFS, kv_utilization=float('nan'))
