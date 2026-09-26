import json
import tempfile
import unittest
from pathlib import Path
from tracepatch.triage import audit_run, classify


class TriageTests(unittest.TestCase):
    def result(self, passed=False, submitted=False):
        return {'status': 'verified', 'verified_success': passed,
                'agent_exit': 'Submitted' if submitted else 'LimitsExceeded',
                'verification': {'returncode': 0 if passed else 1}}

    def progress(self, *states):
        return {'initial_sha256': 'a' * 64,
                'events': [{'state': s, 'snapshot_sha256': 'b' * 64 if s == 'changed' else 'a' * 64} for s in states]}

    def test_submission_and_acceptance_are_independent(self):
        for passed, submitted, expected in [(True, True, 'verified_submitted'), (True, False, 'verified_without_submission'),
                                            (False, True, 'submitted_but_acceptance_failed')]:
            self.assertEqual(classify(self.result(passed, submitted))['category'], expected)

    def test_missing_and_failed_observations_do_not_mean_no_edits(self):
        self.assertEqual(classify(self.result())['category'], 'acceptance_failed_edits_unknown')
        self.assertEqual(classify(self.result(), self.progress('unknown'))['category'], 'acceptance_failed_edits_unknown')
        self.assertEqual(classify(self.result(), self.progress('unchanged'))['category'], 'acceptance_failed_without_observed_edits')
        reverted = classify(self.result(), self.progress('changed', 'unchanged'))
        self.assertEqual(reverted['category'], 'acceptance_failed_after_observed_edits')
        self.assertFalse(reverted['final_net_source_change'])

    def test_abnormal_verifier_and_conflicting_metadata(self):
        for code in (None, True, 2, -9):
            result = self.result()
            result['verification']['returncode'] = code
            self.assertIsNone(classify(result)['acceptance_passed'])
        result = self.result()
        result['verified_success'] = True
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            classify(result)

    def test_stale_public_success_cannot_describe_final_source(self):
        public = {'current': {'source_sha256': 'a' * 64, 'status': 'passed', 'provenance': 'frozen-public-reproducer'}}
        record = classify(self.result(), self.progress('changed'), public)
        self.assertEqual(record['current_public_status'], 'unknown')
        public['current']['source_sha256'] = 'b' * 64
        self.assertTrue(classify(self.result(), self.progress('changed'), public)['public_pass_but_acceptance_failed'])

    def test_mutating_or_old_python_check_cannot_certify_final_version(self):
        check = {'provenance': 'agent-authored-python', 'source_state': 'changed', 'status': 'process_passed',
                 'source_before_sha256': 'a' * 64, 'source_after_sha256': 'b' * 64}
        record = classify(self.result(), self.progress('changed'), checks=[check])
        self.assertEqual(record['source_changing_python_checks'], 1)
        self.assertIsNone(record['current_python_status'])
        check.update(source_state='unchanged', source_before_sha256='b' * 64)
        self.assertTrue(classify(self.result(), self.progress('changed'), checks=[check])['python_pass_but_acceptance_failed'])
        failed = dict(check, status='process_failed')
        self.assertFalse(classify(self.result(), self.progress('changed'), checks=[check, failed])['python_pass_but_acceptance_failed'])

    def test_file_audit_hashes_evidence_and_excludes_raw_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.result()
            result['verification']['output'] = 'private output; never execute'
            (root / 'result.json').write_text(json.dumps(result))
            record = audit_run(root)
            self.assertEqual(len(record['source_file_hashes']['result.json']), 64)
            self.assertNotIn('private output', json.dumps(record))
            self.assertIsNone(record['observations']['python_check_count'])
