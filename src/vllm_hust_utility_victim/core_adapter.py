"""Experimental Core contract adapter for the user's exact 0.23 snapshot."""

import inspect
import json
import sys
from importlib.resources import files

from .plugin import enabled, evidence, fingerprint
from .selector import ModVictimSelector, config_from_host


def install_core(host):
    cls = next((c for c in host.Scheduler.__mro__
                if c.__name__ == "Scheduler" and c.__module__ == "vllm.v1.core.sched.scheduler"), host.Scheduler)
    expected = json.loads(files(__package__).joinpath("core_contract.json").read_text(encoding="utf-8"))
    if getattr(cls, "hust_victim_selector_api_version", None) != 1:
        raise RuntimeError("Core lacks utility-victim contract v1. Apply the supplied exact-source host patch first.")

    def check_methods():
        for name, digest in expected["methods"].items():
            try:
                method = getattr(cls, name)
                # Do not let inspect.unwrap hide platform wrappers from the guard.
                actual = fingerprint(inspect.getsource(method.__code__))
                if name == "__init__" and actual == expected["swa_init_wrapper"]:
                    original = method.__globals__["_original_scheduler_init"]
                    actual = fingerprint(inspect.getsource(original.__code__))
            except (TypeError, OSError, AttributeError, KeyError) as exc:
                raise RuntimeError("cannot verify Core scheduler method " + name) from exc
            if actual != digest:
                raise RuntimeError("unsupported or patched Core scheduler method " + name)

    check_methods()
    previous = cls._hust_victim_selector_factory
    if getattr(previous, "__utility_core_adapter__", False):
        return False
    if previous is not None:
        raise RuntimeError("another victim selector factory is installed")

    def factory(scheduler):
        if not enabled():
            return None
        # Recheck after platform setup; Ascend may replace schedule at that stage.
        check_methods()
        config = scheduler.vllm_config
        allowed_type = type(scheduler) is cls
        if type(scheduler).__module__ == "vllm_ascend.patch.platform.patch_balance_schedule":
            wrapper = sys.modules[type(scheduler).__module__]
            if fingerprint(inspect.getsource(wrapper)) != expected["balance_module"]:
                raise RuntimeError("unknown Ascend BalanceScheduler wrapper")
            for name, digest in expected["balance_methods"].items():
                if fingerprint(inspect.getsource(getattr(type(scheduler), name))) != digest:
                    raise RuntimeError("modified Ascend BalanceScheduler method")
            allowed_type = (type(scheduler) is wrapper.BalanceScheduler
                            and not wrapper._balance_scheduling_enabled(config))
        if not allowed_type or config.scheduler_config.async_scheduling:
            raise RuntimeError("utility core adapter requires the default synchronous Scheduler; use --no-async-scheduling")
        if config.speculative_config is not None or config.kv_transfer_config is not None:
            raise RuntimeError("utility core adapter has not admitted speculative decoding or KV connectors")
        return ModVictimSelector(config_from_host(config))

    factory.__utility_core_adapter__ = True
    cls._hust_victim_selector_factory = staticmethod(factory)
    evidence("installed", mechanism="ascend-utility-victim", backend="core-contract-v1")
    return True
