"""Minimal public reproduction of Click issue 2040; not full acceptance."""
from click import Choice, Command, Option
from click.shell_completion import ShellComplete

command = Command('demo', params=[Option(['-c'], type=Choice(['+red', '+blue', 'plain']))])
items = ShellComplete(command, {}, 'demo', '_DEMO_COMPLETE').get_completions(['-c'], '+')
assert [item.value for item in items] == ['+red', '+blue']
print('Public symbol-value reproduction passed')
