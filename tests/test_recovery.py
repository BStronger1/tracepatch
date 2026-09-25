import unittest

from tracepatch.recovery import diagnose_action, recovery_feedback


class RecoveryTests(unittest.TestCase):
    def test_provider_truncation_overrides_apparently_complete_command(self):
        self.assertEqual(diagnose_action('```bash\necho partial\n```', 'length'), 'output_limit')

    def test_distinct_observed_failures(self):
        cases = [('Done!', 'missing_action'), ('```bash\ncat <<EOF', 'incomplete_action'),
                 ('```bash\necho a\n```\n```bash\necho b\n```', 'multiple_actions'),
                 ('<tool_call>broken', 'malformed_tool_call'),
                 ('```bash\npytest\n```', 'valid')]
        for text, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(diagnose_action(text), expected)

    def test_feedback_is_bounded_and_does_not_echo_untrusted_output(self):
        message = recovery_feedback('output_limit')
        self.assertIn('512-token', message)
        self.assertIn('No command', message)
        self.assertLess(len(message), 600)
        self.assertIn('COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT', recovery_feedback('missing_action'))

    def test_missing_function_tag_seen_in_multifile_run(self):
        # Minimal sanitized reproduction of the observed malformed wrapper.
        text = '<tool_call>\n<parameter=command>\necho ok\n</parameter>\n</function>\n</tool_call>'
        self.assertEqual(diagnose_action(text, 'stop'), 'malformed_tool_call')
        self.assertIn('no tool-call XML', recovery_feedback('malformed_tool_call'))
