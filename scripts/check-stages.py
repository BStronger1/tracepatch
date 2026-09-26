"""Synthetic adapter responses plus real offline Docker; no model API calls."""
import argparse
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runner', ROOT / 'scripts/run-repo.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
from minisweagent.exceptions import FormatError, Submitted
from tracepatch.testing import PythonCheckEnvironment, docker_python_check
from tracepatch.progress import ProgressMonitor, ObservedEnvironment, docker_snapshot, snapshot_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Do not overwrite evidence')
    args.run_dir.mkdir(parents=True, exist_ok=False)
    config = json.loads((ROOT / 'configs/model.json').read_text())
    task = json.loads((ROOT / 'tasks/repos/click-1840/task.json').read_text())
    env = runner.environment(task['image'])
    try:
        env.execute({'command': "printf 'value = 1\\n' > probe.py"})
        cid = env.container_id
        snapshot = lambda: docker_snapshot(runner.runtime.DOCKER, cid, ['probe.py'])
        monitor = ProgressMonitor(snapshot())
        tests = PythonCheckEnvironment(env,
            lambda code: docker_python_check(runner.runtime.DOCKER, cid, code),
            snapshot, args.run_dir / 'python-checks')
        observed = ObservedEnvironment(tests, monitor, snapshot, args.run_dir / 'progress.json')
        model = runner.runtime.DmxModel(config, 'offline-placeholder', run_dir=args.run_dir,
            policy='recovery-submit', max_calls=24, action_protocol='native')
        model.test_tool, model.stage_mode = 'python', 'guide'
        model.progress_monitor, model.python_check_environment = monitor, tests
        model.public_checks = SimpleNamespace(current={'source_sha256': snapshot_digest(monitor.previous), 'status': 'failed'})
        model.calls = [{} for _ in range(6)]  # Explicit synthetic prehistory at the gate.
        messages = [{'role': 'system', 'content': 'Synthetic integration fixture.'},
                    {'role': 'user', 'content': 'Make probe.value equal two and check it.'}]
        payloads = []

        def query(name, argument):
            field = 'code' if name == 'python_check' else 'command'
            response = {'usage': {'prompt_tokens': 1, 'completion_tokens': 1}, 'choices': [{
                'finish_reason': 'tool_calls', 'message': {'content': None, 'tool_calls': [{
                    'id': 'fake-' + str(len(model.calls)), 'type': 'function', 'function': {
                        'name': name, 'arguments': json.dumps({field: argument})}}]}}]}
            class OfflineOpener:
                def open(self, request, timeout):
                    payloads.append(json.loads(request.data))
                    return io.BytesIO(json.dumps(response).encode())
            with patch.object(runner.runtime.urllib.request, 'build_opener', return_value=OfflineOpener()):
                return model.query(messages)

        try:
            query('bash', "printf 'value = 99\\n' > probe.py")
            raise AssertionError('Wrong-tool reply accepted')
        except FormatError as error:
            assert model.calls[-1]['action_diagnosis'] == 'stage_requires_python_check'
            messages.extend(error.messages)
        assert snapshot() == monitor.initial

        cases = [('python_check', 'import probe; assert probe.value == 2', 'check_hypothesis'),
                 ('bash', "printf 'value = 2\\n' > probe.py", 'implement'),
                 ('python_check', 'import probe; assert probe.value == 2', 'check_patch')]
        for name, argument, expected in cases:
            message = query(name, argument)
            assert model.calls[-1]['stage_decision']['stage'] == expected
            output = observed.execute(message['extra']['actions'][0])
            messages.append(message)
            messages.extend(model.format_observation_messages(message, [output]))
            model.public_checks.current = {'source_sha256': snapshot_digest(monitor.previous),
                'status': 'failed' if monitor.previous == monitor.initial else 'passed'}
        message = query('bash', 'echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT')
        assert model.calls[-1]['stage_decision']['stage'] == 'review_submission'
        assert tests.records[0]['status'] == 'process_failed' and tests.records[1]['status'] == 'process_passed'
        try:
            observed.execute(message['extra']['actions'][0])
            raise AssertionError('Explicit submission not recognized')
        except Submitted:
            pass
        report = {'scope': 'Synthetic model responses with real Docker; not repair-performance evidence',
            'model_api_calls': 0, 'assertions_passed': True, 'image': task['image'],
            'wrong_tool_rejected_before_execution': True, 'only_explicit_submission_finishes': True,
            'stages': [r['stage_decision']['stage'] for r in model.calls[6:]],
            'tool_choices': [p['tool_choice'] for p in payloads],
            'check_statuses': [r['status'] for r in tests.records]}
        with args.output.open('x', encoding='utf-8') as handle:
            json.dump(report, handle, indent=2)
        print(json.dumps(report))
    finally:
        env.cleanup()


if __name__ == '__main__':
    main()
