import unittest
from tracepatch.lifecycle import budget_notice, completion_status, prepare_messages


class LifecycleTests(unittest.TestCase):
    def test_submission_aware_guidance_preserves_original_policy(self):
        messages = [{'role': 'user', 'content': 'task'}]
        _, old = prepare_messages(messages, 11, 12, 'recovery-budget')
        _, new = prepare_messages(messages, 11, 12, 'recovery-submit')
        self.assertIn('&& echo', old)
        self.assertNotIn('FIRST output line', old)
        self.assertIn('FIRST output line', new)
        self.assertIn('BOTH stdout and stderr', new)
        self.assertIn('exit nonzero', new)
        self.assertIn('separate bash call', new)
        self.assertEqual(budget_notice(0, 12), budget_notice(0, 12, submission_aware=True))
        self.assertEqual(messages, [{'role': 'user', 'content': 'task'}])

    def test_boundary_includes_current_call(self):
        self.assertIn('12 model calls remain INCLUDING', budget_notice(0, 12))
        self.assertIn('reserve a call', budget_notice(9, 12))
        final = budget_notice(11, 12)
        self.assertIn('1 model calls remain INCLUDING', final)
        self.assertIn('&& echo', final)
        self.assertIn('do not claim completion', final)

    def test_invalid_or_exhausted_budget(self):
        for used, limit in ((12, 12), (13, 12), (-1, 12), (0, 0), (True, 12), (0, 1.5)):
            with self.subTest(used=used, limit=limit), self.assertRaises(ValueError):
                budget_notice(used, limit)

    def test_new_policy_does_not_mutate_history_or_baseline(self):
        messages = [{'role': 'user', 'content': 'task', 'extra': {'private': 'metadata'}}]
        for policy in ('baseline', 'recovery'):
            wire, notice = prepare_messages(messages, 11, 12, policy)
            self.assertEqual(wire, [{'role': 'user', 'content': 'task'}])
            self.assertIsNone(notice)
        wire, notice = prepare_messages(messages, 11, 12, 'recovery-budget')
        self.assertEqual(wire[-1]['content'], notice)
        self.assertEqual(len(messages), 1)
        self.assertEqual(len(wire), 2)

    def test_submission_never_implies_correctness(self):
        for exit_name in ('Submitted', 'LimitsExceeded', 'RepeatedFormatError', None):
            for code in (0, 1, None):
                with self.subTest(exit=exit_name, code=code):
                    result = completion_status(exit_name, {'returncode': code})
                    self.assertIs(result['patch_verified'], None if code is None else code == 0)
                    self.assertEqual(result['agent_submitted'], exit_name == 'Submitted')
        self.assertEqual(completion_status('LimitsExceeded', {'returncode': 0})['state'], 'verified_unsubmitted')
        self.assertEqual(completion_status('Submitted', None)['state'], 'unverified_submitted')
        self.assertIsNone(completion_status('Submitted', {'returncode': False})['patch_verified'])
