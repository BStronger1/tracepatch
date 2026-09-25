"""Replay payload construction only; no execution, network, or model prediction."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from tracepatch.lifecycle import prepare_messages
from tracepatch.window import request_payload

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('run', type=Path)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
manifest = json.loads((args.run.parent / 'manifest.json').read_text(encoding='utf-8'))
trajectory = json.loads((args.run / 'trajectory.json').read_text(encoding='utf-8'))
requests = json.loads((args.run / 'requests.json').read_text(encoding='utf-8'))
messages = [m for m in trajectory['messages'] if m['role'] != 'exit']
wire, _ = prepare_messages(messages, len(requests), manifest['max_calls_per_task'], manifest['policy'])
results = {}
for policy in ('none', 'recent-turns'):
    try:
        payload, metadata = request_payload(manifest['model'], wire, policy)
        results[policy] = {'within_limit': True, 'request_bytes': len(payload), **metadata}
    except RuntimeError as error:
        results[policy] = {'within_limit': False, 'reason': str(error)}
report = {'run': args.run.name, 'mode': 'offline payload replay only', 'policies': results,
          'model_calls': 0, 'limitations': 'Fits payload budget does not mean a correct repair or successful submission.'}
with args.output.open('x', encoding='utf-8') as handle:
    json.dump(report, handle, ensure_ascii=False, indent=2)
print(json.dumps(report, ensure_ascii=False, indent=2))
