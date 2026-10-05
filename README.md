# vllm-hust-utility-victim

Standalone, default-off vLLM `general_plugin` that uses **utility-based victim selection**
at an existing preemption point. It chooses which running request to preempt; the host
retains responsibility for releasing state, recomputation, and resuming requests.

This is one mechanism extracted from
[Ascend PR #39](https://github.com/intellistream/vllm-ascend-hust-legacy-20260831/pull/39),
merge commit `76d8939d7e21d17a295adf99e9dda17bde5a88cc`. This package does **not** import
`vllm-hust-legacy017-perf`, BidKV, or vSpec at runtime. It does not implement Prefix Routing.

**For the tested container, the wheel alone is insufficient:** dev2 requires the included,
source-guarded Core contract patch and the `core-contract-v1` backend.

## Status: candidate, not performance-admitted

Packaging and runtime reachability are established; a serving speedup is not.
The retained **r1** experiment used Qwen3.5-35B-A3B, 2 × Ascend 910B2, TP2 + EP,
vLLM `0.23.0+empty`, vLLM-Ascend `0.23.0.post1`, and this package `0.1.0.dev2`.
Version/hardware snapshots are available for ON; the corresponding OFF snapshots are missing.

- **Algorithm fidelity (tested).** 1,200 decisions compare the extracted selector with
  the preserved historical implementation, including victims, metrics, and snapshots.
  This is fidelity to historical utility selection, not equivalence to default FCFS.
  The current local CPU suite passed **48 tests** on 2026-10-05. The retained Linux dev2
  log records 47 passed and 1 skipped (the optional extension-manager check).
- **Reachability (measured).** ON-r1 emitted `runtime_effective` from EngineCore with
  `selection_changed=true`; OFF emitted no utility runtime event. This proves at least
  one changed selection, not the total number of changed decisions.
- **Serving effect (one OFF/ON pair).** `swe-prefix-reuse` 0.1.2, C16, 900-second window,
  memory utilization 0.65, synchronous FCFS, prefix caching off, no configured MTP:

  | Metric | OFF-r1 | ON-r1 | ON vs OFF |
  | --- | ---: | ---: | ---: |
  | Output throughput, tokens/s, both chips | 172.520 | 146.997 | **−14.79%** |
  | Output throughput, tokens/s/chip | 86.260 | 73.498 | **−14.79%** |
  | Decode speed P90, tokens/s | 19.119 | 19.158 | +0.21% |
  | TTFT P95, ms | 9829.22 | 5973.18 | **−39.23%** |
  | TPOT mean, ms | 82.15 | 98.85 | **+20.33%** |
  | TPOT P95, ms | 153.90 | 286.97 | **+86.46%** |
  | E2E P95, ms | 112872.77 | 117356.59 | +3.97% |
  | Preemptions, including drain | 311 | 188 | −39.55% |

  Both runs were valid with zero failed requests. Lower TTFT and fewer preemptions came
  with lower throughput and worse TPOT. **This is a measured tradeoff, not an overall
  performance improvement.** One pair cannot establish repeatability or causal attribution.
  r2/r3 are explicitly excluded from this evaluation.

Throughput counts output received inside the 900-second window. Latency statistics use
requests successfully completed in that window; preemption counters include drain.
TPOT is `(E2E − TTFT) / (output_tokens − 1)`, not the inverse of decode speed P90.
The largest observed prompt was 40,244 tokens: a configured 262,144-token limit is not
evidence of a full-256K test. The workload does not evaluate answer quality.

Full results and limitations are in the [project report](docs/REPORT.md).
No independent selector microbenchmark or historical end-to-end performance fidelity result
is claimed. Earlier CPU-only documents describe earlier stages, not the current evidence.

## How victim selection works

After the host reaches its victim-selection path, the selector applies its gates and
ranks running requests using the historical defaults:

```text
utility = max(computed_tokens, 0)
          / max(1 + 0.5 * completion + 0.3 * preemptions + epsilon, epsilon)
completion = clamp(output_tokens / max_tokens, 0, 1)
epsilon = 1e-6
```

The highest score is selected; ties use ascending arrival time and request ID.
Defaults are `utility_kv_gate=0`, `utility_cooldown_s=0`, and `utility_min_running=1`.
These gates are configurable. The selector does not initiate preemption or require
additional pressure beyond the host's entry condition under the defaults.

`computed_tokens` estimates potential release, not actual freed bytes. Fewer preemptions
can still involve more expensive victims; actual recomputation cost and fairness remain
unverified. The historical per-request metrics dictionary also needs long-run memory testing.

## The current host needs a selection contract

Two host paths must be distinguished:

- **`ascend-legacy`** (default backend) replaces the existing
  `UnifiedVictimSelector.from_vllm_config` factory on a matching legacy host.
  The original local legacy target already contained an equivalent algorithm; extraction
  there is an ablation facility, not a newly introduced optimization.
- **`core-contract-v1`** (used in r1) requires the included Core patch because the container
  Source snapshot lacks that factory. The patch adds an optional factory and selection
  call, preserves the original OFF branch, and handles cursor and budget bookkeeping
  when utility selects an arbitrary running request. Actual preemption remains in the host.

This is a local experimental contract, **not** upstream PreemptionPolicy v1.
The adapter checks pinned source and known Ascend wrappers. It rejects unsupported async
scheduling, incompatible custom schedulers, speculative decoding, and KV connectors.
The declared `>=0.23,<0.24` version range alone does not establish compatibility.

## Scope and differences from the historical patch

- `historical.py` preserves the algorithm, gates, and statistics with minimal type/import
  adaptation, allowing CPU tests without vLLM or torch.
- Integration adds default-off activation, kill-switch priority, idempotency, source guards,
  configuration validation, and evidence events.
- The dev2 Core contract is new integration work, not part of the original Ascend PR.
  It must be reviewed alongside the wheel.
- [Core PR #171](https://github.com/intellistream/vllm-hust-legacy-20260831/pull/171)
  is a related interface, not another algorithm bundled here. Its separate victim-selector
  entry point is not installed.
- Prefix Routing, scheduling liveness fixes, and later BidKV cascade/liveness protections
  are outside scope. No historical aggregate speedup is inherited.

See the [source mapping](docs/MAPPING.md) and [selection rationale](docs/SELECTION.md).
Their early legacy-host observations do not describe the dev2 container target.

## Installation and activation

Requires Python 3.11+. From this project directory, in the serving Python environment:

```bash
python -m pip install .

# Stop the serving process before applying the host patch.
# Check compatibility first; do not bypass a mismatch.
python scripts/apply_core_contract.py --core-root /vllm-workspace/vllm
python scripts/apply_core_contract.py --core-root /vllm-workspace/vllm --apply
```

The patcher checks source identity and creates a backup. Use the actual container checkout
path. A prebuilt wheel does not replace this host-patching step.

With a compatible `vllm-hust-ext` manager already installed in the serving environment:

```bash
export VLLM_HUST_UTILITY_VICTIM_ENABLE=1
export VLLM_HUST_UTILITY_VICTIM_KILL_SWITCH=0
export VLLM_HUST_UTILITY_VICTIM_BACKEND=core-contract-v1
export VLLM_HUST_UTILITY_VICTIM_EVIDENCE=1
export VLLM_ASCEND_BALANCE_SCHEDULING=0

vllm-hust-ext extension enable org.vllm-hust.utility-victim
vllm-hust-ext extension list
```

Launch through `vllm-hust-ext run -- vllm serve ...` with `--no-async-scheduling` and the
appropriate model/device settings. The manager and Ascend runtime are separate prerequisites;
this package does not install them. See [container adaptation](docs/CONTAINER_023.md) for
offline installation and the precise host restrictions.

| Variable | Effect |
| --- | --- |
| `VLLM_HUST_UTILITY_VICTIM_KILL_SWITCH=1` | Always wins; prevents installation at process startup. |
| `VLLM_HUST_UTILITY_VICTIM_ENABLE=1` | Required to install. Defaults to 0; disabled registration imports no host module. |
| `VLLM_HUST_UTILITY_VICTIM_BACKEND` | Defaults to `ascend-legacy`; set `core-contract-v1` for the patched container. |
| `VLLM_HUST_UTILITY_VICTIM_EVIDENCE=1` | Emits `installed` and the first utility `runtime_effective` event per selector instance. |

The manifest injects `ENABLE=1` when an enabled extension is launched through
`vllm-hust-ext run`; it does not force kill=0. Enabling an extension does not alter an
already running server. Restart between OFF and ON runs.

Optional host `additional_config` settings belong under `utility_victim_mod`:

```json
{"utility_victim_mod":{"utility_kv_gate":0.8,"utility_cooldown_s":0.1,"utility_min_running":2}}
```

These are example overrides, **not** the r1 configuration. Conflicting native utility
enable/kill settings are rejected instead of silently combining two control paths.

## Evidence and OFF/ON reproduction

`LEGACY017_EVIDENCE installed` reports integration installation.
`runtime_effective` reports that utility selection ran; `selection_changed` compares that
decision with fallback. `actual_kv_freed_verified=false` explicitly limits the claim.
Neither event proves actual KV release or throughput improvement. Event counts are not
preemption counts; use the host counter `vllm:num_preemptions_total` for the latter.

For the r1 configuration, after preparing the Ascend environment and enabling the extension,
launch one group at a time:

```bash
KV_MEMORY_FRACTION=0.65 bash scripts/start_swe_ab.sh off /models/Qwen3.5-35B-A3B
# Stop OFF and wait for exit before launching ON:
KV_MEMORY_FRACTION=0.65 bash scripts/start_swe_ab.sh on /models/Qwen3.5-35B-A3B
```

Use a real model path. Both groups retain the same Core patch and parameters; OFF uses
kill=1, ON kill=0. This compares activation, not patched versus pristine Core.
The older `start_qwen35_utility.sh` forces kill=0 and must not be used for OFF.

Use the same prepared workload, C16, 900 seconds, and two chips. The
[OFF/ON guide](docs/SWE_OFF_ON.md) covers client setup, strict token-protocol qualification,
metadata, and monitoring. Wait for drain before stopping the server. Memory fraction 0.65
is this experiment's pressure setting, not a general recommendation.

Recompute the retained r1 tables without accelerator dependencies:

```bash
python scripts/summarize_report.py
```

This reads `results/`, writes [report-data.json](docs/report-data.json), and leaves raw data
unchanged. It checks request counts, window tokens, TTFT P95, process-start snapshots, and
server/client full-run token totals. Original fingerprints are in
[report-r1-SHA256SUMS.txt](docs/report-r1-SHA256SUMS.txt).

## Testing and building

```bash
python -m pip install -e '.[test]'
python -m pytest tests -q
python -m ruff check src tests scripts
python -m build
```

Tests do not require torch, vLLM, or NPU hardware. The optional manager test skips if
`vllm_hust_ext` is absent. Tests cover historical differential decisions, activation,
source guards, manifests, Core bookkeeping, and patch/restore. They do not replace full
serving correctness or performance validation.

`evidence/ascend-pr39-victim_selector.py` is the preserved algorithm reference.
Historical `evidence/build.txt` records **dev0**, not a fresh dev2 build. Historical and
current validation results are distinguished in the [report](docs/REPORT.md).
An installable package is not evidence of publication to PyPI.

## Rollback and remaining work

For a complete rollback, stop the service, then use the serving environment:

```bash
export VLLM_HUST_UTILITY_VICTIM_KILL_SWITCH=1
vllm-hust-ext extension disable org.vllm-hust.utility-victim
python scripts/apply_core_contract.py --core-root /vllm-workspace/vllm --restore
```

Restore verifies the patched file and backup before writing. Restart with the appropriate
original serving command; do not use an ON script that resets the kill switch.
Changing a variable in another shell does not alter a running process.

Pending work includes repeated OFF/ON runs, a no-preemption negative control, actual release
and recomputation measurements, fairness and long-run memory testing, and complete provenance.
The r1 configs have `server_metadata=null`; the prepared workload hash is recorded but its
file still needs to be archived locally. Remote repository, PR, and PyPI publication are
not established by the retained evidence.

Concrete follow-up steps are in [the report, section 10](docs/REPORT.md).
Code is licensed under [Apache-2.0](LICENSE); see [NOTICE](NOTICE) for attribution.
