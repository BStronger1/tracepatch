from solution import resolve_port
assert resolve_port(0, {'PORT': '9000'}, {}) == 0
assert resolve_port(None, {}, {}) == 8000
print('visible tests passed')
