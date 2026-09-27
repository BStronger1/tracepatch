"""Synthetic adapter replies and real Docker edits; no model API calls."""
import argparse
import importlib.util
import io
import json
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runner', ROOT / 'scripts/run-repo.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
from tracepatch.editing import EditingEnvironment, docker_replace
from tracepatch.progress import ProgressMonitor, ObservedEnvironment, docker_snapshot
from minisweagent.exceptions import Submitted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): raise ValueError('Do not overwrite evidence')
    args.run_dir.mkdir(parents=True, exist_ok=False)
    config = json.loads((ROOT / 'configs/model.json').read_text())
    task = json.loads((ROOT / 'tasks/repos/click-2040/task.json').read_text())
    env = runner.environment(task['image'])
    try:
        env.execute({'command': "mkdir -p pkg && printf 'value = 1\\n# aaa\\n' > pkg/probe.py"})
        cid = env.container_id
        snapshot = lambda: docker_snapshot(runner.runtime.DOCKER, cid, ['pkg/probe.py'])
        monitor = ProgressMonitor(snapshot())
        edits = EditingEnvironment(env, lambda edit: docker_replace(runner.runtime.DOCKER, cid, ['pkg/probe.py'], edit), args.run_dir / 'edits')
        observed = ObservedEnvironment(edits, monitor, snapshot, args.run_dir / 'progress.json')
        model = runner.runtime.DmxModel(config, 'offline-placeholder', run_dir=args.run_dir,
            policy='recovery-submit', max_calls=24, action_protocol='native')
        model.test_tool, model.edit_tool = 'python', 'replace'
        messages = [{'role': 'system', 'content': 'Synthetic edit integration.'}, {'role': 'user', 'content': 'Set probe.value to two.'}]
        payloads = []
        def query(name, arguments):
            response = {'usage': {'prompt_tokens': 1, 'completion_tokens': 1}, 'choices': [{'finish_reason': 'tool_calls',
                'message': {'content': None, 'tool_calls': [{'id': 'fake-' + str(len(model.calls)), 'type': 'function',
                    'function': {'name': name, 'arguments': json.dumps(arguments)}}]}}]}
            class Opener:
                def open(self, request, timeout):
                    payloads.append(json.loads(request.data))
                    return io.BytesIO(json.dumps(response).encode())
            with patch.object(runner.runtime.urllib.request, 'build_opener', return_value=Opener()):
                return model.query(messages)
        cases = [('missing', 'value = 2', 'pkg/probe.py', 'old_text_not_found'),
                 ('aa', 'b', 'pkg/probe.py', 'ambiguous_match'),
                 ('value = 1', 'if (', 'pkg/probe.py', 'syntax_error'),
                 ('value = 1', 'value = 2', '../probe.py', 'path_not_allowed'),
                 ('value = 1', 'value = 1', 'pkg/probe.py', 'no_change'),
                 ('value = 1', 'value = 2', 'pkg/probe.py', 'applied')]
        for old, new, path, expected in cases:
            message = query('replace_text', {'path': path, 'old': old, 'new': new})
            output = observed.execute(message['extra']['actions'][0])
            assert output['status'] == expected and output['acceptance_verified'] is None
            assert (monitor.events[-1]['state'] == 'changed') == (expected == 'applied')
            messages.append(message)
            messages.extend(model.format_observation_messages(message, [output]))
            assert json.loads(messages[-1]['content'])['status'] == expected
        assert env.execute({'command': "python -c 'from pkg.probe import value; assert value == 2'"})['returncode'] == 0
        message = query('bash', {'command': 'echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT'})
        try:
            observed.execute(message['extra']['actions'][0])
            raise AssertionError('Explicit submission not recognized')
        except Submitted: pass
        env.execute({'command': 'mv pkg/probe.py pkg/target.py && ln -s target.py pkg/probe.py'})
        linked = docker_replace(runner.runtime.DOCKER, cid, ['pkg/probe.py'], {'path': 'pkg/probe.py', 'old': 'value = 2', 'new': 'value = 3'})
        assert linked['status'] == 'linked_source_rejected'
        assert env.execute({'command': "python -c 'from pkg.target import value; assert value == 2'"})['returncode'] == 0
        # Regression for the first real study: CRLF source, LF tool argument.
        assert env.execute({'command': "python -c \"from pathlib import Path; Path('pkg/crlf.py').write_bytes(b'value = 1\\r\\nother = 0\\r\\n')\""})['returncode'] == 0
        crlf = docker_replace(runner.runtime.DOCKER, cid, ['pkg/crlf.py'],
            {'path': 'pkg/crlf.py', 'old': 'value = 1\nother = 0', 'new': 'value = 2\nother = 0'})
        assert crlf['status'] == 'applied' and crlf['match_mode'] == 'line-ending-normalized'
        assert env.execute({'command': "python -c \"from pathlib import Path; from pkg.crlf import value; assert value == 2; assert Path('pkg/crlf.py').read_bytes() == b'value = 2\\r\\nother = 0\\r\\n'\""})['returncode'] == 0
        report = {'scope': 'Synthetic replies through real adapter and Docker; not repair evidence', 'model_api_calls': 0,
                  'assertions_passed': True, 'image': task['image'], 'statuses': [r['status'] for r in edits.records],
                  'symlink_rejected': True, 'persisted_value_checked_in_separate_process': True,
                  'only_explicit_submission_finishes': True,
                  'crlf_source_lf_arguments_persisted': True,
                  'line_endings_preserved': True,
                  'advertised_tools': [t['function']['name'] for t in payloads[0]['tools']]}
        with args.output.open('x', encoding='utf-8') as handle: json.dump(report, handle, indent=2)
        print(json.dumps(report))
    finally:
        env.cleanup()


if __name__ == '__main__': main()
