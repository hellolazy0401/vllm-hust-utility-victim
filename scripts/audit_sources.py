"""Record read-only local source identities; never infer a fork HEAD from its anchor."""

import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path


def identity(path):
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--documents", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    historical = root / "evidence/ascend-pr39-victim_selector.py"
    target = args.workspace / "vllm-ascend-hust/vllm_ascend/core/victim_selector.py"
    same = ast.dump(ast.parse(historical.read_text(encoding="utf-8"))) == ast.dump(
        ast.parse(target.read_text(encoding="utf-8")))
    relative = [
        "vllm-ascend-hust/vllm_ascend/core/victim_selector.py",
        "vllm-ascend-hust/vllm_ascend/core/recompute_scheduler.py",
        "vllm-ascend-hust/vllm_ascend/core/scheduler_dynamic_batch.py",
        "vllm-ascend-hust/vllm_ascend/core/scheduler_profiling_chunk.py",
        "vllm-ascend-hust/vllm_ascend/patch/platform/patch_balance_schedule.py",
        "vllm-hust/vllm/v1/core/sched/victim_selector.py",
        "vllm-hust/vllm/v1/core/sched/scheduler.py",
    ]
    rows = []
    for path in relative:
        p = args.workspace / path
        text = p.read_text(encoding="utf-8")
        rows.append({**identity(p), "relative_path": path, "factory_call_lines": [
            i for i, line in enumerate(text.splitlines(), 1)
            if "UnifiedVictimSelector.from_vllm_config(" in line]})
    prs = []
    for repo, number, role in [
        ("vllm-ascend-hust-legacy-20260831", 39, "algorithm_source"),
        ("vllm-hust-legacy-20260831", 171, "related_interface_not_installed"),
    ]:
        path = root / f"evidence/{repo}-pr-{number}.json"
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        prs.append({"repository": "intellistream/" + repo, "number": number,
                    "role": role, "author": data["user"]["login"],
                    "url": data["html_url"], "merge_sha": data["merge_commit_sha"],
                    "merged_at": data["merged_at"], "evidence": str(path.relative_to(root))})
    mapping = {
        "date": "2026-10-01", "mechanism_id": "ascend-utility-victim-selection",
        "distribution": "vllm-hust-utility-victim", "version": "0.1.0.dev2",
        "extension_id": "org.vllm-hust.utility-victim", "prs": prs,
        "historical_source": identity(historical),
        "source_core": "1aa7cd10b7b16e82fdb29fcc47d3a3cd93bd01dc",
        "source_core_role": "reported_historical_context_not_algorithm_source",
        "source_ascend": prs[0]["merge_sha"],
        "historical_ascend_pair": "03ae1d03db8049cd2a5c3f824039814459542e25",
        "current_algorithm_disposition": "builtin" if same else "requires_review",
        "current_selector_ast_equal_to_pr39": same,
        "delivery_disposition": "packaged_extraction_for_ablation",
        "current_host_git_head": None,
        "current_host_git_head_note": "Local source directories have no .git; anchors are not fork HEADs.",
        "local_hosts": rows,
        "upstream_metadata": {name: json.loads((args.workspace / name / "upstream_version.json").read_text())
                              for name in ["vllm-hust", "vllm-ascend-hust"]},
        "template_files": [identity(args.template / p) for p in ["pyproject.toml", "src/vllm_hust_vspec/manifests/vllm-hust-extension-v0.2.json"]],
        "input_documents": [identity(p) for p in sorted(args.documents.iterdir()) if p.is_file()],
        "evidence_ids": ["LOCAL-UV-001", "LOCAL-UV-002", "LOCAL-UV-003"],
        "runtime_validation": "not_run", "performance_validation": "not_run",
        "test_scope": "CPU stubs and frozen historical implementation, not full scheduler/NPU integration",
    }
    (root / "docs/mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    with (root / "docs/mapping.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["mechanism", "pr", "commit", "role", "mod", "test"])
        writer.writeheader()
        for pr in prs:
            writer.writerow(dict(mechanism=mapping["mechanism_id"], pr=pr["url"], commit=pr["merge_sha"],
                                 role=pr["role"], mod="historical.py + selector.py + plugin.py" if pr["number"] == 39 else "not installed",
                                 test="tests/test_selector.py; tests/test_activation.py" if pr["number"] == 39 else "source comparison only"))
    assert same, "Target selector differs from the selected historical source"
    assert all(row["factory_call_lines"] for row in rows[1:5])
    print("LOCAL-UV-002: AST equal; all four Ascend factory call sites present; input hashes recorded")


if __name__ == "__main__":
    main()
