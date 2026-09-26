"""No-API sensitivity checks for Click 2040's independent verifier."""
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
    task = ROOT / 'tasks/repos/click-2040'
    config = json.loads((task / 'task.json').read_text())
    preflight = json.loads((args.preflight / 'preflight.json').read_text())
    assert preflight['valid']
    reference = args.preflight / 'reference'
    relative = Path('src/click/shell_completion.py')
    original = (reference / relative).read_text(encoding='utf-8')
    cases = [
        ('punctuation_heuristic', 'return c in ctx._opt_prefixes', 'return not c.isalnum() and c != "/"', 'test_symbol_value_reproduction'),
        ('hardcoded_prefixes', 'return c in ctx._opt_prefixes', 'return c in "-+/"', 'test_symbol_value_reproduction'),
        ('count_consumes_value', 'if param.is_flag or param.count:', 'if param.is_flag:', 'test_count_option_does_not_request_a_value'),
        ('single_value_window', 'if index + 1 > param.nargs:', 'if index + 1 > 1:', 'test_multivalue_symbol_argument_scanning')]
    records = []
    for name, anchor, replacement, expected in cases:
        assert original.count(anchor) == 1
        candidate = args.run_dir / name
        shutil.copytree(reference, candidate)
        source = original.replace(anchor, replacement)
        (candidate / relative).write_text(source, encoding='utf-8')
        result = runner.verify(config['image'], candidate.resolve(), task, import_directory='src')
        assert result['returncode'] == 1 and 'FAIL: ' + expected in result['output'], (name, result)
        records.append({'mutation': name, 'expected_failure': expected,
                        'source_sha256': hashlib.sha256(source.encode()).hexdigest(), 'verification': result})
    report = {'scope': 'Verifier sensitivity, not model performance', 'assertions_passed': True,
              'model_api_calls': 0, 'task': config, 'preflight': preflight, 'mutations': records}
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps({'assertions_passed': True, 'mutations_detected': len(records), 'model_api_calls': 0}))


if __name__ == '__main__':
    main()
