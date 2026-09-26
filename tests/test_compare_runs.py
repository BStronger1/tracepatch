import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('compare_runs', Path(__file__).resolve().parents[1] / 'scripts/compare-runs.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CompareRunsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.left, self.right = [Path(self.temporary.name) / n for n in ('left', 'right')]
        for folder, limit in ((self.left, 512), (self.right, 1024)):
            folder.mkdir()
            manifest = {'tasks': {'example': 'hash'}, 'policy': 'recovery-budget',
                        'context_policy': 'recent-turns', 'model': 'fixed', 'max_output_tokens': limit}
            (folder / 'manifest.json').write_text(json.dumps(manifest))
            result = {'task': 'example', 'verified_success': False, 'agent_exit': 'LimitsExceeded',
                      'api_calls': 2, 'estimated_known_no_cache_cny': 0.001, 'unknown_cost_requests': 0}
            (folder / 'summary.json').write_text(json.dumps({'tasks': [result]}))
            for name in ('runner', 'runtime', 'budget', 'actions', 'recovery', 'window', 'toolcalling'):
                (folder / (name + '.snapshot.py')).write_text('same implementation')

    def test_output_difference_requires_explicit_intervention(self):
        with self.assertRaisesRegex(ValueError, 'max_output_tokens'):
            module.compare(self.left, self.right)
        result = module.compare(self.left, self.right, intervention='output-budget')
        self.assertTrue(result['controls_match'])
        self.assertEqual(result['intervention_fields'], ['max_output_tokens'])
        self.assertEqual([arm['max_output_tokens'] for arm in result['arms']], [512, 1024])

    def test_output_comparison_rejects_other_policy_or_task_changes(self):
        path = self.right / 'manifest.json'
        original = json.loads(path.read_text())
        for key, value in [('policy', 'baseline'), ('context_policy', 'none'),
                           ('model', 'different'), ('tasks', {'example': 'other hash'}),
                           ('source_layout', {'source': 'different'})]:
            path.write_text(json.dumps(dict(original, **{key: value})))
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, key):
                module.compare(self.left, self.right, intervention='output-budget')

    def test_output_comparison_rejects_changed_runtime(self):
        (self.right / 'runtime.snapshot.py').write_text('different implementation')
        with self.assertRaisesRegex(ValueError, 'runtime'):
            module.compare(self.left, self.right, intervention='output-budget')

    def test_repository_snapshot_mismatch_is_rejected(self):
        (self.left/'repositories.snapshot.py').write_text('layout code')
        with self.assertRaisesRegex(ValueError,'Missing repository'):
            module.compare(self.left,self.right,intervention='output-budget')
        (self.right/'repositories.snapshot.py').write_text('changed layout code')
        with self.assertRaisesRegex(ValueError,'Different repository'):
            module.compare(self.left,self.right,intervention='output-budget')

    def test_progress_intervention_keeps_observation_and_controls_equal(self):
        for folder, mode in ((self.left, 'observe'), (self.right, 'feedback')):
            path = folder / 'manifest.json'
            manifest = json.loads(path.read_text())
            manifest.update(progress_mode=mode, max_output_tokens=1024, progress_threshold=6)
            path.write_text(json.dumps(manifest))
            (folder / 'progress.snapshot.py').write_text('same sensor')
        result = module.compare(self.left, self.right, intervention='progress-feedback')
        self.assertEqual(result['intervention_fields'], ['progress_mode'])
        with self.assertRaisesRegex(ValueError, 'progress_mode'):
            module.compare(self.left, self.right)
        path = self.right / 'manifest.json'
        manifest = json.loads(path.read_text())
        manifest['progress_threshold'] = 3
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'progress_threshold'):
            module.compare(self.left, self.right, intervention='progress-feedback')

    def test_memory_intervention_requires_matching_collectors_and_limits(self):
        for folder, mode in ((self.left, 'observe'), (self.right, 'recall')):
            path = folder / 'manifest.json'
            manifest = json.loads(path.read_text())
            manifest.update(memory_mode=mode, max_output_tokens=1024, memory_byte_limit=4200)
            path.write_text(json.dumps(manifest))
            for name in ('memory', 'context'):
                (folder / f'{name}.snapshot.py').write_text('same collector')
        result = module.compare(self.left, self.right, intervention='evidence-memory')
        self.assertEqual(result['intervention_fields'], ['memory_mode'])
        (self.right / 'memory.snapshot.py').write_text('different collector')
        with self.assertRaisesRegex(ValueError, 'memory'):
            module.compare(self.left, self.right, intervention='evidence-memory')

    def test_structured_intervention_keeps_memory_enabled_in_both_arms(self):
        for folder, profile in ((self.left, 'excerpts'), (self.right, 'structured')):
            path = folder / 'manifest.json'
            manifest = json.loads(path.read_text())
            manifest.update(memory_mode='recall', memory_profile=profile, max_output_tokens=1024)
            path.write_text(json.dumps(manifest))
            for name in ('memory', 'context', 'symbols'):
                (folder / f'{name}.snapshot.py').write_text('same')
        result = module.compare(self.left, self.right, intervention='structured-evidence')
        self.assertEqual(result['intervention_fields'], ['memory_profile'])
        path = self.right / 'manifest.json'
        manifest = json.loads(path.read_text())
        manifest['memory_mode'] = 'observe'
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'requires recall'):
            module.compare(self.left, self.right, intervention='structured-evidence')

    def test_public_check_feedback_requires_identical_schedule_and_implementation(self):
        for folder, mode in ((self.left, 'observe'), (self.right, 'feedback')):
            path = folder / 'manifest.json'
            manifest = json.loads(path.read_text())
            manifest.update(check_mode=mode, check_schedule='every-new-version', max_output_tokens=1024)
            path.write_text(json.dumps(manifest))
            (folder / 'checks.snapshot.py').write_text('same')
        result = module.compare(self.left, self.right, intervention='public-check-feedback')
        self.assertEqual(result['intervention_fields'], ['check_mode'])
        (self.right / 'checks.snapshot.py').write_text('different')
        with self.assertRaisesRegex(ValueError, 'Different snapshot: checks'):
            module.compare(self.left, self.right, intervention='public-check-feedback')
