from solution import retry_call
calls = []
for invalid in (0, -1, True, 1.5, '2'):
    try:
        retry_call(lambda: calls.append(1), invalid)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid attempts accepted')
assert not calls
errors = [TimeoutError('first'), TimeoutError('last')]
def failing():
    error = errors[len(calls)]
    calls.append(1)
    raise error
try:
    retry_call(failing, 2)
except TimeoutError as exc:
    assert exc is errors[-1]
else:
    raise AssertionError('error was swallowed')
assert len(calls) == 2
calls.clear()
def permanent():
    calls.append(1)
    raise ValueError('permanent')
try:
    retry_call(permanent, 3)
except ValueError:
    pass
assert len(calls) == 1
calls.clear()
def eventual():
    calls.append(1)
    if len(calls) == 1:
        raise TimeoutError()
    return 'ok'
assert retry_call(eventual, 3) == 'ok' and len(calls) == 2
print('PASS: retry count, validation, exception identity and early propagation')
