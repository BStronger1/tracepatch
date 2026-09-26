"""Version-bound public checks; never infer test success from agent shell output."""
import hashlib
import json

from tracepatch.progress import snapshot_digest, validate_snapshot


class PublicChecks:
    def __init__(self, paths, check_sha256, run_check, output):
        validate_snapshot(dict.fromkeys(paths), paths)
        validate_snapshot({'check.py': check_sha256}, ['check.py'])
        if check_sha256 is None:
            raise ValueError('A frozen check digest is required')
        self.paths = list(paths)
        self.check_sha256 = check_sha256
        self.run_check = run_check
        self.output = output
        self.records = []
        self.cache = {}
        self.current = None

    def observe(self, snapshot, action):
        self.current = None
        if snapshot is None:
            self.save()
            return
        snapshot = validate_snapshot(snapshot, self.paths)
        digest = snapshot_digest(snapshot)
        if digest not in self.cache:
            record = {'action': action, 'source_sha256': digest,
                      'check_sha256': self.check_sha256, 'provenance': 'frozen-public-reproducer',
                      'status': 'unknown', 'returncode': None, 'error_type': None}
            try:
                result = self.run_check(snapshot, len(self.records) + 1)
                if result['source_sha256'] != digest or result['check_sha256'] != self.check_sha256:
                    raise ValueError('Check provenance mismatch')
                code = result['returncode']
                if type(code) is not int or code < 0:
                    raise ValueError('No valid process exit status')
                record.update(returncode=code, status='passed' if code == 0 else 'failed',
                              output_sha256=hashlib.sha256(result['output'].encode()).hexdigest())
            except Exception as error:
                record['error_type'] = type(error).__name__
            self.records.append(record)
            self.cache[digest] = record
        self.current = self.cache[digest]
        self.save()

    def save(self):
        self.output.write_text(json.dumps({'schema_version': 'tracepatch-public-checks-0.1',
            'records': self.records, 'current': self.current}, indent=2), encoding='utf-8')

    def notice(self):
        record = self.current
        facts = {'status': 'unknown'} if record is None else {
            k: record[k] for k in ('status', 'returncode', 'source_sha256', 'check_sha256')}
        return ('Harness public-check evidence: ' + json.dumps(facts, sort_keys=True) +
                '. Provenance: frozen public issue reproducer, run as a direct process in a fresh '
                'offline container on the exported source version. This is a narrow public check, '
                'NOT independent final acceptance. Agent-written tests and shell exit codes have '
                'different provenance. If your test disagrees, review its expected values against '
                'the task and source; do not dismiss a failure merely because this check passed. '
                'After focused checks and requirement review, submit in a separate action containing '
                'only: echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT. No check submits for you.')
