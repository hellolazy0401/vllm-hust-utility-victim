"""Audit only r1 in utility-c1-c16-m65; preserve original files."""
import hashlib
import json
import re
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/utility-c1-c16-m65'


def q(values, fraction):
    values = sorted(values)
    if not values:
        return None
    index = (len(values) - 1) * fraction
    lo = int(index)
    return values[lo] + (values[min(lo + 1, len(values) - 1)] - values[lo]) * (index - lo)


def metrics(path, name):
    found = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        m = re.match(r'^(' + re.escape(name) + r'(?:\{[^}]*\})?)\s+(\S+)', line)
        if m:
            found[m[1]] = float(m[2])
    return found


def main():
    result = []
    for c in (1, 2, 4, 8, 16):
        for mode in ('off', 'on'):
            name = f'{mode}-m65-c{c}-r1'
            folder = BASE / name
            config = json.loads((folder / 'config.json').read_text())
            s = json.loads((folder / 'summary.json').read_text())
            raw = folder / 'requests.jsonl'
            rows = [json.loads(line) for line in raw.read_text().splitlines()]
            complete = [r for r in rows if r['success'] and r['end'] <= s['measurement_seconds']]
            assert len(complete) == s['requests_completed_in_window']
            assert len(rows) == s['requests_started']
            assert sum(n for r in rows for t, n in r['chunks'] if t <= s['measurement_seconds']) == s['observed_output_tokens_in_window']
            assert abs(q([r['ttft_seconds'] for r in complete], .95) - s['ttft_seconds_p95']) < 1e-8
            deltas = {}
            for key in ('vllm:num_preemptions_total', 'vllm:request_success_total',
                        'vllm:prompt_tokens_total', 'vllm:generation_tokens_total',
                        'process_start_time_seconds'):
                before = metrics(BASE / (name + '.before.prom'), key)
                after = metrics(BASE / (name + '.after.prom'), key)
                assert before and before.keys() == after.keys(), name
                deltas[key] = sum(after[k] - before[k] for k in before)
            assert deltas['process_start_time_seconds'] == 0
            checks = {
                'success_count_matches': deltas['vllm:request_success_total'] == len(rows),
                'input_count_matches': deltas['vllm:prompt_tokens_total'] == sum(r['prompt_tokens'] for r in rows),
                'output_count_matches': deltas['vllm:generation_tokens_total'] == sum(len(r['token_ids']) for r in rows),
            }
            log = (BASE / (name + '.server.log')).read_text(encoding='utf-8', errors='replace')
            events = [json.loads(x) for x in re.findall(r'LEGACY017_EVIDENCE runtime_effective (\{[^\n]*\})', log)]
            tpots = [(r['e2e_seconds'] - r['ttft_seconds']) * 1000 / (len(r['token_ids']) - 1)
                     for r in complete if len(r['token_ids']) > 1]
            probe = json.loads((BASE / (name + '-probe') / 'summary.json').read_text())
            item = dict(name=name, concurrency=c, mode=mode, summary=s, config=config,
                        ttft_p50_ms=q([r['ttft_seconds'] * 1000 for r in complete], .5),
                        tpot_mean_ms=mean(tpots), tpot_p95_ms=q(tpots, .95),
                        e2e_p95_ms=q([r['e2e_seconds'] * 1000 for r in complete], .95),
                        deltas=deltas, counter_checks=checks, runtime_events=events,
                        installed_events=log.count('LEGACY017_EVIDENCE installed'),
                        probe_valid=probe['valid'], probe_seconds=probe['measurement_seconds'],
                        exit_code=(BASE / (name + '.exit-code.txt')).read_text().strip(),
                        requests_sha256=hashlib.sha256(raw.read_bytes()).hexdigest())
            result.append(item)
            print(name, 'tps', s['output_tokens_per_second'], 'preempts', deltas['vllm:num_preemptions_total'],
                  'events', len(events), 'checks', checks, 'TPOT', item['tpot_mean_ms'], item['tpot_p95_ms'])
    (ROOT / 'docs/report-data.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
