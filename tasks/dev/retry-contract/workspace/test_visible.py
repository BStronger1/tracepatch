from solution import retry_call
assert retry_call(lambda: 42, 2) == 42
try:
    retry_call(lambda: 42, 0)
except ValueError:
    print('visible tests passed')
else:
    raise AssertionError('zero attempts must raise')
