"""Minimal public behavior from Click's multi-level forwarding issue."""
import click


@click.command()
@click.pass_context
def last(ctx, **values):
    return dict(values)


@click.command()
@click.pass_context
def middle(ctx, **values):
    return ctx.forward(last)


root = click.Context(click.Command('root'))
root.params = {'name': 'example', 'extra': 'keep'}
assert root.forward(middle) == {'name': 'example', 'extra': 'keep'}, 'Forwarded parameters disappeared'
print('Parameters survived multiple forwarding levels')
