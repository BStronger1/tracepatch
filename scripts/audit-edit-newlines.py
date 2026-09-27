"""Read-only newline diagnosis for rejected edits in an unchanged source run."""
import argparse
import hashlib
import json
from pathlib import Path


def audit(run):
    progress = json.loads((run / 'progress.json').read_text(encoding='utf-8'))
    if any(e['state'] != 'unchanged' for e in progress['events']):
        raise ValueError('This audit requires an unchanged-source run')
    records = []
    for entry in sorted((run / 'edits').glob('*.input.json')):
        edit = json.loads(entry.read_text(encoding='utf-8'))
        source = (run / 'candidate' / edit['path']).resolve()
        if (run / 'candidate').resolve() not in source.parents:
            raise ValueError('Source outside candidate')
        raw = source.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == progress['initial'][edit['path']]
        result = json.loads(entry.with_name(entry.name.replace('.input.json', '.json')).read_text(encoding='utf-8'))
        assert result['status'] == 'old_text_not_found'
        assert result['file_before_sha256'] == result['file_after_sha256'] == digest
        assert result['edit_sha256'] == hashlib.sha256(json.dumps(edit, sort_keys=True).encode()).hexdigest()
        text = raw.decode('utf-8')
        old = edit['old']
        records.append({'input_file': entry.name, 'input_file_sha256': hashlib.sha256(entry.read_bytes()).hexdigest(),
            'source_file_sha256': digest, 'recorded_status': result['status'],
            'source_crlf_count': raw.count(b'\r\n'), 'source_lf_count': raw.count(b'\n'),
            'argument_crlf_count': old.count('\r\n'), 'argument_lf_count': old.count('\n'),
            'exact_matches': text.count(old),
            'matches_after_only_eol_normalization': text.replace('\r\n', '\n').count(old.replace('\r\n', '\n'))})
    return {'scope': 'Post-run byte comparison only; no commands or edits executed, frozen scores unchanged',
            'run': run.name, 'records': records}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.run)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps(report))
