from solution import parse_record
assert parse_record('"Doe, Jane",Paris,"said ""hello"""') == ('Doe, Jane', 'Paris', 'said "hello"')
assert parse_record('a,b,c') == ('a', 'b', 'c')
assert parse_record(',,') == ('', '', '')
assert parse_record('"x,y",z,') == ('x,y', 'z', '')
for invalid in ('a,b', 'a,b,c,d', '"unclosed,b,c', ''):
    try:
        parse_record(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid CSV accepted')
print('PASS: quoted commas, escaping, empty fields and malformed inputs')
