"""Offline outcome categories from recorded metadata, never causal diagnoses."""
import hashlib
import json
from pathlib import Path


def classify(result, progress=None, public=None, checks=None):
    verification = result.get('verification') or {}
    code = verification.get('returncode')
    known = (result.get('status') == 'verified' and not result.get('error_type')
             and type(code) is int and code in (0, 1))
    passed = code == 0 if known else None
    submitted = result.get('agent_exit') == 'Submitted'
    if known and result.get('verified_success') is not passed:
        raise ValueError('Conflicting acceptance metadata')
    completion = result.get('completion')
    if completion and known and (completion.get('patch_verified') is not passed or
                                 completion.get('agent_submitted') is not submitted):
        raise ValueError('Conflicting completion metadata')
    events = None if progress is None else progress.get('events')
    if events is not None:
        if not isinstance(events, list) or any(e.get('state') not in ('changed', 'unchanged', 'unknown') for e in events):
            raise ValueError('Invalid progress events')
    changed = None if events is None else sum(e['state'] == 'changed' for e in events)
    unknown = None if events is None else sum(e['state'] == 'unknown' for e in events)
    final_digest = None
    if events is not None:
        final_digest = (events[-1].get('snapshot_sha256') if events else progress.get('initial_sha256'))
        if events and events[-1]['state'] == 'unknown':
            final_digest = None
    net_changed = (final_digest != progress.get('initial_sha256')) if final_digest else None
    if not known:
        category = 'acceptance_unknown'
    elif passed:
        category = 'verified_submitted' if submitted else 'verified_without_submission'
    elif submitted:
        category = 'submitted_but_acceptance_failed'
    elif changed is not None and changed > 0:
        category = 'acceptance_failed_after_observed_edits'
    elif changed == 0 and unknown == 0:
        category = 'acceptance_failed_without_observed_edits'
    else:
        category = 'acceptance_failed_edits_unknown'

    # Match final recorded source, never use a stale success or parse stdout as evidence.
    public_record = (public or {}).get('current') or {}
    public_status = 'unknown'
    if (final_digest and public_record.get('source_sha256') == final_digest and
            public_record.get('provenance') == 'frozen-public-reproducer' and
            public_record.get('status') in ('passed', 'failed') and not public_record.get('error_type')):
        public_status = public_record['status']
    matching = [r for r in checks or [] if final_digest and
                r.get('provenance') == 'agent-authored-python' and r.get('source_state') == 'unchanged' and
                r.get('source_before_sha256') == r.get('source_after_sha256') == final_digest]
    latest_status = matching[-1]['status'] if matching else None
    return {'category': category, 'acceptance_passed': passed, 'agent_submitted': submitted,
            'observed_changed_actions': changed, 'unknown_observation_actions': unknown,
            'final_net_source_change': net_changed, 'final_source_sha256': final_digest,
            'current_public_status': public_status, 'current_python_status': latest_status,
            'python_check_count': None if checks is None else len(checks),
            'source_changing_python_checks': None if checks is None else sum(r.get('source_state') == 'changed' for r in checks),
            'public_pass_but_acceptance_failed': public_status == 'passed' and passed is False,
            'python_pass_but_acceptance_failed': latest_status == 'process_passed' and passed is False}


def audit_run(run_dir):
    """Read only selected JSON metadata; do not emit command/code/output bodies."""
    run_dir = Path(run_dir)
    hashes = {}

    def read(name, required=False):
        path = run_dir / name
        if not path.exists() and not required:
            return None
        raw = path.read_bytes()
        hashes[name] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)

    result = read('result.json', required=True)
    progress = read('progress.json')
    public = read('public-checks/checks.json')
    check_dir = run_dir / 'python-checks'
    checks = None if not check_dir.is_dir() else [read(p.relative_to(run_dir).as_posix()) for p in sorted(check_dir.glob('[0-9][0-9][0-9].json'))]
    return {'run': run_dir.name, 'task': result.get('task'),
            'observations': classify(result, progress, public, checks), 'source_file_hashes': hashes}
