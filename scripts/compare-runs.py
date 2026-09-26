"""Compare frozen paired development batches without exposing raw prompts or commands."""
import argparse
import json
from pathlib import Path


def compare(left: Path, right: Path, *, intervention='policy') -> dict:
    if intervention not in ('policy', 'output-budget', 'progress-feedback', 'evidence-memory'):
        raise ValueError('Unknown intervention')
    manifests = [json.loads((p / 'manifest.json').read_text(encoding='utf-8')) for p in (left, right)]
    controlled = ('split', 'suite', 'upstream_commit', 'image', 'system_prompt', 'model', 'action_protocol',
                  'max_calls_per_task', 'max_output_tokens', 'enable_thinking',
                  'observation_char_limit', 'input_json_byte_limit', 'tasks', 'reject_provider_truncation', 'source_layout',
                  'progress_mode', 'progress_threshold', 'progress_schema',
                  'memory_mode', 'memory_schema', 'memory_byte_limit')
    if intervention == 'output-budget':
        controlled = tuple(k for k in controlled if k != 'max_output_tokens') + ('policy', 'context_policy')
    if intervention == 'progress-feedback':
        controlled = tuple(k for k in controlled if k != 'progress_mode') + ('policy', 'context_policy')
        if {m.get('progress_mode') for m in manifests} != {'observe', 'feedback'}:
            raise ValueError('Progress comparison requires observe and feedback modes')
    if intervention == 'evidence-memory':
        controlled = tuple(k for k in controlled if k != 'memory_mode') + ('policy', 'context_policy')
        if {m.get('memory_mode') for m in manifests} != {'observe', 'recall'}:
            raise ValueError('Memory comparison requires observe and recall modes')
    differences = [key for key in controlled if manifests[0].get(key) != manifests[1].get(key)]
    if differences:
        raise ValueError('Uncontrolled differences: ' + ', '.join(differences))
    # Same runner and policies implementation; only selected policy may differ.
    for name in ('runner', 'runtime', 'budget', 'actions', 'recovery'):
        if (left / f'{name}.snapshot.py').read_bytes() != (right / f'{name}.snapshot.py').read_bytes():
            raise ValueError('Different implementation snapshot: ' + name)
    if any((p / 'lifecycle.snapshot.py').exists() for p in (left, right)):
        if not all((p / 'lifecycle.snapshot.py').exists() for p in (left, right)):
            raise ValueError('Missing lifecycle snapshot')
        if (left / 'lifecycle.snapshot.py').read_bytes() != (right / 'lifecycle.snapshot.py').read_bytes():
            raise ValueError('Different lifecycle snapshot')
    arms = []
    for name in ('memory', 'context'):
        if intervention == 'evidence-memory' or any((p / f'{name}.snapshot.py').exists() for p in (left, right)):
            if not all((p / f'{name}.snapshot.py').exists() for p in (left, right)):
                raise ValueError('Missing snapshot: ' + name)
            if (left / f'{name}.snapshot.py').read_bytes() != (right / f'{name}.snapshot.py').read_bytes():
                raise ValueError('Different snapshot: ' + name)
    if any((p / 'progress.snapshot.py').exists() for p in (left, right)):
        if not all((p / 'progress.snapshot.py').exists() for p in (left, right)):
            raise ValueError('Missing progress snapshot')
        if (left / 'progress.snapshot.py').read_bytes() != (right / 'progress.snapshot.py').read_bytes():
            raise ValueError('Different progress snapshot')
    if any((p / 'repositories.snapshot.py').exists() for p in (left, right)):
        if not all((p / 'repositories.snapshot.py').exists() for p in (left, right)):
            raise ValueError('Missing repository layout snapshot')
        if (left / 'repositories.snapshot.py').read_bytes() != (right / 'repositories.snapshot.py').read_bytes():
            raise ValueError('Different repository layout snapshot')
    if any((p / 'toolcalling.snapshot.py').exists() for p in (left, right)):
        if not all((p / 'toolcalling.snapshot.py').exists() for p in (left, right)):
            raise ValueError('Missing toolcalling snapshot')
        if (left / 'toolcalling.snapshot.py').read_bytes() != (right / 'toolcalling.snapshot.py').read_bytes():
            raise ValueError('Different toolcalling snapshot')
    if any((p / 'window.snapshot.py').exists() for p in (left, right)):
        if not all((p / 'window.snapshot.py').exists() for p in (left, right)):
            raise ValueError('Missing context implementation snapshot')
        if (left / 'window.snapshot.py').read_bytes() != (right / 'window.snapshot.py').read_bytes():
            raise ValueError('Different context implementation snapshot')
    for folder, manifest in zip((left, right), manifests):
        summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
        tasks = summary['tasks']
        if set(t['task'] for t in tasks) != set(manifest['tasks']):
            raise ValueError('Incomplete batch')
        arms.append({'batch': folder.name, 'policy': manifest['policy'],
                     'progress_mode': manifest.get('progress_mode', 'off'),
                     'memory_mode': manifest.get('memory_mode', 'off'),
                     'max_output_tokens': manifest.get('max_output_tokens'),
                     'context_policy': manifest.get('context_policy', 'none'),
                     'verified': sum(t['verified_success'] for t in tasks),
                     'submitted': sum(t.get('agent_exit') == 'Submitted' for t in tasks),
                     'calls': sum(t['api_calls'] for t in tasks),
                     'rejected_actions': sum(t.get('format_error_count', 0) for t in tasks),
                     'estimated_known_no_cache_cny': sum(t['estimated_known_no_cache_cny'] for t in tasks),
                     'unknown_cost_requests': sum(t['unknown_cost_requests'] for t in tasks),
                     'tasks': [{k: t.get(k) for k in ('task', 'verified_success', 'agent_exit',
                                'api_calls', 'format_error_count')} for t in tasks]})
    interventions = [key for key in ('policy', 'context_policy', 'max_output_tokens', 'progress_mode', 'memory_mode')
                     if manifests[0].get(key, 'none') != manifests[1].get(key, 'none')]
    return {'scope': 'Single run per development task per arm; not a benchmark or causal estimate.',
            'controls_match': True, 'intervention_fields': interventions, 'arms': arms}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('recovery', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--intervention', choices=('policy', 'output-budget', 'progress-feedback', 'evidence-memory'), default='policy')
    args = parser.parse_args()
    result = compare(args.baseline, args.recovery, intervention=args.intervention)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
