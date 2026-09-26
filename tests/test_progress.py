import unittest
import json
import tempfile
from pathlib import Path
from tracepatch.progress import ProgressMonitor, ObservedEnvironment, validate_snapshot


class ProgressTests(unittest.TestCase):
    def test_different_commands_can_trigger_same_source_signal(self):
        monitor = ProgressMonitor({'pkg/a.py': 'a' * 64}, threshold=3)
        for command in ('cat pkg/a.py', 'head pkg/a.py', 'grep def pkg/a.py'):
            monitor.observe({'pkg/a.py': 'a' * 64}, command=command, returncode=0)
        self.assertEqual(monitor.report()['summary']['review_signals'], 1)
        self.assertEqual(len({e['command_sha256'] for e in monitor.events}), 3)
        self.assertIn('does not prove a stall', monitor.notice())
        self.assertTrue(all(e['test_passed'] is None for e in monitor.events))

    def test_change_revert_and_delete_do_not_imply_success(self):
        monitor = ProgressMonitor({'pkg/a.py': 'a' * 64})
        change = monitor.observe({'pkg/a.py': 'b' * 64}, returncode=1)
        self.assertEqual(change['net_changed_paths'], ['pkg/a.py'])
        reverted = monitor.observe({'pkg/a.py': 'a' * 64})
        self.assertEqual(reverted['state'], 'changed')
        self.assertEqual(reverted['net_changed_paths'], [])
        removed = monitor.observe({'pkg/a.py': None})
        self.assertEqual(removed['changed_paths'], ['pkg/a.py'])
        self.assertIsNone(monitor.notice())

    def test_missing_observation_breaks_streak_without_inventing_change(self):
        state = {'pkg/a.py': 'a' * 64}
        monitor = ProgressMonitor(state, threshold=2)
        monitor.observe(state)
        unknown = monitor.observe(None, error='TimeoutExpired')
        self.assertEqual(unknown['state'], 'unknown')
        recovered = monitor.observe(state)
        self.assertEqual(recovered['state'], 'reanchored')
        self.assertIsNone(recovered['changed_paths'])
        self.assertEqual(recovered['unchanged_streak'], 0)
        monitor.observe(state)
        self.assertIsNone(monitor.notice())
        monitor.observe(state)
        self.assertIsNotNone(monitor.notice())

    def test_signal_cadence_and_edit_reset(self):
        state = {'pkg/a.py': 'a' * 64}
        monitor = ProgressMonitor(state, threshold=2)
        signals = [monitor.observe(state)['signal'] for _ in range(5)]
        self.assertEqual([i for i, signal in enumerate(signals, 1) if signal], [2, 4])
        monitor.observe({'pkg/a.py': 'b' * 64})
        self.assertEqual(monitor.unchanged, 0)
        self.assertIsNone(monitor.notice())

    def test_bad_snapshot_is_not_a_valid_no_change_observation(self):
        for state in ({'../a.py': 'a' * 64}, {'/a.py': 'a' * 64},
                      {'a.py': 'bad'}, {'a.txt': 'a' * 64}):
            with self.subTest(state=state), self.assertRaises(ValueError):
                ProgressMonitor(state)
        with self.assertRaises(ValueError):
            validate_snapshot({}, ['a.py'])
        with self.assertRaises(ValueError):
            ProgressMonitor({'a.py': 'a' * 64}, threshold=True)

    def test_observer_preserves_results_and_submission_exceptions(self):
        state = {'pkg/a.py': 'a' * 64}
        class Finished(Exception):
            pass
        class Environment:
            def execute(self, action):
                if action['command'] == 'submit':
                    raise Finished()
                return {'returncode': 7, 'output': 'failed'}
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'progress.json'
            monitor = ProgressMonitor(state)
            env = ObservedEnvironment(Environment(), monitor, lambda: state, output)
            self.assertEqual(env.execute({'command': 'check'})['returncode'], 7)
            with self.assertRaises(Finished):
                env.execute({'command': 'submit'})
            events = json.loads(output.read_text())['events']
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]['tool_returncode'], 7)
            self.assertIsNone(events[1]['tool_returncode'])

    def test_sensor_failure_keeps_tool_result_and_records_unknown(self):
        class Environment:
            def execute(self, action):
                return {'returncode': 0}
        def fail():
            raise TimeoutError('Not a no-op')
        with tempfile.TemporaryDirectory() as folder:
            monitor = ProgressMonitor({'pkg/a.py': 'a' * 64})
            env = ObservedEnvironment(Environment(), monitor, fail, Path(folder) / 'p.json')
            self.assertEqual(env.execute({'command': 'read'})['returncode'], 0)
            self.assertEqual(monitor.events[0]['state'], 'unknown')
            self.assertEqual(monitor.events[0]['observation_error'], 'TimeoutError')
