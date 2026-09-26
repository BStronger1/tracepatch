"""Deterministic offline Docker integration check; no model API calls."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runner', ROOT / 'scripts/run-repo.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
from tracepatch.progress import ProgressMonitor, ObservedEnvironment, docker_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Do not overwrite evidence')
    task = json.loads((ROOT / 'tasks/repos/click-1687/task.json').read_text())
    env = runner.environment(task['image'])
    try:
        assert env.execute({'command': "printf 'x = 1\\n' > probe.py"})['returncode'] == 0
        snapshot = lambda: docker_snapshot(runner.runtime.DOCKER, env.container_id, ['probe.py'])
        monitor = ProgressMonitor(snapshot())
        # Do not wrap setup or sensor commands as model actions.
        observed = ObservedEnvironment(env, monitor, snapshot, args.output)
        for command in ('cat probe.py', 'head probe.py', 'tail probe.py',
                        'grep x probe.py', 'wc -l probe.py', "sed -n '1p' probe.py"):
            observed.execute({'command': command})
        assert monitor.events[-1]['signal'] == 'unchanged_source_review'
        observed.execute({'command': "printf 'x = 2\\n' > probe.py; exit 1"})
        assert monitor.events[-1]['state'] == 'changed'
        assert monitor.events[-1]['tool_returncode'] == 1
        observed.execute({'command': "python -c \"assert False, 'replacement did not match'\""})
        assert monitor.events[-1]['state'] == 'unchanged'
        observed.execute({'command': "printf 'x = 1\\n' > probe.py"})
        assert monitor.events[-1]['state'] == 'changed'
        assert monitor.events[-1]['net_changed_paths'] == []
        observed.execute({'command': 'rm probe.py'})
        assert monitor.events[-1]['state'] == 'changed'
        observed.execute({'command': 'ln -s /etc/passwd probe.py'})
        assert monitor.events[-1]['state'] == 'unknown'
        observed.execute({'command': "rm probe.py; printf 'x = 1\\n' > probe.py"})
        assert monitor.events[-1]['state'] == 'reanchored'
        try:
            observed.execute({'command': 'echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT'})
        except Exception as error:
            assert type(error).__name__ == 'Submitted'
        else:
            raise AssertionError('Submission was swallowed')
        assert len(monitor.events) == 13
        report = monitor.report()
        report.update(scope='Synthetic Docker sensor integration; not a model repair experiment',
                      image=task['image'], model_api_calls=0, assertions_passed=True)
        args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report['summary']))
    finally:
        env.cleanup()


if __name__ == '__main__':
    main()
