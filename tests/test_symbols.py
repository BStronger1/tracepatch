import hashlib
import tempfile
import unittest
from pathlib import Path
from tracepatch.symbols import source_context, task_cues
from tracepatch.memory import EvidenceMemory


class SymbolTests(unittest.TestCase):
    def test_function_body_resolves_complete_signature_and_class(self):
        source = 'class Item(Base):\n    def __init__(\n        self, value, /, *, flag=False, **attrs\n    ):\n        self.value = value\n'
        result = source_context(source, 5, 5)
        scope = result['scopes'][0]
        self.assertEqual(scope['qualified_name'], 'Item.__init__')
        self.assertEqual(scope['signature'], 'def __init__(self, value, /, *, flag=False, **attrs):')
        self.assertEqual(scope['parameters'], ['self', 'value', 'flag', 'attrs'])
        self.assertEqual(scope['class_bases'], ['Base'])
        self.assertFalse(scope['signature_omitted'])

    def test_nested_scope_async_and_annotations(self):
        source = 'def outer(value):\n    async def inner(x: int, *items) -> str:\n        return str(x)\n    return inner\n'
        scope = source_context(source, 3, 3)['scopes'][0]
        self.assertEqual(scope['qualified_name'], 'outer.inner')
        self.assertEqual(scope['signature'], 'async def inner(x: int, *items) -> str:')
        self.assertNotIn('value', scope['parameters'])

    def test_invalid_source_is_unknown_and_defaults_never_execute(self):
        self.assertEqual(source_context('def broken(', 1, 1)['parse_error'], 'SyntaxError')
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / 'must-not-exist'
            source = f"def f(x=open({str(marker)!r}, 'w')):\n    return x\n"
            self.assertTrue(source_context(source, 2, 2)['scopes'])
            self.assertFalse(marker.exists())

    def test_oversized_signature_is_omitted_not_cut(self):
        source = 'def f(' + ','.join(f'argument_{i}' for i in range(160)) + '):\n    pass\n'
        scope = source_context(source, 2, 2)['scopes'][0]
        self.assertIsNone(scope['signature'])
        self.assertTrue(scope['signature_omitted'])

    def test_task_cues_are_exact_original_spans(self):
        task = 'Fix copying. Preserve the type and policy. A subclass may require arguments. Do not reset state.'
        result = task_cues(task)
        self.assertEqual(result['task_sha256'], hashlib.sha256(task.encode()).hexdigest())
        self.assertEqual(len(result['clauses']), 3)
        for clause in result['clauses']:
            self.assertEqual(task[clause['start']:clause['end']], clause['text'])

    def test_profiles_share_cards_and_stale_signatures_are_not_recalled(self):
        source = 'def copy(jar):\n    return jar\n'
        version = hashlib.sha256(source.encode()).hexdigest()
        state = {'pkg.py': version}
        def reader(ranges):
            return [dict(r, version=version, excerpt='    return jar', excerpt_truncated=False,
                         context=source_context(source, r['start'], r['end'])) for r in ranges]
        with tempfile.TemporaryDirectory() as folder:
            memory = EvidenceMemory(['pkg.py'], Path(folder) / 'memory.json', reader,
                                    instruction='Preserve subclass state. A subclass may require arguments.')
            memory.observe(1, 'sed -n 2p pkg.py', {'returncode': 0, 'output': 'return jar'}, state, state)
            plain, _ = memory.recall(state)
            structured, cards = memory.recall(state, profile='structured')
            self.assertNotIn('def copy(jar)', plain)
            self.assertIn('def copy(jar)', structured)
            self.assertIn('Preserve subclass state.', structured)
            self.assertEqual(cards[0]['source_status'], 'original_task')
            stale, _ = memory.recall({'pkg.py': '0' * 64}, profile='structured')
            self.assertNotIn('def copy(jar)', stale)
            self.assertIn('stale', stale)
            self.assertLessEqual(len(structured.encode()), 4200)
