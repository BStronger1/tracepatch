import csv
import io

def parse_record(line):
    try:
        rows = list(csv.reader(io.StringIO(line), strict=True))
    except csv.Error as exc:
        raise ValueError('malformed CSV') from exc
    if len(rows) != 1 or len(rows[0]) != 3:
        raise ValueError('expected three fields')
    return tuple(rows[0])
