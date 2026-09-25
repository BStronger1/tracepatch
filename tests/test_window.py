import json
import unittest
from tracepatch.window import request_payload


class WindowTests(unittest.TestCase):
    def test_output_limit_reaches_wire_and_rejects_unbudgeted_values(self):
        messages = [{'role': 'system', 'content': 's'}, {'role': 'user', 'content': 't'}]
        default, _ = request_payload('m', messages)
        explicit, _ = request_payload('m', messages, max_output_tokens=512)
        larger, _ = request_payload('m', messages, max_output_tokens=1024)
        self.assertEqual(default, explicit)
        a, b = json.loads(default), json.loads(larger)
        self.assertEqual(a.pop('max_tokens'), 512)
        self.assertEqual(b.pop('max_tokens'), 1024)
        self.assertEqual(a, b)
        for invalid in (True, 512.0, '1024', 0, 2048):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                request_payload('m', messages, max_output_tokens=invalid)

    def test_whole_turn_removal_preserves_task_and_latest_feedback(self):
        messages = [{'role': 'system', 'content': 'system'}, {'role': 'user', 'content': 'task'}]
        for i in range(4):
            messages += [{'role': 'assistant', 'content': 'action' + str(i)},
                         {'role': 'user', 'content': str(i) * 700}]
        messages += [{'role': 'user', 'content': 'final call notice'}]
        raw, meta = request_payload('model', messages, 'recent-turns', 1500)
        wire = json.loads(raw)['messages']
        self.assertLessEqual(len(raw), 1500)
        self.assertEqual(wire[:2], messages[:2])
        self.assertEqual(wire[3:], messages[-3:])
        self.assertEqual(meta['omitted_messages'], 6)
        self.assertEqual(len(messages), 11)

    def test_no_pruning_when_small_and_fail_closed_when_impossible(self):
        messages = [{'role': 'system', 'content': 's'}, {'role': 'user', 'content': 't'}]
        a, _ = request_payload('m', messages, 'none')
        b, meta = request_payload('m', messages, 'recent-turns')
        self.assertEqual(a, b)
        self.assertEqual(meta['omitted_messages'], 0)
        messages += [{'role': 'assistant', 'content': 'a'}, {'role': 'user', 'content': 'x' * 3000}]
        for policy in ('none', 'recent-turns'):
            with self.assertRaises(RuntimeError):
                request_payload('m', messages, policy, 1000)
