"""Patch the existing Ascend selector factory, never scheduler bookkeeping."""

from __future__ import annotations

import ast
import hashlib
import importlib
import inspect
import json
import os
import sys
import textwrap
from importlib.resources import files

PREFIX = "VLLM_HUST_UTILITY_VICTIM_"
MARKER = "__vllm_hust_utility_victim__"


def enabled() -> bool:
    # Kill switch wins, including when ENABLE contains an invalid value.
    if os.environ.get(PREFIX + "KILL_SWITCH", "0") == "1":
        return False
    value = os.environ.get(PREFIX + "ENABLE", "0")
    if value not in {"0", "1"}:
        raise ValueError(PREFIX + "ENABLE must be 0 or 1")
    kill = os.environ.get(PREFIX + "KILL_SWITCH", "0")
    if kill not in {"0", "1"}:
        raise ValueError(PREFIX + "KILL_SWITCH must be 0 or 1")
    return value == "1"


def evidence(event: str, **fields) -> None:
    if os.environ.get(PREFIX + "EVIDENCE", "0") == "1":
        print("LEGACY017_EVIDENCE " + event + " " + json.dumps(fields, sort_keys=True),
              file=sys.stderr)


def fingerprint(source: str) -> str:
    # Python 3.12 adds type_params=[] to functions/classes. Serialize fields
    # explicitly so identical non-generic source has the same hash on 3.11/3.12.
    # Non-empty type parameters remain part of the fingerprint.
    def normalize(value):
        if isinstance(value, ast.AST):
            return [type(value).__name__, [
                [name, normalize(field)] for name, field in ast.iter_fields(value)
                if not (name == "type_params" and field == [])
            ]]
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value

    canonical = json.dumps(normalize(ast.parse(textwrap.dedent(source))),
                           ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def validate_host(host) -> None:
    expected = json.loads(files(__package__).joinpath("host_fingerprints.json").read_text(encoding="utf-8"))
    try:
        if fingerprint(inspect.getsource(host)) != expected["module_ast_sha256"]:
            raise RuntimeError("unsupported Ascend selector source fingerprint")
        for name, digest in expected["live_methods"].items():
            obj = host
            for part in name.split("."):
                obj = getattr(obj, part)
            if fingerprint(inspect.getsource(obj)) != digest:
                raise RuntimeError("unsupported or already patched host method: " + name)
    except (OSError, TypeError, AttributeError, SyntaxError) as exc:
        raise RuntimeError("cannot verify Ascend selector source; refusing patch") from exc


def install(host) -> bool:
    cls = host.UnifiedVictimSelector
    factory = cls.__dict__["from_vllm_config"]
    if getattr(factory.__func__, MARKER, False):
        return False
    validate_host(host)
    original = factory.__func__

    def from_vllm_config(owner, vllm_config):
        if not enabled():
            return original(owner, vllm_config)
        from .selector import ModVictimSelector, config_from_host

        return ModVictimSelector(config_from_host(vllm_config))

    setattr(from_vllm_config, MARKER, True)
    # Mutate the class descriptor so previously imported class aliases also see it.
    cls.from_vllm_config = classmethod(from_vllm_config)
    evidence("installed", mechanism="ascend-utility-victim", source_pr="ascend#39")
    return True


def register() -> None:
    if not enabled():
        return
    backend = os.environ.get(PREFIX + "BACKEND", "ascend-legacy")
    if backend == "core-contract-v1":
        from .core_adapter import install_core

        install_core(importlib.import_module("vllm.v1.core.sched.scheduler"))
    elif backend == "ascend-legacy":
        try:
            host = importlib.import_module("vllm_ascend.core.victim_selector")
        except ModuleNotFoundError as exc:
            if exc.name != "vllm_ascend.core.victim_selector":
                raise
            raise RuntimeError(
                "Ascend legacy selector is absent. This host requires the supplied "
                "Core contract patch and VLLM_HUST_UTILITY_VICTIM_BACKEND=core-contract-v1."
            ) from exc
        install(host)
    else:
        raise ValueError("unknown utility victim backend: " + backend)
