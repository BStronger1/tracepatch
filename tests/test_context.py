import json
import tempfile
import unittest
from pathlib import Path
from tracepatch.context import preserve_observation


class ContextTests(unittest.TestCase):
    def test_complete_evidence_and_valid_bounded_json(self):
        with tempfile.TemporaryDirectory() as folder:
            original = {'returncode': 1, 'output': 'START' + '\n"中' * 5000 + 'END'}
            result = preserve_observation(original, Path(folder), 1000)
            self.assertLessEqual(len(result['content']), 1000)
            preview = json.loads(result['content'])
            self.assertEqual(preview['returncode'], 1)
            self.assertTrue(preview['head'].startswith('START'))
            self.assertTrue(preview['tail'].endswith('END'))
            stored = Path(folder) / (result['evidence_sha256'] + '.json')
            self.assertEqual(json.loads(stored.read_text(encoding='utf-8')), original)
            self.assertEqual(preserve_observation(original, Path(folder), 1000), result)

    def test_small_observation_unchanged_and_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            original = {'returncode': 0, 'output': 'ok'}
            result = preserve_observation(original, Path(folder))
            self.assertFalse(result['truncated'])
            self.assertEqual(json.loads(result['content']), original)
            path = Path(folder) / (result['evidence_sha256'] + '.json')
            path.write_text('changed', encoding='utf-8')
            with self.assertRaises(ValueError):
                preserve_observation(original, Path(folder))
