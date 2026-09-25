from solution import resolve_port
assert resolve_port(0, {'PORT': '9000'}, {'port': 7000}) == 0
assert resolve_port('', {'PORT': '0'}, {'port': 7000}) == 0
assert resolve_port(None, {'PORT': ''}, {'port': '65535'}) == 65535
assert resolve_port(None, {}, {}) == 8000
for invalid in (-1, 65536, True, 3.2, 'abc', '-1', '+2', '１２'):
    try:
        resolve_port(invalid, {'PORT': '9000'}, {})
    except ValueError:
        pass
    else:
        raise AssertionError(f'accepted invalid value {invalid!r}')
print('PASS: precedence, absence, bounds and invalid-input cases')
