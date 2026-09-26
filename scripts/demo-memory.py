"""Synthetic evidence-memory walkthrough. No Docker, API or source execution."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from tracepatch.memory import EvidenceMemory
from tracepatch.window import request_payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    fixture = args.output_dir / 'fixture.py'
    fixture.write_text('def example():\n    return missing\n', encoding='utf-8')
    def snapshot():
        return {'fixture.py': hashlib.sha256(fixture.read_bytes()).hexdigest()}
    def reader(ranges):
        return [dict(r, version=snapshot()['fixture.py'], excerpt=fixture.read_text(),
                     excerpt_truncated=False) for r in ranges]
    memory = EvidenceMemory(['fixture.py'], args.output_dir / 'memory.json', reader)
    initial = snapshot()
    # Simulate a read action; the fixture source is never run.
    memory.observe(1, 'sed -n 1,2p fixture.py',
                   {'output': fixture.read_text(), 'returncode': 0}, initial, initial)
    _, before_edit = memory.recall(initial)
    fixture.write_text('def example():\n    return 7\n', encoding='utf-8')
    updated = snapshot()
    stale_text, after_edit = memory.recall(updated)
    assert after_edit[0]['source_status'] == 'stale' and 'return missing' not in stale_text
    memory.observe(2, 'sed -n 1,2p fixture.py',
                   {'output': fixture.read_text(), 'returncode': 0}, updated, updated)
    notice, after_reread = memory.recall(updated)
    assert after_reread[0]['source_status'] == 'current' and 'return 7' in notice
    history = [{'role': 'system', 'content': 'system'}, {'role': 'user', 'content': 'task'}]
    for i in range(4):
        history += [{'role': 'assistant', 'content': f'action {i}'}, {'role': 'user', 'content': 'x' * 1800}]
    payload, metadata = request_payload('offline-demo', history, 'recent-turns', 3600, memory_notice=notice)
    assert metadata['memory_included'] and len(payload) <= 3600
    memory.save_recall(notice)
    report = {'synthetic': True, 'model_api_calls': 0, 'source_executed': False,
              'before_edit': before_edit, 'after_edit': after_edit, 'after_reread': after_reread,
              'payload_bytes': len(payload), 'byte_limit': 3600, 'context': metadata,
              'scope': 'Mechanism walkthrough, not model performance evidence'}
    (args.output_dir / 'demo-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
