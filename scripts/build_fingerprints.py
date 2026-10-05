"""Regenerate guards from the pinned PR source only, never from a live host."""

import ast
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from vllm_hust_utility_victim.plugin import fingerprint  # noqa: E402


def main():
    path = ROOT / "evidence/ascend-pr39-victim_selector.py"
    source = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    expected = "a2c8ab3101f2fdbc091134eb44e13c75ebd0b4e8b3c5343d91c6d7b719589d94"
    if hashlib.sha256(source.encode()).hexdigest() != expected:
        raise RuntimeError("pinned historical source changed; refusing to regenerate guards")
    methods = {}
    for cls in ast.parse(source).body:
        if not isinstance(cls, ast.ClassDef):
            continue
        for node in cls.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            if any(isinstance(d, ast.Name) and d.id == "property" for d in node.decorator_list):
                continue
            start = min([node.lineno] + [d.lineno for d in node.decorator_list]) - 1
            methods[cls.name + "." + node.name] = fingerprint(
                "\n".join(source.splitlines()[start:node.end_lineno]))
    result = {"format": "normalized-ast-v1", "module_ast_sha256": fingerprint(source),
              "live_methods": methods}
    target = ROOT / "src/vllm_hust_utility_victim/host_fingerprints.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(result["module_ast_sha256"])


if __name__ == "__main__":
    main()
