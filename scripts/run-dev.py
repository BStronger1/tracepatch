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


def verify(task, source):
    env = runtime.WindowsDockerEnvironment(image=IMAGE, executable=runtime.DOCKER,
        cwd='/workspace', timeout=20, container_timeout='90',
        run_args=['--rm', '--network', 'none', '--memory', '256m', '--cpus', '1',
                  '--pids-limit', '64', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges'])
    try:
        docker('cp', str(source), env.container_id + ':/workspace/solution.py')
        docker('cp', str(task / 'verify.py'), env.container_id + ':/workspace/verify.py')
        result = env.execute({'command': 'python -I -c "import sys;sys.path.insert(0,\'/workspace\');import runpy;runpy.run_path(\'/workspace/verify.py\',run_name=\'__main__\')"'})
        return result
    finally:
        env.cleanup()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', required=True)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--policy', choices=('baseline', 'recovery'), default='baseline')
    args = parser.parse_args()
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
    save(batch / 'config.json', config)
    manifest = {'split': 'development', 'benchmark_result': False, 'upstream_commit': commit,
                'image': IMAGE, 'system_prompt': SYSTEM, 'policy': args.policy,
                'reject_provider_truncation': True,
                'model': config['model'], 'max_calls_per_task': 8, 'max_output_tokens': 512,
                'enable_thinking': False, 'observation_char_limit': 6000,
                'input_json_byte_limit': 24000, 'tasks': {}}
    for task_id in TASK_IDS:
        task = ROOT / 'tasks/dev' / task_id
        manifest['tasks'][task_id] = {
            p.relative_to(task).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(task.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    save(batch / 'manifest.json', manifest)
    preflight = {}
    for task_id in TASK_IDS:
        task = ROOT / 'tasks/dev' / task_id
        broken = verify(task, task / 'workspace/solution.py')
        oracle = verify(task, task / 'oracle.py')
        expected_failure = 'ValueError: expected three fields' if task_id == 'long-log' else 'AssertionError'
        passed = broken['returncode'] == 1 and expected_failure in broken['output'] and oracle['returncode'] == 0
        preflight[task_id] = {'broken': broken, 'oracle': oracle, 'valid': passed}
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
    for task_id in TASK_IDS:
        task = ROOT / 'tasks/dev' / task_id
        task_config = json.loads((task / 'task.json').read_text())
        run = batch / f'{args.batch}--{task_id}'
        run.mkdir()
        model = runtime.DmxModel(config, key, run_dir=run, ledger=ledger, policy=args.policy)
        env = runtime.WindowsDockerEnvironment(image=IMAGE, executable=runtime.DOCKER,
            cwd='/workspace', timeout=20, container_timeout='600',
            run_args=['--rm', '--network', 'none', '--memory', '512m', '--cpus', '1',
                      '--pids-limit', '64', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges'])
        started = time.monotonic()
        result = {'task': task_id, 'status': 'started', 'verified_success': False}
        save(run / 'result.json', result)
        try:
            docker('cp', str(task / 'workspace') + '/.', env.container_id + ':/workspace')
            agent = runtime.DefaultAgent(model, env, step_limit=8, cost_limit=0.8,
                wall_time_limit_seconds=300, output_path=run / 'trajectory.json',
                system_template=SYSTEM, instance_template='{{task}}')
            exit_data = agent.run(task_config['instruction'])
            result['agent_exit'] = exit_data.get('exit_status')
            docker('cp', env.container_id + ':/workspace/solution.py', str(run / 'solution.py'))
            result['status'] = 'agent_finished'
        except Exception as error:
            result.update(status='execution_error', error_type=type(error).__name__)
        finally:
            env.cleanup()
        if (run / 'solution.py').exists():
            result['verification'] = verify(task, run / 'solution.py')
            result['verified_success'] = result['verification']['returncode'] == 0
            result['status'] = 'verified'
            patch = ''.join(difflib.unified_diff((task / 'workspace/solution.py').read_text().splitlines(True),
                (run / 'solution.py').read_text().splitlines(True), fromfile='a/solution.py', tofile='b/solution.py'))
            (run / 'patch.diff').write_text(patch, encoding='utf-8')
        if (run / 'trajectory.json').exists():
            trajectory = json.loads((run / 'trajectory.json').read_text())
            result['diagnostics'] = analyze(trajectory)
            result['format_error_count'] = sum(m.get('role') == 'assistant' and not m.get('extra', {}).get('actions')
                                                for m in trajectory['messages'])
        result.update(api_calls=len(model.calls), elapsed_seconds=round(time.monotonic() - started, 3),
            estimated_known_no_cache_cny=sum(c.get('estimated_no_cache_cny', 0) for c in model.calls),
            unknown_cost_requests=sum('estimated_no_cache_cny' not in c for c in model.calls),
            budget=ledger.summary())
        save(run / 'result.json', result)
        summaries.append(result)
        save(batch / 'summary.json', {'tasks': summaries, 'planned_tasks': list(TASK_IDS), 'budget': ledger.summary()})
        print(f"Task {task_id}: {result['status']}, success={result['verified_success']}, calls={len(model.calls)}", flush=True)
        if result['status'] == 'execution_error':
            print('Stopping batch for inspection. No automatic retry.', flush=True)
            break
    print(json.dumps(ledger.summary()), flush=True)


if __name__ == '__main__':
    main()
