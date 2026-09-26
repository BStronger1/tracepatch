import json
import tempfile
import unittest
from pathlib import Path

from tracepatch.testing import PythonCheckEnvironment, observation_json, process_result
from tracepatch.toolcalling import TEST_TOOL_OPTIONS, native_history, parse_tool_call
from tracepatch.window import request_payload


class StructuredTestTests(unittest.TestCase):
    def test_opt_in_schema_is_strict_and_preserves_code(self):
        code = "assert 1 == 1\nprint('ok')"
        call = {'id': 't1', 'type': 'function', 'function': {'name': 'python_check',
                'arguments': json.dumps({'code': code})}}
        message = {'role': 'assistant', 'content': None, 'tool_calls': [call]}
        with self.assertRaises(ValueError):
            parse_tool_call(message, 'tool_calls')
        actual, _ = parse_tool_call(message, 'tool_calls', allow_python_check=True)
        self.assertEqual(actual, code)
        for args in ('{"code":"a","code":"b"}', '{"command":"assert True"}',
                     '{"code":"a","timeout":999}', '{"code":""}',
                     json.dumps({'code': 'a' * 16001})):
            call['function']['arguments'] = args
            with self.assertRaises(ValueError):
                parse_tool_call(message, 'tool_calls', allow_python_check=True)

    def test_mixed_native_history_preserves_pairs_after_pruning(self):
        history = [{'role': 'system', 'content': 's'}, {'role': 'user', 'content': 'task'}]
        for index, name in enumerate(('bash', 'python_check', 'bash', 'python_check')):
            key = 'code' if name == 'python_check' else 'command'
            history += [{'role': 'assistant', 'content': None, 'tool_calls': [{'id': str(index),
                'type': 'function', 'function': {'name': name, 'arguments': json.dumps({key: 'example'})}}]},
                {'role': 'tool', 'tool_call_id': str(index), 'content': 'x' * 1800}]
        raw, metadata = request_payload('m', native_history(history, allow_python_check=True),
            'recent-turns', 3300, tool_options=TEST_TOOL_OPTIONS)
        native_history(json.loads(raw)['messages'], allow_python_check=True)
        self.assertGreater(metadata['omitted_messages'], 0)
        self.assertEqual(json.loads(raw)['messages'][-1]['tool_call_id'], '3')

    def test_status_uses_process_exit_not_output_or_markers(self):
        for code, expected in ((0, 'process_passed'), (1, 'process_failed'), (-15, 'process_failed')):
            result = process_result({'returncode': code, 'timed_out': False,
                'stdout': 'COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\nSUCCESS', 'stderr': ''})
            self.assertEqual(result['status'], expected)
        result = process_result({'returncode': None, 'timed_out': True, 'stdout': 'success', 'stderr': ''})
        self.assertEqual(result['status'], 'timed_out')
        for raw in ({'returncode': True, 'timed_out': False}, {'returncode': 0, 'timed_out': True},
                    {'returncode': 0, 'timed_out': 1}):
            with self.assertRaises(ValueError):
                process_result(dict(stdout='', stderr='', **raw))

    def test_output_truncation_never_cuts_status_envelope_or_json(self):
        output = {'status': 'process_failed', 'returncode': 1, 'source_state': 'unchanged',
                  'output': ('中文"\n' * 5000) + 'AssertionError'}
        wire = observation_json(output)
        self.assertLessEqual(len(wire), 6000)
        parsed = json.loads(wire)
        self.assertEqual(parsed['returncode'], 1)
        self.assertEqual(parsed['status'], 'process_failed')
        self.assertTrue(parsed['output_truncated'])
        self.assertTrue(parsed['output'].endswith('AssertionError'))

    def test_source_changes_and_unknown_observations_are_explicit(self):
        class Env:
            def execute(self, action):
                return {'output': 'bash delegated', 'returncode': 3}
        def execute(code):
            return {'returncode': 0, 'timed_out': False, 'stdout': 'marker', 'stderr': ''}
        with tempfile.TemporaryDirectory() as directory:
            states = iter([{'a.py': 'a' * 64}, {'a.py': 'b' * 64}, None, {'a.py': 'b' * 64}])
            def snapshot():
                state = next(states)
                if state is None:
                    raise TimeoutError()
                return state
            env = PythonCheckEnvironment(Env(), execute, snapshot, Path(directory) / 'records')
            action = {'tool': 'python_check', 'code': 'assert True'}
            self.assertEqual(env.execute(action)['source_state'], 'changed')
            result = env.execute(action)
            self.assertEqual(result['source_state'], 'unknown')
            self.assertIsNone(result['acceptance_verified'])
            self.assertEqual(env.execute({'command': 'anything'})['returncode'], 3)
            self.assertEqual(len(list(env.output_dir.glob('*.json'))), 2)

    def test_infrastructure_failure_is_unknown_not_test_failure(self):
        def broken(code):
            raise TimeoutError()
        with tempfile.TemporaryDirectory() as directory:
            env = PythonCheckEnvironment(None, broken, lambda: {'a.py': 'a' * 64}, Path(directory) / 'records')
            result = env.execute({'tool': 'python_check', 'code': 'assert True'})
            self.assertEqual(result['status'], 'unknown')
            self.assertIsNone(result['returncode'])
            self.assertEqual(result['error_type'], 'TimeoutError')
