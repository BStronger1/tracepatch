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
