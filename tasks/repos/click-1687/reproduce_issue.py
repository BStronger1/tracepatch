"""Minimal symptom for repeated option default inference, not a reference fix."""
import click
from click.testing import CliRunner

option = click.Option(['--count'], multiple=True, default=(2, 5))
assert option.nargs == 1, 'A scalar repeated default must not imply a two-value option'
command = click.Command('sample', params=[option], callback=lambda count: count)
result = CliRunner().invoke(command, [], standalone_mode=False)
assert result.exception is None, str(result.exception)
assert result.return_value == (2, 5), repr(result.return_value)
print('Repeated scalar defaults preserved')
