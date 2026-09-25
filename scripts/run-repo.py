"""One pinned upstream issue, full source checkout, custom independent offline verifier."""
import argparse
import difflib
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


def archive_source(commit, target):
    upstream = ROOT.parent / 'vendor/requests'
    archive = target.with_suffix('.tar')
    subprocess.run(['git', '-c', f'safe.directory={upstream.as_posix()}', '-C', str(upstream),
                    'archive', '--format=tar', '-o', str(archive), commit], check=True)
    target.mkdir()
    with tarfile.open(archive) as handle:
        handle.extractall(target, filter='data')
    return hashlib.sha256(archive.read_bytes()).hexdigest()


def environment(image):
    return runtime.WindowsDockerEnvironment(image=image, executable=runtime.DOCKER,
        cwd='/workspace', timeout=25, container_timeout='600',
        run_args=['--rm', '--network', 'none', '--memory', '512m', '--cpus', '1',
                  '--pids-limit', '64', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges'])


def verify(image, source, task, verifier='verify.py'):
    env = environment(image)
    try:
        docker('cp', str(source) + '/.', env.container_id + ':/workspace')
        docker('cp', str(task / verifier), env.container_id + ':/workspace/verify.py')
        return env.execute({'command': 'python -I -c "import sys;sys.path.insert(0,\'/workspace\');import runpy;runpy.run_path(\'/workspace/verify.py\',run_name=\'__main__\')"'})
    finally:
        env.cleanup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', required=True)
    parser.add_argument('--policy', choices=('recovery', 'recovery-budget'), default='recovery-budget')
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--context-policy', choices=('none', 'recent-turns'), default='none')
    parser.add_argument('--visible-reproducer', action='store_true')
    parser.add_argument('--max-calls', type=int, choices=(12, 24), default=12)
    parser.add_argument('--action-protocol', choices=('text', 'native'), default='text')
    args = parser.parse_args()
    system = SYSTEM.replace('12 model calls', f'{args.max_calls} model calls')
    if args.action_protocol == 'native':
        system = system.replace('Return exactly one complete fenced bash action per reply.',
                                'Call the bash function exactly once per reply with a complete command argument. Do not write XML or fenced actions.')
    if not re.fullmatch(r'repo-[a-z0-9-]{1,45}', args.batch):
        parser.error('Use a new repo-... batch ID')
    task = ROOT / 'tasks/repos/requests-2317'
    task_config = json.loads((task / 'task.json').read_text())
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
                       **{n: ROOT / f'src/tracepatch/{n}.py' for n in ('budget', 'actions', 'recovery', 'lifecycle', 'window', 'toolcalling')}}.items():
        shutil.copyfile(path, batch / f'{name}.snapshot.py')
    base, reference = batch / 'base', batch / 'reference'
    hashes = {'base_archive': archive_source(task_config['base_commit'], base),
              'reference_archive': archive_source(task_config['reference_commit'], reference),
              'verifier': hashlib.sha256((task / 'verify.py').read_bytes()).hexdigest(),
              'task': hashlib.sha256((task / 'task.json').read_bytes()).hexdigest()}
    if args.visible_reproducer:
        hashes['visible_reproducer'] = hashlib.sha256((task / 'reproduce_issue.py').read_bytes()).hexdigest()
    manifest = {'split': 'development', 'suite': 'real-repo-custom', 'benchmark_result': False,
                'upstream_commit': commit, 'image': image, 'system_prompt': system,
                'policy': args.policy, 'model': config['model'], 'max_calls_per_task': args.max_calls,
                'context_policy': args.context_policy,
                'action_protocol': args.action_protocol,
                'max_output_tokens': 512, 'enable_thinking': False, 'observation_char_limit': 6000,
                'input_json_byte_limit': 24000, 'reject_provider_truncation': True,
                'tasks': {task_config['id']: hashes}, 'provenance': task_config}
    save(batch / 'manifest.json', manifest)
    save(batch / 'config.json', config)
    before, oracle = verify(image, base, task), verify(image, reference, task)
    valid = (before['returncode'] == 1 and 'FAIL: test_bytes_get_issue_reproduction' in before['output']
             and oracle['returncode'] == 0 and 'Ran 5 tests' in oracle['output'])
    checks = {'broken': before, 'reference': oracle, 'valid': valid}
    if args.visible_reproducer:
        repro_before = verify(image, base, task, 'reproduce_issue.py')
        repro_after = verify(image, reference, task, 'reproduce_issue.py')
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
                             max_calls=args.max_calls, context_policy=args.context_policy, action_protocol=args.action_protocol)
    env = environment(image)
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
        agent = runtime.DefaultAgent(model, env, step_limit=args.max_calls, cost_limit=args.max_calls * 0.1,
            wall_time_limit_seconds=300, output_path=run / 'trajectory.json',
            system_template=system, instance_template='{{task}}')
        result['agent_exit'] = agent.run(instruction).get('exit_status')
    except Exception as error:
        result.update(status='execution_error', error_type=type(error).__name__)
    finally:
        try:
            docker('cp', env.container_id + ':/workspace/requests', str(run / 'requests'))
        except Exception as error:
            result['export_error'] = type(error).__name__
        if not result.get('agent_exit') and (run / 'trajectory.json').exists():
            result['agent_exit'] = json.loads((run / 'trajectory.json').read_text())['info'].get('exit_status')
        env.cleanup()
    try:
        if (run / 'requests').is_dir():
            candidate = run / 'candidate'
            shutil.copytree(base, candidate)
            patches = []
            for original in sorted((base / 'requests').rglob('*.py')):
                rel = original.relative_to(base)
                exported = run / rel
                if any(p.is_symlink() for p in [exported, *exported.parents] if p != run.parent):
                    raise ValueError('Symlink export rejected')
                if not exported.is_file():
                    raise ValueError('Missing allowed source file')
                shutil.copyfile(exported, candidate / rel)
                patches.extend(difflib.unified_diff(original.read_text(encoding='utf-8').splitlines(True),
                    exported.read_text(encoding='utf-8').splitlines(True),
                    fromfile='a/' + rel.as_posix(), tofile='b/' + rel.as_posix()))
            (run / 'patch.diff').write_text(''.join(patches), encoding='utf-8')
            result['verification'] = verify(image, candidate, task)
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
