"""Sequential, low-volume release evaluation. Structural checks need human accuracy review.

Records real endpoint latency/usage. Optional supplied per-million token prices
estimate model cost only, excluding retrieval, hosting and provider-specific fees.
Never treats mocked timings or absent usage as real performance/cost evidence.
"""
import argparse
import json
import math
import time
from pathlib import Path

import requests


def percentile(values, percentile):
    values = sorted(values)
    return values[max(0, math.ceil(len(values) * percentile / 100) - 1)] if values else None


def estimated_cost(metrics, prices):
    calls = [('text', call) for call in metrics.get('generation', [])]
    if metrics.get('vision', {}).get('status') == 'used':
        calls.append(('vision', metrics['vision']))
    if not calls:
        return None
    total = 0
    for kind, call in calls:
        for field, suffix in [('prompt_tokens', 'input'), ('completion_tokens', 'output')]:
            rate = prices.get(f'{kind}_{suffix}')
            tokens = call.get(field)
            if rate is None or not isinstance(tokens, int):
                return None
            total += tokens * rate / 1_000_000
    return round(total, 8)


def evaluate(base, cases, *, session=None, prices=None, expected_version=None, require_vision=False):
    session = session or requests.Session()
    results = []
    for case in cases:
        started = time.perf_counter()
        result = {**case, 'human_review': 'pending'}
        try:
            response = session.post(base.rstrip('/') + '/chat/ask', json={'question': case['question'], 'history': []}, timeout=120, allow_redirects=False)
            response.raise_for_status()
            if response.status_code != 200 or 'json' not in response.headers.get('Content-Type', ''):
                raise ValueError('Expected chat JSON response')
            body = response.json()
            sources, metrics = body.get('sources', []), body.get('metrics', {})
            problems = []
            if not body.get('answer', '').strip():
                problems.append('empty-answer')
            if case['chapters'] and not set(case['chapters']).intersection(source.get('section_id') for source in sources):
                problems.append('missing-expected-chapter-reference')
            if expected_version and any(source.get('version') != expected_version for source in sources):
                problems.append('source-version-mismatch')
            if len({source.get('version') for source in sources}) > 1:
                problems.append('mixed-source-versions')
            status = metrics.get('vision', {}).get('status')
            if case['kind'] == 'text' and status == 'used':
                problems.append('unnecessary-vision-call')
            if case['kind'] == 'visual' and require_vision and status != 'used':
                problems.append('vision-not-used')
            if status == 'used' and metrics['vision'].get('version') != metrics.get('manual_version'):
                problems.append('image-version-mismatch')
            if status == 'used' and case.get('expected_image_ids'):
                ids = metrics['vision'].get('image_ids', [])
                if not set(ids).intersection(case['expected_image_ids']):
                    problems.append('missing-target-screenshot')
                if any(not any(value.startswith(chapter + '-') for chapter in case['chapters']) for value in ids):
                    problems.append('unrelated-screenshot')
            result.update(answer=body.get('answer'), sources=sources, metrics=metrics,
                structural_status='failed' if problems else 'passed', problems=problems,
                estimated_model_usd=estimated_cost(metrics, prices or {}))
        except Exception as exc:
            result.update(structural_status='failed', error_type=type(exc).__name__)
        result['client_duration_ms'] = round((time.perf_counter() - started) * 1000)
        results.append(result)
    timings = [result['client_duration_ms'] for result in results]
    return {'scope': 'sequential live release evaluation, not a load/capacity test', 'human_accuracy_review': 'pending',
        'sample_count': len(results), 'structural_passed': sum(result['structural_status'] == 'passed' for result in results),
        'latency_ms': {f'p{p}': percentile(timings, p) for p in [50, 95, 99]},
        'cost_scope': 'model token estimate only; unknown prices/usage => null', 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--cases', type=Path, default=Path(__file__).resolve().parents[1] / 'evaluation/manual-cases.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ids', help='Comma-separated case IDs; default all cases')
    parser.add_argument('--expected-version')
    parser.add_argument('--require-vision', action='store_true')
    for kind in ['text', 'vision']:
        for suffix in ['input', 'output']:
            parser.add_argument(f'--{kind}-{suffix}-price', type=float, help='USD per million tokens, from your actual provider plan')
    args = parser.parse_args()
    if not args.base_url.startswith('https://'):
        parser.error('Use the configured HTTPS chatbot origin')
    cases = json.loads(args.cases.read_text())
    if args.ids:
        ids = set(args.ids.split(','))
        if not ids <= {case['id'] for case in cases}:
            parser.error('Unknown evaluation ID')
        cases = [case for case in cases if case['id'] in ids]
    prices = {f'{kind}_{suffix}': getattr(args, f'{kind}_{suffix}_price') for kind in ['text', 'vision'] for suffix in ['input', 'output']}
    report = evaluate(args.base_url, cases, expected_version=args.expected_version, require_vision=args.require_vision, prices=prices)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({key: report[key] for key in ['sample_count', 'structural_passed', 'latency_ms', 'human_accuracy_review']}))
    return int(report['structural_passed'] != report['sample_count'])


if __name__ == '__main__':
    raise SystemExit(main())
