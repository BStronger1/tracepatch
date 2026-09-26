"""No-API Docker integration check for frozen public-test provenance."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runner', ROOT / 'scripts/run-repo.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
from tracepatch.progress import docker_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.run_dir = args.run_dir.resolve()
    if args.output.exists():
        raise ValueError('Do not overwrite evidence')
    args.run_dir.mkdir(parents=True, exist_ok=False)
    task = ROOT / 'tasks/repos/requests-2527-v2'
    config = json.loads((task / 'task.json').read_text())
    layout = runner.repository_layout(config['repository'])
    base, reference = args.run_dir / 'base', args.run_dir / 'reference'
    runner.archive_source(config['base_commit'], base, config['repository'])
    runner.archive_source(config['reference_commit'], reference, config['repository'])
    paths = [p.relative_to(base).as_posix() for p in sorted((base / layout.source).rglob('*.py'))]
    env = runner.environment(config['image'])
    try:
        runner.docker('cp', str(base) + '/.', env.container_id + ':/workspace')
        checks = runner.make_public_checks(base, layout, paths, config['image'],
            task / 'reproduce_issue.py', env.container_id, args.run_dir / 'public-checks')
        state = docker_snapshot(runner.runtime.DOCKER, env.container_id, paths)
        checks.observe(state, 0)
        assert checks.current['status'] == 'failed'
        # Agent-local tests, added files and a forged public repro are never exported.
        masked = env.execute({'command': "printf 'print(\"fake success\")' > reproduce_issue.py; python -c 'raise AssertionError()'; echo SUCCESS"})
        assert masked['returncode'] == 0
        checks.observe(state, 1)
        assert checks.current['status'] == 'failed' and len(checks.records) == 1
        runner.docker('cp', str(reference / layout.source) + '/.', env.container_id + ':/workspace/' + layout.source)
        fixed = docker_snapshot(runner.runtime.DOCKER, env.container_id, paths)
        checks.observe(fixed, 2)
        assert checks.current['status'] == 'passed'
        # Freeze-check mismatch prevents a new version from being certified.
        frozen = args.run_dir / 'public-checks/reproduce_issue.py'
        frozen.write_text('print("tampered")')
        env.execute({'command': "printf '\\n# new version\\n' >> requests/cookies.py"})
        checks.observe(docker_snapshot(runner.runtime.DOCKER, env.container_id, paths), 3)
        assert checks.current['status'] == 'unknown'
        report = {'scope': 'No-API Docker integration; not model repair evidence',
                  'assertions_passed': True, 'model_api_calls': 0, 'image': config['image'],
                  'masked_shell_returncode': masked['returncode'], 'forged_agent_reproducer_ignored': True,
                  'frozen_check_tampering_rejected': True, 'records': checks.records}
        with args.output.open('x', encoding='utf-8') as handle:
            json.dump(report, handle, indent=2)
        print(json.dumps(report))
    finally:
        env.cleanup()


if __name__ == '__main__':
    main()
