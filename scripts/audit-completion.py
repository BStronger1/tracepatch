"""Offline audit of a frozen run. Never executes commands or queries a model."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from tracepatch.lifecycle import budget_notice, completion_status


def audit(run: Path) -> dict:
    result = json.loads((run / 'result.json').read_text(encoding='utf-8'))
    requests = json.loads((run / 'requests.json').read_text(encoding='utf-8'))
    manifest = json.loads((run.parent / 'manifest.json').read_text(encoding='utf-8'))
    limit = manifest['max_calls_per_task']
    if [r['index'] for r in requests] != list(range(1, len(requests) + 1)) or len(requests) > limit:
        raise ValueError('Inconsistent request sequence or call limit')
    events = []
    for request in requests:
        index = request['index']
        events.append({'call': index, 'remaining_including_current': limit - index + 1,
                       'observed_action_diagnosis': request.get('action_diagnosis'),
                       'observed_finish_reason': request.get('finish_reason'),
                       'notice_preview': budget_notice(index - 1, limit) if limit - index < 3 else None})
    return {'run': run.name, 'observed_policy': manifest['policy'],
            'mode': 'offline audit; notice previews were NOT sent in this historical run',
            'completion': completion_status(result.get('agent_exit'), result.get('verification')),
            'calls_used': len(requests), 'call_limit': limit,
            'rejected_responses': sum(r.get('action_diagnosis') not in (None, 'valid') for r in requests),
            'events': events,
            'limitations': ['No counterfactual model outputs were generated.',
                           'Preview does not establish that reminders improve task completion.',
                           'Post-run verification does not identify when the patch first became correct.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.run)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    print(json.dumps({k: report[k] for k in ('mode', 'completion', 'calls_used', 'rejected_responses')}, indent=2))
