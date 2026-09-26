"""Group local run outcomes without executing trace commands or calling an API."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from tracepatch.triage import audit_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, action='append', required=True, help='A task run directory; repeat to audit multiple runs')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    resolved = [p.resolve() for p in args.run]
    if len(set(resolved)) != len(resolved):
        parser.error('Duplicate run directories would double-count outcomes')
    records = [audit_run(p) for p in resolved]
    report = {'schema_version': 'tracepatch-triage-0.1',
              'scope': 'Descriptive metadata audit. Categories are not causes or independent verification of the logs.',
              'categories': dict(Counter(r['observations']['category'] for r in records)),
              'runs': records,
              'limitations': ['No trace commands are executed.', 'Missing evidence stays unknown.',
                              'Passing checks do not prove sufficient coverage.', 'No claims about model reasoning, memory loss or general success rates.']}
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps({'runs': len(records), 'categories': report['categories']}))


if __name__ == '__main__':
    main()
