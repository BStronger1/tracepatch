"""Independent contracts for command parameter forwarding; stdlib-only runner."""
import unittest
import click
from click.testing import CliRunner


def command(callback, params=()):
    return click.Command('target', callback=click.pass_context(callback), params=list(params))


class ForwardContract(unittest.TestCase):
    def root(self, **values):
        ctx = click.Context(click.Command('root'))
        ctx.params.update(values)
        return ctx

    def test_multilevel_forward_issue_reproduction(self):
        last = command(lambda ctx, **kw: kw)
        middle = command(lambda ctx, **kw: ctx.forward(last))
        self.assertEqual(self.root(a='alpha', extra='keep').forward(middle), {'a': 'alpha', 'extra': 'keep'})

    def test_direct_command_invoke_records_all_kwargs(self):
        child = command(lambda ctx, **kw: (dict(ctx.params), kw))
        self.assertEqual(self.root().invoke(child, extra=7), ({'extra': 7}, {'extra': 7}))

    def test_defaults_survive_next_forward(self):
        last = command(lambda ctx, **kw: kw)
        middle = command(lambda ctx, **kw: ctx.forward(last), [click.Option(['--count'], default=3)])
        self.assertEqual(self.root().forward(middle), {'count': 3})

    def test_explicit_overrides_include_false_and_none(self):
        child = command(lambda ctx, **kw: (dict(ctx.params), kw))
        for value in (None, False, 0, '', 'override'):
            with self.subTest(value=value):
                result = self.root(value='parent').forward(child, value=value)
                self.assertEqual(result, ({'value': value}, {'value': value}))

    def test_parent_params_are_not_changed_or_aliased(self):
        parent = self.root(value='parent')
        def callback(ctx, **kw):
            self.assertEqual(ctx.params, {'value': 'child'})
            ctx.params['added'] = 2
        parent.forward(command(callback), value='child')
        self.assertEqual(parent.params, {'value': 'parent'})

    def test_command_context_identity_and_parent(self):
        parent = self.root()
        child = command(lambda ctx, **kw: (ctx.command, ctx.parent, ctx is parent))
        self.assertEqual(parent.invoke(child), (child, parent, False))

    def test_callback_invocation_keeps_current_context(self):
        parent = self.root(existing=2)
        @click.pass_context
        def callback(ctx, arg, **kw):
            return ctx is parent, arg, kw, dict(ctx.params)
        self.assertEqual(parent.invoke(callback, 4, extra=5), (True, 4, {'extra': 5}, {'existing': 2}))

    def test_nonexposed_defaults_are_not_injected(self):
        child = command(lambda ctx, **kw: (dict(ctx.params), kw),
                        [click.Option(['--secret'], default=5, expose_value=False)])
        self.assertEqual(self.root().invoke(child), ({}, {}))

    def test_invalid_forward_and_missing_callback_errors_remain(self):
        parent = self.root()
        with self.assertRaises(TypeError):
            parent.forward(lambda: None)
        with self.assertRaises(TypeError):
            parent.invoke(click.Command('empty'))

    def test_cli_three_levels_and_return_value(self):
        last = command(lambda ctx, **kw: (kw, dict(ctx.params)))
        middle = command(lambda ctx, **kw: ctx.forward(last), [click.Option(['--other'], default=9)])
        @click.command()
        @click.option('--count', type=int)
        @click.option('--extra')
        @click.pass_context
        def first(ctx, **kw):
            return ctx.forward(middle)
        result = CliRunner().invoke(first, ['--count', '6', '--extra', 'retain'], standalone_mode=False)
        self.assertIsNone(result.exception, str(result.exception))
        expected = {'count': 6, 'extra': 'retain', 'other': 9}
        self.assertEqual(result.return_value, (expected, expected))


if __name__ == '__main__':
    unittest.main(verbosity=2)
