"""Frozen behavior checks; run independently of agent-written tests."""
import unittest
from click import Argument, Choice, Command, Group, Option, Path
from click.shell_completion import CompletionItem, ShellComplete


def items(command, args, incomplete):
    return ShellComplete(command, {}, 'demo', '_DEMO_COMPLETE').get_completions(args, incomplete)


def words(command, args, incomplete):
    return [item.value for item in items(command, args, incomplete)]


class CompletionContract(unittest.TestCase):
    def test_symbol_value_reproduction(self):
        for prefix in ('+', '!', '~', '@', '/'):
            with self.subTest(prefix=prefix):
                choices = [prefix + 'red', prefix + 'blue', 'plain']
                command = Command('demo', params=[Option(['-c'], type=Choice(choices))])
                self.assertEqual(words(command, ['-c'], prefix), choices[:2])

    def test_registered_plus_prefix_keeps_option_precedence(self):
        command = Command('demo', params=[Option(['-c'], type=Choice(['+red'])), Option(['+extra'], is_flag=True)])
        self.assertEqual(words(command, ['-c'], '+'), ['+extra'])
        self.assertEqual(words(command, ['-c'], ''), ['+red'])

    def test_registered_slash_prefix_keeps_option_precedence(self):
        command = Command('demo', params=[Option(['-c'], type=Choice(['/red'])), Option(['/extra'], is_flag=True)])
        self.assertEqual(words(command, ['-c'], '/'), ['/extra'])

    def test_count_option_does_not_request_a_value(self):
        def complete_count(ctx, param, incomplete):
            return ['WRONG-count-value']
        command = Command('demo', params=[Option(['-v'], count=True, shell_complete=complete_count), Argument(['dest'], type=Choice(['north', 'south']))])
        self.assertEqual(words(command, ['-v'], ''), ['north', 'south'])
        self.assertEqual(words(command, ['-v', '-v'], 'n'), ['north'])

    def test_boolean_flag_does_not_request_a_value(self):
        command = Command('demo', params=[Option(['--on/--off']), Argument(['dest'], type=Choice(['north']))])
        self.assertEqual(words(command, ['--on'], 'n'), ['north'])
        self.assertEqual(words(command, [], '--o'), ['--on', '--off'])

    def test_multivalue_symbol_argument_scanning(self):
        command = Command('demo', params=[Option(['-c'], type=Choice(['!one', '!two']), nargs=2)])
        self.assertEqual(words(command, ['-c', '!one'], '!'), ['!one', '!two'])
        self.assertEqual(words(command, ['-c', '!one', '!two'], ''), [])

    def test_repeat_option_still_accepts_values(self):
        command = Command('demo', params=[Option(['-c'], type=Choice(['+one', '+two']), multiple=True)])
        self.assertEqual(words(command, ['-c', '+one', '-c'], '+'), ['+one', '+two'])
        self.assertIn('-c', words(command, ['-c', '+one'], '-'))

    def test_equals_syntax_preserves_symbol_value(self):
        command = Command('demo', params=[Option(['--color'], type=Choice(['!red', '!rose', 'blue']))])
        self.assertEqual(words(command, [], '--color=!r'), ['!red', '!rose'])

    def test_double_dash_preserves_positional_values(self):
        command = Command('demo', params=[Option(['--other']), Argument(['dest'], type=Choice(['--red', '--rose']))])
        self.assertEqual(words(command, ['--'], '--r'), ['--red', '--rose'])

    def test_absolute_path_completion_metadata(self):
        command = Command('demo', params=[Option(['-p'], type=Path())])
        result = items(command, ['-p'], '/tmp/target')
        self.assertEqual([(x.value, x.type) for x in result], [('/tmp/target', 'file')])

    def test_nested_context_prefixes_do_not_leak_from_siblings(self):
        plain = Command('plain', params=[Option(['-c'], type=Choice(['+red', '+rose']))])
        custom = Command('custom', params=[Option(['-c'], type=Choice(['+red'])), Option(['+extra'], is_flag=True)])
        command = Group('demo', commands=[plain, custom])
        self.assertEqual(words(command, ['plain', '-c'], '+'), ['+red', '+rose'])
        self.assertEqual(words(command, ['custom', '-c'], '+'), ['+extra'])

    def test_custom_completion_and_regular_option_names(self):
        def complete(ctx, param, incomplete):
            return [CompletionItem(incomplete + 'done', help='custom help')]
        command = Command('demo', params=[Option(['--value'], shell_complete=complete), Option(['--hidden'], hidden=True)])
        result = items(command, ['--value'], '!')
        self.assertEqual([(x.value, x.help) for x in result], [('!done', 'custom help')])
        self.assertEqual(words(command, [], '--'), ['--value', '--help'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
