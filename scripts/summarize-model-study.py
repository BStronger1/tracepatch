"""Audit a frozen local model study without executing any recorded action."""
import argparse
import hashlib
import importlib.util
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from tracepatch.triage import audit_run
from tracepatch.progress import snapshot_digest
from tracepatch.stages import decide_stage

spec = importlib.util.spec_from_file_location('compare_runs', ROOT / 'scripts/compare-runs.py')
compare_runs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare_runs)


def local_path(name):
    path = (ROOT / name).resolve()
    if ROOT not in path.parents:
        raise ValueError('Evidence path must stay inside this repository')
    return path


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def summarize(plan_path):
    plan = read(plan_path)
    for name, digest in plan['file_hashes'].items():
        if hashlib.sha256(local_path(name).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen file changed: ' + name)
    arms = []
    for arm in plan['order']:
        batch = local_path('runs/' + arm['batch'])
        run = local_path('runs/' + arm['batch'] + '/' + arm['batch'] + '--' + arm['task'])
        manifest, config, result = read(batch / 'manifest.json'), read(batch / 'config.json'), read(run / 'result.json')
        calls, progress, public = [read(run / name) for name in ('requests.json', 'progress.json', 'public-checks/checks.json')]
        if not read(batch / 'preflight.json')['valid'] or result.get('error_type') or result.get('unknown_cost_requests'):
            raise ValueError('Incomplete/infrastructure run requires separate reporting')
        assert manifest['stage_mode'] == 'observe' and manifest['model_profile'] == arm['model_profile']
        assert manifest['model'] == config['model'] and manifest['pricing'] == config['pricing']
        assert manifest['max_calls_per_task'] == plan['max_calls'] and manifest['max_output_tokens'] == plan['max_output_tokens']
        assert len(calls) == result['api_calls'] <= plan['max_calls']
        versions = {}
        for number, record in enumerate(public['records'], 1):
            assert record.get('error_type') is None
            candidate = run / 'public-checks' / f'version-{number:03d}' / 'candidate'
            state = {name: hashlib.sha256((candidate / name).read_bytes()).hexdigest() for name in progress['initial']}
            assert snapshot_digest(state) == record['source_sha256']
            versions[record['source_sha256']] = state
        trajectory = read(run / 'trajectory.json')
        action_index, tools, python_records = 0, Counter(), []
        for index, message in enumerate(trajectory['messages']):
            for action in message.get('extra', {}).get('actions', []):
                action_index += 1
                name = action.get('tool', 'bash')
                tools[name] += 1
                if name != 'python_check':
                    continue
                number = len(python_records) + 1
                record = read(run / 'python-checks' / f'{number:03d}.json')
                code = (run / 'python-checks' / f'{number:03d}.py').read_text(encoding='utf-8')
                assert action['code'] == code and hashlib.sha256(code.encode()).hexdigest() == record['check_sha256']
                assert hashlib.sha256((record['stdout'] + record['stderr']).encode()).hexdigest() == record['output_sha256']
                before = progress['initial_sha256'] if action_index == 1 else progress['events'][action_index-2]['snapshot_sha256']
                after = progress['events'][action_index-1]['snapshot_sha256']
                assert (record['source_before_sha256'], record['source_after_sha256']) == (before, after)
                observation = json.loads(trajectory['messages'][index+1]['content'])
                assert observation['status'] == record['status'] and observation['acceptance_verified'] is None
                python_records.append({'action': action_index, **{k: v for k, v in record.items() if k not in ('stdout', 'stderr')}})
        assert action_index == len(progress['events'])
        diagnoses = []
        for call in calls:
            assert call['status'] == 'completed' and call['request_bytes'] <= plan['input_json_byte_limit']
            assert call.get('stage_notice') is None and call.get('progress_notice') is None and call['actual_tool_choice'] == 'required'
            price = config['pricing']
            expected = (call['prompt_tokens'] * price['input'] + call['completion_tokens'] * price['output']) / 1e6
            assert math.isclose(call['estimated_no_cache_cny'], expected, rel_tol=1e-10)
            used = call['progress_action_index']
            digest = progress['initial_sha256'] if used == 0 else progress['events'][used-1]['snapshot_sha256']
            evidence = [r for r in python_records if r['action'] <= used]
            decision = decide_stage(progress['initial'], versions[digest], evidence, call['public_check_evidence'], call['index']-1, plan['max_calls'])
            assert call['stage_decision'] == decision
            if call['action_diagnosis'] != 'valid':
                diagnoses.append({'call': call['index'], 'reason': call['action_diagnosis'], 'finish_reason': call['finish_reason']})
        assert len(diagnoses) == result['format_error_count']
        assert math.isclose(sum(c['estimated_no_cache_cny'] for c in calls), result['estimated_known_no_cache_cny'], rel_tol=1e-10)
        final_state = {name: hashlib.sha256((run / 'candidate' / name).read_bytes()).hexdigest() for name in progress['initial']}
        assert snapshot_digest(final_state) == progress['events'][-1]['snapshot_sha256']
        arms.append({'batch': arm['batch'], 'task': arm['task'], 'requested_model': manifest['model'],
            'response_models': sorted({c.get('response_model') or '(missing)' for c in calls}),
            'result': result, 'tool_calls': dict(tools), 'python_checks': python_records, 'rejections': diagnoses,
            'progress': progress['summary'], 'first_changed_action': next((e['action'] for e in progress['events'] if e['state'] == 'changed'), None),
            'history_pruned_requests': sum(c.get('omitted_messages', 0) > 0 for c in calls),
            'prompt_tokens': sum(c['prompt_tokens'] for c in calls), 'completion_tokens': sum(c['completion_tokens'] for c in calls),
            'all_stage_decisions_replayed': True, 'triage': audit_run(run),
            'hashes': {n: hashlib.sha256((run / n).read_bytes()).hexdigest() for n in ('requests.json', 'trajectory.json', 'patch.diff')}})
    pairs = []
    for task in sorted({a['task'] for a in plan['order']}):
        selected = [a for a in plan['order'] if a['task'] == task]
        assert len(selected) == 2
        pairs.append({'task': task, 'comparison': compare_runs.compare(*(local_path('runs/' + a['batch']) for a in selected), intervention='model')})
    return {'scope': plan['scope'], 'plan': plan_path.name, 'pairs': pairs, 'arms': arms,
            'totals': {'calls': sum(a['result']['api_calls'] for a in arms),
                       'estimated_known_no_cache_cny': sum(a['result']['estimated_known_no_cache_cny'] for a in arms)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = summarize(args.plan)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps({'arms': [{k: a[k] for k in ('task', 'requested_model', 'response_models', 'tool_calls', 'first_changed_action')} for a in report['arms']],
                      'totals': report['totals']}))


if __name__ == '__main__':
    main()
