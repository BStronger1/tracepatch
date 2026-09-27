import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from tracepatch.editing import replace_source, validate_edit, EditingEnvironment
from tracepatch.toolcalling import parse_tool_call, validate_history


class EditingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / 'a.py'
        self.source.write_bytes(b'x = 1\n')

    def edit(self, old='x = 1', new='x = 2', path='a.py'):
        return replace_source(self.root, ['a.py'], {'path': path, 'old': old, 'new': new})

    def test_applied_hashes_and_no_source_execution(self):
        result = self.edit(new='raise RuntimeError("not executed")')
        self.assertEqual(result['status'], 'applied')
        self.assertEqual(result['file_after_sha256'], hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertIsNone(result['acceptance_verified'])

    def test_missing_ambiguous_overlapping_and_noop_leave_file_unchanged(self):
        for content, old, new, status in [('x = 1\n', 'missing', 'x', 'old_text_not_found'),
                ('# aaa\n', 'aa', 'b', 'ambiguous_match'), ('x = 1\n', 'x', 'x', 'no_change')]:
            self.source.write_text(content)
            before = self.source.read_bytes()
            self.assertEqual(self.edit(old, new)['status'], status)
            self.assertEqual(self.source.read_bytes(), before)

    def test_syntax_failure_never_writes(self):
        self.assertEqual(self.edit(new='if (')['status'], 'syntax_error')
        self.assertEqual(self.source.read_bytes(), b'x = 1\n')

    def test_path_allowlist_rejects_traversal_and_new_files(self):
        for path in ('../a.py', '/a.py', 'new.py', './a.py', 'a\\b.py'):
            self.assertEqual(self.edit(path=path)['status'], 'path_not_allowed')
        self.assertEqual(list(self.root.iterdir()), [self.source])

    def test_uniform_line_endings_preserved_across_json_styles(self):
        for source, old, new, expected in [
                (b'x = 1\r\ny = 2\r\n', 'x = 1\ny = 2', 'x = 3\ny = 4', b'x = 3\r\ny = 4\r\n'),
                (b'x = 1\ny = 2\n', 'x = 1\r\ny = 2', 'x = 3\r\ny = 4', b'x = 3\ny = 4\n')]:
            self.source.write_bytes(source)
            result = self.edit(old, new)
            self.assertEqual(result['status'], 'applied')
            self.assertEqual(result['match_mode'], 'line-ending-normalized')
            self.assertEqual(self.source.read_bytes(), expected)
        before = self.source.read_bytes()
        self.assertEqual(self.edit('x = 3\r\ny = 4', 'x = 3\ny = 4')['status'], 'no_change')
        self.assertEqual(self.source.read_bytes(), before)

    def test_mixed_line_endings_and_other_whitespace_are_not_normalized(self):
        source = b'x = 1\r\ny = 2\n'
        self.source.write_bytes(source)
        self.assertEqual(self.edit('x = 1\ny = 2', 'x = 3')['status'], 'old_text_not_found')
        self.assertEqual(self.edit('x=1', 'x=3')['status'], 'old_text_not_found')
        self.assertEqual(self.source.read_bytes(), source)

    def test_schema_limits_and_empty_replacement(self):
        for edit in ({}, {'path': 'a.py', 'old': '', 'new': ''}, {'path': 'a.py', 'old': 'x', 'new': '\x00'},
                     {'path': 'a.py', 'old': 'x', 'new': 'a' * 16000}):
            with self.assertRaises(ValueError): validate_edit(edit)
        self.assertEqual(self.edit('x = 1', '')['status'], 'applied')

    def test_protocol_is_opt_in_and_history_stays_paired(self):
        args = {'path': 'a.py', 'old': 'x = 1', 'new': 'x = 2'}
        message = {'role': 'assistant', 'tool_calls': [{'id': 'edit1', 'type': 'function',
                    'function': {'name': 'replace_text', 'arguments': json.dumps(args)}}]}
        with self.assertRaises(ValueError): parse_tool_call(message, 'tool_calls')
        parsed, _ = parse_tool_call(message, 'tool_calls', allow_replace_text=True)
        self.assertEqual(json.loads(parsed), args)
        with self.assertRaises(ValueError): validate_history([message], allow_replace_text=True)
        validate_history([message, {'role': 'tool', 'tool_call_id': 'edit1', 'content': '{}'}], allow_replace_text=True)

    def test_executor_error_is_unknown_and_recorded(self):
        def fail(edit): raise OSError('unavailable')
        env = EditingEnvironment(None, fail, self.root / 'records')
        result = env.execute({'tool': 'replace_text', 'edit': {'path': 'a.py', 'old': 'x', 'new': 'y'}})
        self.assertEqual(result['status'], 'unknown')
        self.assertIsNone(result['acceptance_verified'])
        self.assertTrue((self.root / 'records/001.json').exists())
