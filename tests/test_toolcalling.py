import json
import unittest
from tracepatch.toolcalling import TOOL_OPTIONS, native_history, parse_tool_call, validate_history
from tracepatch.window import request_payload


def call(arguments='{"command":"echo ok"}', name='bash', ident='call_1'):
    return {'id': ident, 'type': 'function', 'function': {'name': name, 'arguments': arguments}}


class ToolCallingTests(unittest.TestCase):
    def test_valid_call_preserves_command(self):
        command = "python -c 'print(\"two  spaces\")'"
        actual, canonical = parse_tool_call({'tool_calls': [call(json.dumps({'command': command}))]}, 'tool_calls')
        self.assertEqual(actual, command)
        self.assertEqual(json.loads(canonical['function']['arguments'])['command'], command)

    def test_reject_ambiguous_or_incomplete_without_text_fallback(self):
        invalid = [[], [call(), call()], [call(name='python')], [call(ident='')],
                   [call('{"command":')], [call('{"command":"a","command":"b"}')],
                   [call('{"command":"echo ok","extra":1}')], [call('{"command":123}')], [call('{"command":" "}')]]
        for calls in invalid:
            with self.subTest(calls=calls), self.assertRaises(ValueError):
                parse_tool_call({'tool_calls': calls, 'content': '```bash\necho ok\n```'}, 'tool_calls')
        with self.assertRaisesRegex(ValueError, 'output_limit'):
            parse_tool_call({'tool_calls': [call()]}, 'length')

    def test_round_trip_and_orphans(self):
        valid = [{'role': 'assistant', 'content': None, 'tool_calls': [call()]},
                 {'role': 'tool', 'tool_call_id': 'call_1', 'content': 'ok'}]
        self.assertEqual(native_history(valid), valid)
        for history in (valid[:1], valid[1:], [valid[0], {'role': 'user', 'content': 'ok'}],
                        [valid[0], {'role': 'tool', 'tool_call_id': 'wrong', 'content': 'ok'}]):
            with self.assertRaises(ValueError):
                validate_history(history)

    def test_context_pruning_keeps_pairs_and_schema_within_budget(self):
        messages = [{'role': 'system', 'content': 'system'}, {'role': 'user', 'content': 'task'}]
        for i in range(4):
            messages += [{'role': 'assistant', 'content': None, 'tool_calls': [call(ident=f'c{i}')]},
                         {'role': 'tool', 'tool_call_id': f'c{i}', 'content': 'x' * 900}]
        raw, meta = request_payload('m', messages, 'recent-turns', 1900, tool_options=TOOL_OPTIONS)
        data = json.loads(raw)
        validate_history(data['messages'])
        self.assertLessEqual(len(raw), 1900)
        self.assertGreater(meta['omitted_messages'], 0)
        self.assertEqual(data['tools'], TOOL_OPTIONS['tools'])
        self.assertEqual(data['messages'][-1]['tool_call_id'], 'c3')
