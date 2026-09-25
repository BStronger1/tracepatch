import tempfile
import unittest
from pathlib import Path
from tracepatch.budget import BudgetLedger


class BudgetTests(unittest.TestCase):
    def test_crash_restart_duplicate_and_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ledger.json'
            ledger = BudgetLedger(path, '0.3', '0.1')
            ledger.reserve('a')
            restarted = BudgetLedger(path, '0.3', '0.1')
            with self.assertRaises(ValueError):
                restarted.reserve('a')
            restarted.record('a', {'status': 'request_failed', 'reserved_cny': '0'})
            restarted.reserve('b')
            with self.assertRaises(RuntimeError):
                restarted.reserve('c')
            self.assertEqual(restarted.summary()['remaining_reservation_cny'], '0.0')
            self.assertEqual(len(restarted.read()['requests']), 2)

    def test_lock_and_invalid_amount_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ledger.json'
            ledger = BudgetLedger(path)
            for amount in ('-1', 'NaN', 'Infinity', '0'):
                with self.assertRaises(ValueError):
                    ledger.reserve('bad', amount)
            path.with_suffix('.lock').touch()
            with self.assertRaises(RuntimeError):
                ledger.reserve('busy')
            self.assertEqual(ledger.read()['requests'], [])
