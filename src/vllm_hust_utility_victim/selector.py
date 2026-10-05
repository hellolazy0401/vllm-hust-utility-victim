"""Activation, validation and evidence around the extracted historical algorithm."""

from __future__ import annotations

import math
from dataclasses import fields

from .historical import UnifiedVictimSelector, UtilityVictimSelectorConfig
from .plugin import enabled, evidence


def config_from_host(vllm_config) -> UtilityVictimSelectorConfig:
    additional = getattr(vllm_config, "additional_config", None) or {}
    if additional.get("enable_utility_victim_selection"):
        raise RuntimeError("native utility is enabled; disable it before enabling this mod")
    if additional.get("utility_kill_switch"):
        raise RuntimeError("native utility_kill_switch is set; refusing to override it")
    values = additional.get("utility_victim_mod", {})
    if not isinstance(values, dict):
        raise ValueError("utility_victim_mod must be an object")
    allowed = {f.name for f in fields(UtilityVictimSelectorConfig)} - {
        "enable_utility_victim_selection", "utility_kill_switch"
    }
    if set(values) - allowed:
        raise ValueError("unknown or activation field in utility_victim_mod")
    defaults = UtilityVictimSelectorConfig()
    for key, value in values.items():
        default = getattr(defaults, key)
        if isinstance(default, bool):
            valid = isinstance(value, bool)
        elif isinstance(default, int):
            valid = type(value) is int
        else:
            valid = type(value) in (int, float) and math.isfinite(value)
        if not valid:
            raise ValueError("invalid type or non-finite value: " + key)
    return UtilityVictimSelectorConfig.from_additional_config({
        **values, "enable_utility_victim_selection": True, "utility_kill_switch": False
    })


class ModVictimSelector(UnifiedVictimSelector):
    @property
    def _utility_enabled(self) -> bool:
        return enabled() and super()._utility_enabled

    def pick_victim(self, running, policy, *, kv_utilization=None, now_s=None):
        # Fail closed on invalid runtime measurements rather than treating NaN as pressure.
        if kv_utilization is not None and (
            not math.isfinite(kv_utilization) or not 0 <= kv_utilization <= 1
        ):
            raise ValueError("kv_utilization must be finite and in [0, 1]")
        if now_s is not None and not math.isfinite(now_s):
            raise ValueError("now_s must be finite")
        if len({r.request_id for r in running}) != len(running):
            raise ValueError("duplicate request IDs")
        before = self._utility_strategy_hits
        victim = super().pick_victim(running, policy, kv_utilization=kv_utilization, now_s=now_s)
        if self._utility_strategy_hits > before and not getattr(self, "_evidence_emitted", False):
            default = self._pick_default_victim(running, policy)
            evidence("runtime_effective", mechanism="ascend-utility-victim",
                     selection_changed=victim is not default,
                     tokens_proxy=max(int(victim.num_computed_tokens), 0),
                     scope="victim_selection_only", actual_kv_freed_verified=False)
            self._evidence_emitted = True
        return victim
