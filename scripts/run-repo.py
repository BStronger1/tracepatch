"""Pinned upstream tasks, full source checkouts, independent offline verifiers."""
import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from tracepatch.budget import BudgetLedger
from tracepatch.lifecycle import completion_status
from tracepatch.repositories import repository_layout, reconstruct_candidate
from tracepatch.progress import ProgressMonitor, ObservedEnvironment, docker_snapshot, snapshot_digest
from tracepatch.memory import EvidenceMemory, docker_read_ranges
from tracepatch.checks import PublicChecks
from tracepatch.testing import PythonCheckEnvironment, docker_python_check, python_tool_prompt

spec = importlib.util.spec_from_file_location('runtime', ROOT / 'scripts/run-smoke.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
docker = runtime.docker
SYSTEM = ('Fix the repository issue in /workspace. Use cd /workspace or absolute paths. '
          'Return exactly one complete fenced bash action per reply. No network is available. '
          'Inspect relevant code, make a focused fix and test it. Only existing Python files '
          'under requests/ are exported. You have at most 12 model calls, including rejected replies. '
          'When ready, issue echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT.')


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def archive_source(commit, target, repository='https://github.com/psf/requests'):
    upstream = ROOT.parent / 'vendor' / repository_layout(repository).vendor
    archive = target.with_suffix('.tar')
    subprocess.run(['git', '-c', f'safe.directory={upstream.as_posix()}', '-C', str(upstream),
                    'archive', '--format=tar', '-o', str(archive), commit], check=True)
    target.mkdir()
    with tarfile.open(archive) as handle:
        handle.extractall(target, filter='data')
    return hashlib.sha256(archive.read_bytes()).hexdigest()


def environment(image, import_directory='.'):
    return runtime.WindowsDockerEnvironment(image=image, executable=runtime.DOCKER,
        cwd='/workspace', timeout=25, container_timeout='600',
        env={'PYTHONPATH': '/workspace/' + import_directory} if import_directory != '.' else {},
        run_args=['--rm', '--network', 'none', '--memory', '512m', '--cpus', '1',
                  '--pids-limit', '64', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges'])


def verify(image, source, task, verifier='verify.py', *, import_directory='.'):
    env = environment(image)
    try:
        docker('cp', str(source) + '/.', env.container_id + ':/workspace')
        docker('cp', str(task / verifier), env.container_id + ':/workspace/verify.py')
        if import_directory not in ('.', 'src'):
            raise ValueError('Unsupported import directory')
        import_path = '/workspace' if import_directory == '.' else '/workspace/src'
        return env.execute({'command': f'python -I -c "import sys;sys.path.insert(0,\'{import_path}\');import runpy;runpy.run_path(\'/workspace/verify.py\',run_name=\'__main__\')"'})
    finally:
        env.cleanup()


def public_check(image, source, check_file, *, import_directory='.'):
    """No agent shell, marker parser, or agent-written test enters this check."""
    if import_directory not in ('.', 'src'):
        raise ValueError('Unsupported import directory')
    env = environment(image)
    try:
        docker('cp', str(source) + '/.', env.container_id + ':/workspace')
        docker('cp', str(check_file), env.container_id + ':/workspace/public_check.py')
        import_path = '/workspace' if import_directory == '.' else '/workspace/src'
        program = (f'import sys;sys.path.insert(0,{import_path!r});import runpy;'
                   "runpy.run_path('/workspace/public_check.py',run_name='__main__')")
        result = subprocess.run([runtime.DOCKER, 'exec', env.container_id, 'python', '-I', '-c', program],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=25)
        return {'returncode': result.returncode, 'output': result.stdout + result.stderr}
    finally:
        env.cleanup()


def make_public_checks(base, layout, paths, image, check_file, container_id, output_dir):
    output_dir.mkdir(exist_ok=False)
    frozen = output_dir / 'reproduce_issue.py'
    shutil.copyfile(check_file, frozen)
    check_hash = hashlib.sha256(frozen.read_bytes()).hexdigest()

    def run_check(snapshot, index):
        started = time.monotonic()
        folder = output_dir / f'version-{index:03d}'
        folder.mkdir()
        exported = folder / 'export'
        destination = exported / layout.source
        destination.parent.mkdir(parents=True)
        docker('cp', container_id + ':/workspace/' + layout.source, str(destination))
        candidate = folder / 'candidate'
        reconstruct_candidate(base, exported, candidate, layout)
        actual = {name: hashlib.sha256((candidate / name).read_bytes()).hexdigest() for name in paths}
        if actual != snapshot:
            raise ValueError('Source changed during check capture')
        if hashlib.sha256(frozen.read_bytes()).hexdigest() != check_hash:
            raise ValueError('Public check changed')
        result = public_check(image, candidate, frozen, import_directory=layout.imports)
        result.update(source_sha256=snapshot_digest(actual), check_sha256=check_hash,
                      elapsed_seconds=round(time.monotonic() - started, 3))
        save(folder / 'result.json', result)
        return result

    return PublicChecks(paths, check_hash, run_check, output_dir / 'checks.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', required=True)
    parser.add_argument('--task', choices=sorted(p.parent.name for p in (ROOT / 'tasks/repos').glob('*/task.json')),
                        default='requests-2317')
    parser.add_argument('--policy', choices=('recovery', 'recovery-budget', 'recovery-submit'), default='recovery-budget')
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--context-policy', choices=('none', 'recent-turns'), default='none')
    parser.add_argument('--visible-reproducer', action='store_true')
    parser.add_argument('--max-calls', type=int, choices=(12, 24), default=12)
    parser.add_argument('--max-output-tokens', type=int, choices=(512, 1024), default=512)
    parser.add_argument('--action-protocol', choices=('text', 'native'), default='text')
    parser.add_argument('--progress-mode', choices=('off', 'observe', 'feedback'), default='off')
    parser.add_argument('--memory-mode', choices=('off', 'observe', 'recall'), default='off')
    parser.add_argument('--memory-profile', choices=('excerpts', 'structured'), default='excerpts')
    parser.add_argument('--check-mode', choices=('off', 'observe', 'feedback'), default='off')
    parser.add_argument('--test-tool', choices=('off', 'python'), default='off')
    args = parser.parse_args()
    if args.memory_mode != 'off' and args.progress_mode == 'off':
        parser.error('Evidence memory requires source observation')
    if args.check_mode != 'off' and (args.progress_mode == 'off' or not args.visible_reproducer):
        parser.error('Public checks require source observation and a visible reproducer')
    if args.test_tool == 'python' and (args.action_protocol != 'native' or args.progress_mode == 'off'):
        parser.error('Python checks require native tools and source observation')
    system = SYSTEM.replace('12 model calls', f'{args.max_calls} model calls')
    if args.action_protocol == 'native':
        system = system.replace('Return exactly one complete fenced bash action per reply.',
                                'Call the bash function exactly once per reply with a complete command argument. Do not write XML or fenced actions.')
    if args.test_tool == 'python':
        system = python_tool_prompt(system)
    if not re.fullmatch(r'repo-[a-z0-9-]{1,45}', args.batch):
        parser.error('Use a new repo-... batch ID')
    task = ROOT / 'tasks/repos' / args.task
    task_config = json.loads((task / 'task.json').read_text())
    layout = repository_layout(task_config['repository'])
    system = system.replace('under requests/', f'under {layout.source}/')
    config = json.loads((ROOT / 'configs/model.json').read_text())
    ledger = BudgetLedger(ROOT / 'artifacts/budget-ledger.json', str(config['first_run_budget_cny']))
    commit = subprocess.check_output(['git', '-c', f'safe.directory={runtime.UPSTREAM.as_posix()}',
        '-C', str(runtime.UPSTREAM), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != '04d809ceab9df28f9adaed044884180159172930':
        raise ValueError('Agent upstream changed')
    image = task_config['image']
    docker('image', 'inspect', image)
    batch = ROOT / 'runs' / args.batch
    batch.mkdir(parents=True, exist_ok=False)
    for name, path in {'runner': Path(__file__), 'runtime': ROOT / 'scripts/run-smoke.py',
                       **{n: ROOT / f'src/tracepatch/{n}.py' for n in ('budget', 'actions', 'recovery', 'lifecycle', 'window', 'toolcalling', 'repositories', 'progress', 'memory', 'context', 'symbols', 'checks', 'testing')}}.items():
        shutil.copyfile(path, batch / f'{name}.snapshot.py')
    base, reference = batch / 'base', batch / 'reference'
    hashes = {'base_archive': archive_source(task_config['base_commit'], base, task_config['repository']),
              'reference_archive': archive_source(task_config['reference_commit'], reference, task_config['repository']),
              'verifier': hashlib.sha256((task / 'verify.py').read_bytes()).hexdigest(),
              'task': hashlib.sha256((task / 'task.json').read_bytes()).hexdigest()}
    if args.visible_reproducer:
        hashes['visible_reproducer'] = hashlib.sha256((task / 'reproduce_issue.py').read_bytes()).hexdigest()
    manifest = {'split': 'development', 'suite': 'real-repo-custom', 'benchmark_result': False,
                'upstream_commit': commit, 'image': image, 'system_prompt': system,
                'policy': args.policy, 'model': config['model'], 'max_calls_per_task': args.max_calls,
                'context_policy': args.context_policy,
                'action_protocol': args.action_protocol,
                'source_layout': {'vendor': layout.vendor, 'source': layout.source, 'imports': layout.imports},
                'progress_mode': args.progress_mode,
                'progress_threshold': 6, 'progress_schema': 'tracepatch-progress-0.1',
                'memory_mode': args.memory_mode, 'memory_schema': 'tracepatch-memory-0.1',
                'memory_byte_limit': 4200,
                'memory_profile': args.memory_profile,
                'check_mode': args.check_mode, 'check_schema': 'tracepatch-public-checks-0.1',
                'check_schedule': 'initial-and-each-new-observed-source-version',
                'test_tool': args.test_tool, 'test_tool_schema': 'tracepatch-python-check-0.1',
                'test_tool_timeout': 20,
                'max_output_tokens': args.max_output_tokens, 'enable_thinking': False, 'observation_char_limit': 6000,
                'input_json_byte_limit': 24000, 'reject_provider_truncation': True,
                'tasks': {task_config['id']: hashes}, 'provenance': task_config}
    save(batch / 'manifest.json', manifest)
    save(batch / 'config.json', config)
    before, oracle = verify(image, base, task, import_directory=layout.imports), verify(image, reference, task, import_directory=layout.imports)
    expected_failure = task_config.get('expected_failure', 'test_bytes_get_issue_reproduction')
    test_count = task_config.get('verifier_test_count', 5)
    valid = (before['returncode'] == 1 and f'FAIL: {expected_failure} ' in before['output']
             and oracle['returncode'] == 0 and f'Ran {test_count} tests' in oracle['output'])
    checks = {'broken': before, 'reference': oracle, 'valid': valid}
    if args.visible_reproducer:
        repro_before = verify(image, base, task, 'reproduce_issue.py', import_directory=layout.imports)
        repro_after = verify(image, reference, task, 'reproduce_issue.py', import_directory=layout.imports)
        valid = valid and repro_before['returncode'] == 1 and 'AssertionError' in repro_before['output'] and repro_after['returncode'] == 0
        checks.update(visible_broken=repro_before, visible_reference=repro_after, valid=valid)
    save(batch / 'preflight.json', checks)
    print('Preflight:', valid, flush=True)
    if not valid:
        raise RuntimeError('Invalid reproduction; no model call allowed')
    if args.verify_only:
        return
    local = dict(line.split('=', 1) for line in (ROOT / '.env').read_text().splitlines()
                 if '=' in line and not line.startswith('#'))
    key = local.get('OPENAI_API_KEY', '')
    if not re.fullmatch(r'sk-[A-Za-z0-9_-]{16,}', key):
        raise ValueError('No valid key')
    run = batch / (args.batch + '--' + task_config['id'])
    run.mkdir()
    model = runtime.DmxModel(config, key, run_dir=run, ledger=ledger, policy=args.policy,
                             max_calls=args.max_calls, context_policy=args.context_policy, action_protocol=args.action_protocol,
                             max_output_tokens=args.max_output_tokens)
    model.test_tool = args.test_tool
    env = environment(image, layout.imports)
    result = {'task': task_config['id'], 'status': 'started', 'verified_success': False}
    started = time.monotonic()
    save(run / 'result.json', result)
    try:
        # Source archive has no .git, gold patch, future commit, or custom verifier.
        docker('cp', str(base) + '/.', env.container_id + ':/workspace')
        instruction = task_config['instruction']
        if args.visible_reproducer:
            docker('cp', str(task / 'reproduce_issue.py'), env.container_id + ':/workspace/reproduce_issue.py')
            instruction += ' A public-issue offline reproducer is provided: run python reproduce_issue.py before and after your fix. Do not modify it.'
        if args.progress_mode != 'off':
            paths = [p.relative_to(base).as_posix() for p in sorted((base / layout.source).rglob('*.py'))]
            container_id = env.container_id
            snapshot = lambda: docker_snapshot(runtime.DOCKER, container_id, paths)
            initial = snapshot()
            expected = {name: hashlib.sha256((base / name).read_bytes()).hexdigest() for name in paths}
            if initial != expected:
                raise ValueError('Initial source observation does not match the frozen base')
            monitor = ProgressMonitor(initial)
            memory = None
            if args.memory_mode != 'off':
                reader = lambda ranges: docker_read_ranges(runtime.DOCKER, container_id, ranges)
                memory = EvidenceMemory(paths, run / 'memory.json', reader, instruction=task_config['instruction'])
                model.evidence_memory = memory
                model.memory_mode = args.memory_mode
                model.memory_profile = args.memory_profile
            public_checks = None
            if args.check_mode != 'off':
                public_checks = make_public_checks(base, layout, paths, image,
                    task / 'reproduce_issue.py', container_id, run / 'public-checks')
                public_checks.observe(initial, 0)
                model.public_checks = public_checks
                model.check_feedback = args.check_mode == 'feedback'
            if args.test_tool == 'python':
                execute_check = lambda code: docker_python_check(runtime.DOCKER, container_id, code, layout.imports)
                env = PythonCheckEnvironment(env, execute_check, snapshot, run / 'python-checks')
            env = ObservedEnvironment(env, monitor, snapshot, run / 'progress.json', memory=memory,
                                      checks=public_checks)
            model.progress_monitor = monitor
            model.progress_feedback = args.progress_mode == 'feedback'
        agent = runtime.DefaultAgent(model, env, step_limit=args.max_calls, cost_limit=args.max_calls * 0.1,
            wall_time_limit_seconds=300, output_path=run / 'trajectory.json',
            system_template=system, instance_template='{{task}}')
        result['agent_exit'] = agent.run(instruction).get('exit_status')
    except Exception as error:
        result.update(status='execution_error', error_type=type(error).__name__)
    finally:
        try:
            export_path = run / layout.source
            export_path.parent.mkdir(parents=True, exist_ok=True)
            docker('cp', env.container_id + ':/workspace/' + layout.source, str(export_path))
        except Exception as error:
            result['export_error'] = type(error).__name__
        if not result.get('agent_exit') and (run / 'trajectory.json').exists():
            result['agent_exit'] = json.loads((run / 'trajectory.json').read_text())['info'].get('exit_status')
        env.cleanup()
    try:
        if (run / layout.source).is_dir():
            candidate = run / 'candidate'
            patch = reconstruct_candidate(base, run, candidate, layout)
            (run / 'patch.diff').write_text(patch, encoding='utf-8')
            result['verification'] = verify(image, candidate, task, import_directory=layout.imports)
            result.update(status='verified', verified_success=result['verification']['returncode'] == 0)
    except Exception as error:
        result.update(status='verification_error', error_type=type(error).__name__)
    result.update(completion=completion_status(result.get('agent_exit'), result.get('verification')),
        api_calls=len(model.calls), format_error_count=sum(c.get('action_diagnosis') not in (None, 'valid') for c in model.calls),
        estimated_known_no_cache_cny=sum(c.get('estimated_no_cache_cny', 0) for c in model.calls),
        unknown_cost_requests=sum('estimated_no_cache_cny' not in c for c in model.calls),
        elapsed_seconds=round(time.monotonic() - started, 3), budget=ledger.summary())
    save(run / 'result.json', result)
    save(batch / 'summary.json', {'tasks': [result], 'planned_tasks': [task_config['id']], 'budget': ledger.summary()})
    print(json.dumps({k: result[k] for k in ('status', 'completion', 'api_calls', 'budget')}), flush=True)


if __name__ == '__main__':
    main()
