"""Offline Docker integration for evidence capture, recall and invalidation."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runner', ROOT / 'scripts/run-repo.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
from tracepatch.progress import ProgressMonitor, ObservedEnvironment, docker_snapshot
from tracepatch.memory import EvidenceMemory, docker_read_ranges
from tracepatch.window import request_payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Do not overwrite evidence')
    args.run_dir.mkdir(parents=True, exist_ok=False)
    task = json.loads((ROOT / 'tasks/repos/click-1687/task.json').read_text())
    env = runner.environment(task['image'])
    try:
        setup = "mkdir -p src; printf 'def fail():\\n    return missing\\n\\nfail()\\n' > src/probe.py"
        assert env.execute({'command': setup})['returncode'] == 0
        paths = ['src/probe.py']
        snapshot = lambda: docker_snapshot(runner.runtime.DOCKER, env.container_id, paths)
        reader = lambda ranges: docker_read_ranges(runner.runtime.DOCKER, env.container_id, ranges)
        monitor = ProgressMonitor(snapshot())
        memory = EvidenceMemory(paths, args.run_dir / 'memory.json', reader)
        observed = ObservedEnvironment(env, monitor, snapshot, args.run_dir / 'progress.json', memory=memory)
        observed.execute({'command': 'sed -n 1,4p src/probe.py'})
        text, cards = memory.recall(monitor.previous)
        assert cards[0]['source_status'] == 'current' and 'return missing' in text
        assert observed.execute({'command': 'python src/probe.py'})['returncode'] == 1
        text, cards = memory.recall(monitor.previous)
        assert 'NameError' in text and cards[0]['kind'] == 'failure'
        observed.execute({'command': "python -c \"from pathlib import Path;p=Path('src/probe.py');p.write_text(p.read_text().replace('missing','7'))\""})
        text, cards = memory.recall(monitor.previous)
        assert all(c['source_status'] == 'stale' for c in cards)
        assert 'return missing' not in text
        observed.execute({'command': 'sed -n 1,4p src/probe.py'})
        assert observed.execute({'command': 'python src/probe.py'})['returncode'] == 0
        text, cards = memory.recall(monitor.previous)
        assert cards[0]['source_status'] == 'stale'  # Historical failure is not silently erased.
        assert cards[1]['source_status'] == 'current' and 'return 7' in text
        history = [{'role': 'system', 'content': 'system'}, {'role': 'user', 'content': 'task'}]
        for i in range(4):
            history += [{'role': 'assistant', 'content': f'action {i}'}, {'role': 'user', 'content': 'x' * 2000}]
        payload, metadata = request_payload('offline', history, 'recent-turns', 4500, memory_notice=text)
        assert metadata['memory_included'] and len(payload) <= 4500
        assert json.loads(payload)['messages'][-2:] == history[-2:]
        report = {'scope': 'Synthetic offline Docker integration, not model repair evidence',
                  'model_api_calls': 0, 'assertions_passed': True, 'actions': len(monitor.events),
                  'checks': ['captured source with matching version', 'captured failed command and frames',
                             'invalidated old cards after edit', 'refreshed reread card',
                             'kept historical failure stale', 'injected within fixed context limit'],
                  'source_cards_captured': sum(e['source_cards'] for e in memory.events),
                  'failure_cards_captured': sum(e['failure_cards'] for e in memory.events),
                  'source_collection_errors': sum(e['source_error'] is not None for e in memory.events),
                  'final_card_metadata': cards, 'context_metadata': metadata,
                  'image': task['image']}
        with args.output.open('x', encoding='utf-8') as handle:
            json.dump(report, handle, indent=2)
        print(json.dumps(report))
    finally:
        env.cleanup()


if __name__ == '__main__':
    main()
