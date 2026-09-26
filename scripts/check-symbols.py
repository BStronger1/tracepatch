"""No-API check of AST scopes in the same pinned Docker Python as real runs."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runner', ROOT / 'scripts/run-repo.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
from tracepatch.memory import EvidenceMemory, docker_read_ranges
from tracepatch.progress import docker_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Do not overwrite evidence')
    args.run_dir.mkdir(parents=True, exist_ok=False)
    task = json.loads((ROOT / 'tasks/repos/requests-2527-v2/task.json').read_text())
    env = runner.environment(task['image'])
    try:
        setup = "printf 'class Jar:\\n    def __init__(\\n        self, label, *, policy=None\\n    ):\\n        self.label = label\\n' > probe.py"
        assert env.execute({'command': setup})['returncode'] == 0
        paths = ['probe.py']
        state = docker_snapshot(runner.runtime.DOCKER, env.container_id, paths)
        reader = lambda ranges: docker_read_ranges(runner.runtime.DOCKER, env.container_id, ranges)
        memory = EvidenceMemory(paths, args.run_dir / 'memory.json', reader,
                                instruction=task['instruction'])
        command = 'sed -n 5p probe.py'
        result = env.execute({'command': command})
        memory.observe(1, command, result, state, state)
        plain, _ = memory.recall(state)
        structured, cards = memory.recall(state, profile='structured')
        assert 'def __init__(self, label, *, policy=None):' in structured
        assert 'def __init__' not in plain
        assert 'A subclass may require constructor arguments.' in structured
        assert len(structured.encode()) <= 4200
        changed = dict(state, **{'probe.py': '0' * 64})
        stale, _ = memory.recall(changed, profile='structured')
        assert 'def __init__' not in stale
        for clause in memory.task['clauses']:
            assert task['instruction'][clause['start']:clause['end']] == clause['text']
        scope = memory.cards[0]['context']['scopes'][0]
        report = {'scope': 'Synthetic Docker signature and task-cue integration; not model repair evidence',
                  'assertions_passed': True, 'model_api_calls': 0, 'image': task['image'],
                  'signature': scope['signature'], 'parameters': scope['parameters'],
                  'source_cards': len(memory.cards), 'task_clauses': len(memory.task['clauses']),
                  'structured_bytes': len(structured.encode()), 'stale_signature_removed': True,
                  'task_spans_match_original': True, 'selected_cards': cards}
        with args.output.open('x', encoding='utf-8') as handle:
            json.dump(report, handle, indent=2)
        print(json.dumps(report))
    finally:
        env.cleanup()


if __name__ == '__main__':
    main()
