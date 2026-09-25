import unittest
from tracepatch.actions import parse_action


class ActionTests(unittest.TestCase):
    def test_complete_native_and_fenced(self):
        self.assertEqual(parse_action('Read files\n```bash\ncat ranges.py\n```'), 'cat ranges.py\n')
        self.assertEqual(parse_action('<tool_call>\n<function=bash>\n<parameter=command>\ncat ranges.py\n</parameter>\n</function>\n</tool_call>'), 'cat ranges.py')

    def test_reject_malformed_multiple_and_wrong_tools(self):
        cases = [
            '<tool_call><parameter=command>\nls\n</parameter></function></tool_call>',
            '```bash\nls\n```\n```bash\npwd\n```',
            '<tool_call><function=python><parameter=command>\nls\n</parameter></function></tool_call>',
            '<tool_call>incomplete',
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                parse_action(case)
