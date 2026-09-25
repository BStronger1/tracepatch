"""Compare frozen paired development batches without exposing raw prompts or commands."""
import argparse
import json
from pathlib import Path


def compare(left: Path, right: Path) -> dict:
    manifests = [json.loads((p / 'manifest.json').read_text(encoding='utf-8')) for p in (left, right)]
    controlled = ('split', 'upstream_commit', 'image', 'system_prompt', 'model',
                  'max_calls_per_task', 'max_output_tokens', 'enable_thinking',
                  'observation_char_limit', 'input_json_byte_limit', 'tasks', 'reject_provider_truncation')
    differences = [key for key in controlled if manifests[0].get(key) != manifests[1].get(key)]
    if differences:
        raise ValueError('Uncontrolled differences: ' + ', '.join(differences))
    # Same runner and policies implementation; only selected policy may differ.
    for name in ('runner', 'runtime', 'budget', 'actions', 'recovery'):
        if (left / f'{name}.snapshot.py').read_bytes() != (right / f'{name}.snapshot.py').read_bytes():
            raise ValueError('Different implementation snapshot: ' + name)
    arms = []
    for folder, manifest in zip((left, right), manifests):
        summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
        tasks = summary['tasks']
        if set(t['task'] for t in tasks) != set(manifest['tasks']):
            raise ValueError('Incomplete batch')
        arms.append({'batch': folder.name, 'policy': manifest['policy'],
                     'verified': sum(t['verified_success'] for t in tasks),
                     'submitted': sum(t.get('agent_exit') == 'Submitted' for t in tasks),
                     'calls': sum(t['api_calls'] for t in tasks),
                     'rejected_actions': sum(t.get('format_error_count', 0) for t in tasks),
                     'estimated_known_no_cache_cny': sum(t['estimated_known_no_cache_cny'] for t in tasks),
                     'unknown_cost_requests': sum(t['unknown_cost_requests'] for t in tasks),
                     'tasks': [{k: t.get(k) for k in ('task', 'verified_success', 'agent_exit',
                                'api_calls', 'format_error_count')} for t in tasks]})
    return {'scope': 'Single run per development task per arm; not a benchmark or causal estimate.',
            'controls_match': True, 'arms': arms}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('recovery', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.baseline, args.recovery)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
