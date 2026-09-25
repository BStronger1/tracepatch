"""Validate the published fixture and verifier without Docker or model access."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TASK = Path(__file__).resolve().parents[1] / 'tasks/multifile/job-queue'
FILES = ('config.py', 'queue_store.py', 'worker.py')


class MultifileContractTests(unittest.TestCase):
    def run_fixture(self, broken=()):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            for name in FILES:
                source = TASK / ('workspace' if name in broken else 'oracle') / name
                shutil.copyfile(source, target / name)
            shutil.copyfile(TASK / 'verify.py', target / 'verify.py')
            return subprocess.run([sys.executable, 'verify.py'], cwd=target,
                                  capture_output=True, text=True, timeout=20)

    def test_reference_passes_all_contract_groups(self):
        result = self.run_fixture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Ran 8 tests', result.stderr)

    def test_each_module_regression_is_detected(self):
        for name in FILES:
            with self.subTest(module=name):
                result = self.run_fixture((name,))
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('FAIL:', result.stderr)

    def test_original_fails_for_contract_violations(self):
        result = self.run_fixture(FILES)
        self.assertEqual(result.returncode, 1)
        self.assertIn('AssertionError', result.stderr)
