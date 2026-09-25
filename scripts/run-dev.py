"""Sequential development-only tasks; source files alone enter fresh verification containers."""
import argparse
import difflib
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from tracepatch.budget import BudgetLedger
from tracepatch.analyze import analyze
from tracepatch.lifecycle import completion_status

spec = importlib.util.spec_from_file_location('smoke_runtime', ROOT / 'scripts/run-smoke.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
docker = runtime.docker
TASK_IDS = ('config-precedence', 'long-log', 'retry-contract')
IMAGE = 'python@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9'
COMMIT = '04d809ceab9df28f9adaed044884180159172930'
SYSTEM = ('You fix Python code in /workspace. Inspect files, edit solution.py, and run visible tests. '
          'Return exactly ONE action, formatted as a bash code block: ```bash\\ncommand\\n```. '
          'Each command runs in a new shell. No network is available. Do not edit tests. '
          'When done, issue only: echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT')


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def source_files(task):
    files = json.loads((task / 'task.json').read_text()).get('source_files', ['solution.py'])
    if not files or len(set(files)) != len(files) or any(not re.fullmatch(r'[a-z_]+\.py', f) for f in files):
        raise ValueError('Source allowlist must contain unique plain Python filenames')
    return files


def verify(task, source, replacement=None):
    env = runtime.WindowsDockerEnvironment(image=IMAGE, executable=runtime.DOCKER,
        cwd='/workspace', timeout=20, container_timeout='90',
        run_args=['--rm', '--network', 'none', '--memory', '256m', '--cpus', '1',
                  '--pids-limit', '64', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges'])
    try:
        for name in source_files(task):
            path = source / name if source.is_dir() else source
            if replacement and name == replacement:
                path = task / 'workspace' / name
            docker('cp', str(path), env.container_id + ':/workspace/' + name)
        docker('cp', str(task / 'verify.py'), env.container_id + ':/workspace/verify.py')
        result = env.execute({'command': 'python -I -c "import sys;sys.path.insert(0,\'/workspace\');import runpy;runpy.run_path(\'/workspace/verify.py\',run_name=\'__main__\')"'})
        return result
    finally:
        env.cleanup()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', required=True)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--policy', choices=('baseline', 'recovery', 'recovery-budget'), default='baseline')
    parser.add_argument('--suite', choices=('dev', 'multifile'), default='dev')
    args = parser.parse_args()
    task_ids = TASK_IDS if args.suite == 'dev' else ('job-queue',)
    max_calls = 8 if args.suite == 'dev' else 12
    system = SYSTEM if args.suite == 'dev' else (
        'You fix Python code in /workspace. Read SPEC.md, inspect the source files, edit only allowed source files, '
        'and run visible tests. You have at most 12 model turns, including inspection, edits and submission. '
        'Each reply must contain exactly one complete fenced bash action. Each command runs in a new shell; '
        'use cd /workspace or absolute paths. No network. Do not edit tests or SPEC.md. '
        'When done issue: echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT')
    if not re.fullmatch(r'dev-[a-z0-9-]{1,40}', args.batch):
        parser.error('Use a batch ID such as dev-baseline-001')
    config = json.loads((ROOT / 'configs/model.json').read_text())
    ledger = BudgetLedger(ROOT / 'artifacts/budget-ledger.json', str(config['first_run_budget_cny']))
    commit = subprocess.run(['git', '-c', f'safe.directory={runtime.UPSTREAM.as_posix()}',
        '-C', str(runtime.UPSTREAM), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    if commit != COMMIT:
        raise RuntimeError('Upstream version changed')
    docker('image', 'inspect', IMAGE)
    batch = ROOT / 'runs' / args.batch
    batch.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, batch / 'runner.snapshot.py')
    shutil.copyfile(ROOT / 'scripts/run-smoke.py', batch / 'runtime.snapshot.py')
    shutil.copyfile(ROOT / 'src/tracepatch/budget.py', batch / 'budget.snapshot.py')
    shutil.copyfile(ROOT / 'src/tracepatch/actions.py', batch / 'actions.snapshot.py')
    shutil.copyfile(ROOT / 'src/tracepatch/recovery.py', batch / 'recovery.snapshot.py')
    shutil.copyfile(ROOT / 'src/tracepatch/lifecycle.py', batch / 'lifecycle.snapshot.py')
    shutil.copyfile(ROOT / 'src/tracepatch/window.py', batch / 'window.snapshot.py')
    save(batch / 'config.json', config)
    manifest = {'split': 'development', 'benchmark_result': False, 'upstream_commit': commit,
                'image': IMAGE, 'system_prompt': system, 'policy': args.policy, 'suite': args.suite,
                'reject_provider_truncation': True,
                'model': config['model'], 'max_calls_per_task': max_calls, 'max_output_tokens': 512,
                'enable_thinking': False, 'observation_char_limit': 6000,
                'input_json_byte_limit': 24000, 'tasks': {}}
    for task_id in task_ids:
        task = ROOT / 'tasks' / args.suite / task_id
        manifest['tasks'][task_id] = {
            p.relative_to(task).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(task.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    save(batch / 'manifest.json', manifest)
    preflight = {}
    for task_id in task_ids:
        task = ROOT / 'tasks' / args.suite / task_id
        reference = task / ('oracle.py' if args.suite == 'dev' else 'oracle')
        broken = verify(task, task / 'workspace')
        oracle = verify(task, reference)
        expected_failure = 'ValueError: expected three fields' if task_id == 'long-log' else 'AssertionError'
        passed = broken['returncode'] == 1 and expected_failure in broken['output'] and oracle['returncode'] == 0
        preflight[task_id] = {'broken': broken, 'oracle': oracle, 'valid': passed}
        if args.suite == 'multifile':
            mutations = {name: verify(task, reference, replacement=name) for name in source_files(task)}
            passed = passed and all(r['returncode'] == 1 and 'FAIL:' in r['output'] for r in mutations.values())
            preflight[task_id].update(single_module_regressions=mutations, valid=passed)
        save(batch / 'preflight.json', preflight)
        print(f'Preflight {task_id}: {passed}', flush=True)
        if not passed:
            raise RuntimeError('Invalid task; no paid requests allowed')
    if args.verify_only:
        return
    local = dict(line.split('=', 1) for line in (ROOT / '.env').read_text().splitlines()
                 if '=' in line and not line.startswith('#'))
    key = local.get('OPENAI_API_KEY', '')
    if not re.fullmatch(r'sk-[A-Za-z0-9_-]{16,}', key):
        raise RuntimeError('No valid key')
    summaries = []
    for task_id in task_ids:
        task = ROOT / 'tasks' / args.suite / task_id
        task_config = json.loads((task / 'task.json').read_text())
        run = batch / f'{args.batch}--{task_id}'
        run.mkdir()
        model = runtime.DmxModel(config, key, run_dir=run, ledger=ledger, policy=args.policy, max_calls=max_calls)
        env = runtime.WindowsDockerEnvironment(image=IMAGE, executable=runtime.DOCKER,
            cwd='/workspace', timeout=20, container_timeout='600',
            run_args=['--rm', '--network', 'none', '--memory', '512m', '--cpus', '1',
                      '--pids-limit', '64', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges'])
        started = time.monotonic()
        result = {'task': task_id, 'status': 'started', 'verified_success': False}
        save(run / 'result.json', result)
        try:
            docker('cp', str(task / 'workspace') + '/.', env.container_id + ':/workspace')
            agent = runtime.DefaultAgent(model, env, step_limit=max_calls, cost_limit=max_calls * 0.1,
                wall_time_limit_seconds=300, output_path=run / 'trajectory.json',
                system_template=system, instance_template='{{task}}')
            exit_data = agent.run(task_config['instruction'])
            result['agent_exit'] = exit_data.get('exit_status')
            for name in source_files(task):
                docker('cp', env.container_id + ':/workspace/' + name, str(run / name))
            result['status'] = 'agent_finished'
        except Exception as error:
            result.update(status='execution_error', error_type=type(error).__name__)
        finally:
            env.cleanup()
        if all((run / name).is_file() and not (run / name).is_symlink() for name in source_files(task)):
            result['verification'] = verify(task, run)
            result['verified_success'] = result['verification']['returncode'] == 0
            result['status'] = 'verified'
            patch = ''.join(''.join(difflib.unified_diff((task / 'workspace' / name).read_text().splitlines(True),
                (run / name).read_text().splitlines(True), fromfile='a/' + name, tofile='b/' + name))
                for name in source_files(task))
            (run / 'patch.diff').write_text(patch, encoding='utf-8')
        if (run / 'trajectory.json').exists():
            trajectory = json.loads((run / 'trajectory.json').read_text())
            result['diagnostics'] = analyze(trajectory)
            result['format_error_count'] = sum(m.get('role') == 'assistant' and not m.get('extra', {}).get('actions')
                                                for m in trajectory['messages'])
        result['completion'] = completion_status(result.get('agent_exit'), result.get('verification'))
        result.update(api_calls=len(model.calls), elapsed_seconds=round(time.monotonic() - started, 3),
            estimated_known_no_cache_cny=sum(c.get('estimated_no_cache_cny', 0) for c in model.calls),
            unknown_cost_requests=sum('estimated_no_cache_cny' not in c for c in model.calls),
            budget=ledger.summary())
        save(run / 'result.json', result)
        summaries.append(result)
        save(batch / 'summary.json', {'tasks': summaries, 'planned_tasks': list(task_ids), 'budget': ledger.summary()})
        print(f"Task {task_id}: {result['status']}, success={result['verified_success']}, calls={len(model.calls)}", flush=True)
        if result['status'] == 'execution_error':
            print('Stopping batch for inspection. No automatic retry.', flush=True)
            break
    print(json.dumps(ledger.summary()), flush=True)


if __name__ == '__main__':
    main()
