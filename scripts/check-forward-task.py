"""No-API verifier sensitivity checks for the historical Click forwarding task."""
import argparse
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runner', ROOT / 'scripts/run-repo.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Do not overwrite evidence')
    args.run_dir.mkdir(parents=True, exist_ok=False)
    config = json.loads((ROOT / 'tasks/repos/click-1840/task.json').read_text())
    preflight = json.loads((args.preflight / 'preflight.json').read_text())
    assert preflight['valid']
    reference = args.preflight / 'reference'
    original = (reference / 'src/click/core.py').read_text(encoding='utf-8')
    anchor = '            ctx.params.update(kwargs)'
    assert original.count(anchor) == 1
    cases = [
        ('parent_state_leak', anchor + '\n            self.params.update(kwargs)', 'test_parent_params_are_not_changed_or_aliased'),
        ('filter_undeclared', '            ctx.params.update({p.name: kwargs[p.name] for p in other_cmd.params if p.name in kwargs})', 'test_multilevel_forward_issue_reproduction'),
        ('overwrite_explicit', None, 'test_explicit_overrides_include_false_and_none')]
    reports = []
    for name, replacement, expected in cases:
        candidate = args.run_dir / name
        shutil.copytree(reference, candidate)
        source = original.replace(anchor, replacement) if replacement is not None else original.replace(
            '            if param not in kwargs:\n                kwargs[param] = self.params[param]',
            '            if True:\n                kwargs[param] = self.params[param]')
        assert source != original
        (candidate / 'src/click/core.py').write_text(source, encoding='utf-8')
        result = runner.verify(config['image'], candidate.resolve(), ROOT / 'tasks/repos/click-1840', import_directory='src')
        assert result['returncode'] == 1 and 'FAIL: ' + expected in result['output'], (name, result)
        reports.append({'mutation': name, 'expected_failure': expected,
                        'core_sha256': hashlib.sha256(source.encode()).hexdigest(), 'verification': result})
    report = {'scope': 'Preflight and three injected regressions; no model repair evidence',
        'assertions_passed': True, 'model_api_calls': 0, 'task': config, 'preflight': preflight, 'mutations': reports}
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps({'assertions_passed': True, 'mutations_detected': len(reports), 'model_api_calls': 0}))


if __name__ == '__main__':
    main()
