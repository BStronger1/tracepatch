import unittest
from tracepatch.progress import snapshot_digest
from tracepatch.stages import decide_stage, stage_notice, stage_tool_options
from tracepatch.toolcalling import TEST_TOOL_OPTIONS


class StageTests(unittest.TestCase):
    initial = {'a.py': 'a' * 64}
    changed = {'a.py': 'b' * 64}

    def check(self, snapshot, status='process_passed', **extra):
        digest = snapshot_digest(snapshot)
        return dict(provenance='agent-authored-python', source_state='unchanged',
            source_before_sha256=digest, source_after_sha256=digest,
            status=status, check_sha256='c' * 64, **extra)

    def decide(self, snapshot=None, checks=(), used=6, public=None):
        return decide_stage(self.initial, self.initial if snapshot is None else snapshot,
                            checks, public, used, 24)

    def test_inspection_boundary_and_fixed_check_gate(self):
        self.assertEqual(self.decide(used=5)['stage'], 'inspect')
        state = self.decide(used=6)
        self.assertEqual(state['stage'], 'check_hypothesis')
        self.assertEqual(state['required_tool'], 'python_check')
        self.assertIn('must call python_check', stage_notice(state))

    def test_new_patch_requires_check_even_before_inspection_boundary(self):
        old = self.check(self.initial)
        state = self.decide(self.changed, [old], used=2)
        self.assertEqual(state['stage'], 'check_patch')
        self.assertEqual(state['required_tool'], 'python_check')
        current = self.check(self.changed)
        public = {'status': 'passed', 'source_sha256': snapshot_digest(self.changed)}
        ready = self.decide(self.changed, [current], public=public)
        self.assertEqual(ready['stage'], 'review_submission')
        self.assertIsNone(ready['required_tool'])
        self.assertIn('not independent acceptance', stage_notice(ready))

    def test_no_change_after_check_directs_implementation_not_dummy_edits(self):
        state = self.decide(checks=[self.check(self.initial, 'process_failed')])
        self.assertEqual(state['stage'], 'implement')
        self.assertIsNone(state['required_tool'])
        self.assertIn('cosmetic edits', stage_notice(state))

    def test_changed_source_during_test_cannot_certify_current_version(self):
        record = self.check(self.initial)
        record.update(source_after_sha256=snapshot_digest(self.changed), source_state='changed')
        self.assertEqual(self.decide(self.changed, [record])['stage'], 'check_patch')
        record.update(source_state='unchanged', source_before_sha256=snapshot_digest(self.changed),
                      provenance='shell-output')
        self.assertEqual(self.decide(self.changed, [record])['stage'], 'check_patch')

    def test_failed_or_stale_evidence_never_directs_submission(self):
        for status in ('process_failed', 'unknown', 'timed_out'):
            state = self.decide(self.changed, [self.check(self.changed, status)],
                public={'source_sha256': snapshot_digest(self.changed), 'status': 'passed'})
            self.assertNotEqual(state['stage'], 'review_submission')
        stale_public = {'source_sha256': snapshot_digest(self.initial), 'status': 'passed'}
        state = self.decide(self.changed, [self.check(self.changed)], public=stale_public)
        self.assertEqual(state['public_status'], 'unknown')
        self.assertEqual(state['stage'], 'repair_or_recheck')

    def test_latest_matching_failure_overrides_old_pass(self):
        records = [self.check(self.changed), self.check(self.changed, 'process_failed')]
        state = self.decide(self.changed, records,
            public={'source_sha256': snapshot_digest(self.changed), 'status': 'passed'})
        self.assertEqual(state['stage'], 'repair_or_recheck')

    def test_unknown_sensor_and_final_budget_never_force_submission(self):
        for snapshot in (None, {'a.py': None}):
            state = decide_stage(self.initial, snapshot, [], None, 8, 24)
            self.assertEqual(state['stage'], 'observation_unknown')
            self.assertIsNone(state['required_tool'])
        for used in (22, 23):
            state = self.decide(self.changed, used=used)
            self.assertEqual(state['stage'], 'final_review')
            self.assertIsNone(state['required_tool'])

    def test_routing_is_opt_in_and_does_not_mutate_shared_options(self):
        state = self.decide()
        observed = stage_tool_options(TEST_TOOL_OPTIONS, state, enabled=False)
        guided = stage_tool_options(TEST_TOOL_OPTIONS, state, enabled=True)
        self.assertEqual(observed['tool_choice'], 'required')
        self.assertEqual(guided['tool_choice']['function']['name'], 'python_check')
        self.assertEqual(TEST_TOOL_OPTIONS['tool_choice'], 'required')
        with self.assertRaises(ValueError):
            stage_tool_options({'tools': []}, state, enabled=True)
