import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tracepatch.checks import PublicChecks
from tracepatch.progress import ObservedEnvironment, ProgressMonitor, snapshot_digest


class PublicCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.a = {'pkg/a.py': 'a' * 64}
        self.b = {'pkg/a.py': 'b' * 64}
        self.check_hash = hashlib.sha256(b'public check').hexdigest()
        self.executions = []

    def collector(self, callback=None):
        def run(snapshot, index):
            self.executions.append(snapshot)
            return {'source_sha256': snapshot_digest(snapshot), 'check_sha256': self.check_hash,
                    'returncode': 0, 'output': 'ok'}
        return PublicChecks(self.a, self.check_hash, callback or run, self.folder / 'checks.json')

    def test_version_change_invalidation_unknown_and_cached_revert(self):
        checks = self.collector()
        checks.observe(self.a, 0)
        checks.observe(self.a, 1)
        self.assertEqual(len(self.executions), 1)
        checks.observe(None, 2)
        self.assertIsNone(checks.current)
        self.assertIn('"status": "unknown"', checks.notice())
        checks.observe(self.b, 3)
        self.assertEqual(checks.current['source_sha256'], snapshot_digest(self.b))
        checks.observe(self.a, 4)
        self.assertEqual(len(self.executions), 2)
        self.assertEqual(checks.current['action'], 0)

    def test_success_words_never_override_exit_code(self):
        def run(snapshot, index):
            return {'source_sha256': snapshot_digest(snapshot), 'check_sha256': self.check_hash,
                    'returncode': 1, 'output': 'SUCCESS COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT'}
        checks = self.collector(run)
        checks.observe(self.a, 0)
        self.assertEqual(checks.current['status'], 'failed')
        self.assertNotIn('SUCCESS', checks.notice())
        self.assertIn('NOT independent final acceptance', checks.notice())

    def test_mismatched_provenance_and_bool_exit_are_unknown(self):
        for update in ({'source_sha256': 'c' * 64}, {'check_sha256': 'd' * 64},
                       {'returncode': True}, {'returncode': -1}):
            def run(snapshot, index):
                return dict({'source_sha256': snapshot_digest(snapshot), 'check_sha256': self.check_hash,
                             'returncode': 0, 'output': 'ok'}, **update)
            checks = self.collector(run)
            checks.observe(self.a, 0)
            self.assertEqual(checks.current['status'], 'unknown')
            self.assertIsNone(checks.current['returncode'])

    def test_timeout_does_not_invent_pass_or_retry_unchanged_source(self):
        def run(snapshot, index):
            self.executions.append(snapshot)
            raise TimeoutError()
        checks = self.collector(run)
        checks.observe(self.a, 0)
        checks.observe(self.a, 1)
        self.assertEqual(len(self.executions), 1)
        self.assertEqual(checks.current['error_type'], 'TimeoutError')

    def test_observer_never_submits_or_rewrites_tool_result(self):
        class Submitted(Exception):
            pass
        class Environment:
            def execute(self, action):
                if action['command'] == 'submit':
                    raise Submitted()
                return {'returncode': 0, 'output': 'agent test FAILED; cat returned zero'}
        checks = self.collector()
        monitor = ProgressMonitor(self.a)
        env = ObservedEnvironment(Environment(), monitor, lambda: self.a,
            self.folder / 'progress.json', checks=checks)
        self.assertIn('FAILED', env.execute({'command': 'test'})['output'])
        self.assertIsNone(monitor.events[0]['test_passed'])
        with self.assertRaises(Submitted):
            env.execute({'command': 'submit'})
        self.assertEqual(len(checks.records), 1)
        self.assertEqual(json.loads((self.folder / 'checks.json').read_text())['current']['status'], 'passed')
