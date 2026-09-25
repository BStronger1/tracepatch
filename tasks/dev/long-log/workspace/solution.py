def parse_record(line):
    parts = line.split(',')
    if len(parts) != 3:
        raise ValueError('expected three fields')
    return tuple(parts)
