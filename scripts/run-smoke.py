"""One-shot teaching task using the pinned upstream DefaultAgent and DockerEnvironment."""
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT.parent / 'vendor/mini-swe-agent'
RUN = ROOT / 'runs/smoke-003'
DOCKER = r'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
os.environ['MSWEA_GLOBAL_CONFIG_DIR'] = str(ROOT / 'artifacts/mini-config')
os.environ['MSWEA_SILENT_STARTUP'] = '1'
sys.path.insert(0, str(UPSTREAM / 'src'))
sys.path.insert(0, str(ROOT / 'src'))
from tracepatch.actions import parse_action
from tracepatch.recovery import diagnose_action, recovery_feedback
from tracepatch.lifecycle import prepare_messages
from tracepatch.window import request_payload
from minisweagent.agents.default import DefaultAgent
from minisweagent.environments.docker import DockerEnvironment
from minisweagent.exceptions import FormatError


def docker(*args, check=True):
    return subprocess.run([DOCKER, *args], capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=180, check=check)


class WindowsDockerEnvironment(DockerEnvironment):
    def cleanup(self):
        if self.container_id:
            docker('rm', '-f', self.container_id, check=False)
            self.container_id = None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class DmxModel:
    """Thin adapter; fixed model, no retries, no secrets in serialization."""
    def __init__(self, config, key, *, run_dir=None, ledger=None, policy='baseline', max_calls=8, context_policy='none'):
        self.config = config
        self.key = key
        self.calls = []
        self.run_dir = run_dir or RUN
        self.ledger = ledger
        self.context_policy = context_policy
        if max_calls not in (8, 12, 24):
            raise ValueError('Unsupported request limit')
        self.max_calls = max_calls
        if policy not in ('baseline', 'recovery', 'recovery-budget'):
            raise ValueError('Unknown policy')
        self.policy = policy

    def format_message(self, **kwargs):
        return kwargs

    def get_template_vars(self, **kwargs):
        return {}

    def serialize(self):
        return {'info': {'provider': 'DMXAPI', 'model': self.config['model'],
                         'currency': 'CNY', 'request_records': self.calls}}

    def query(self, messages):
        if len(self.calls) >= self.max_calls:
            raise RuntimeError('Smoke request limit reached')
        wire, notice = prepare_messages(messages, len(self.calls), self.max_calls, self.policy)
        payload, context_metadata = request_payload(self.config['model'], wire, self.context_policy)
        # At quoted prices even input + cache creation per byte and full output
        # fits within 0.1 CNY/request. Reserve 0.8 CNY for all 8 requests.
        record = {'index': len(self.calls) + 1, 'status': 'started',
                  'request_bytes': len(payload), 'reserved_cny': 0.1}
        record.update(calls_remaining_including_current=self.max_calls - len(self.calls), budget_notice=notice)
        record.update(context_metadata)
        if self.ledger:
            self.ledger.reserve(f'{self.run_dir.name}:{record["index"]}')
        self.calls.append(record)
        self.save_calls()
        request = urllib.request.Request(self.config['base_url'] + '/chat/completions',
            data=payload, headers={'Content-Type': 'application/json',
                                  'Authorization': 'Bearer ' + self.key}, method='POST')
        started = time.monotonic()
        try:
            opener = urllib.request.build_opener(NoRedirect, urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=90) as response:
                data = json.load(response)
        except Exception as error:
            record['status'] = 'request_failed'
            record['error_type'] = type(error).__name__
            self.save_calls()
            raise RuntimeError('Provider request failed; inspect request metadata, no automatic retry') from None
        record['elapsed_seconds'] = round(time.monotonic() - started, 3)
        usage = data.get('usage', {})
        if any(type(usage.get(k)) is not int for k in ('prompt_tokens', 'completion_tokens')):
            record['status'] = 'missing_usage'
            self.save_calls()
            raise RuntimeError('Missing usage; stop to avoid unaccounted calls')
        record.update(status='completed', prompt_tokens=usage['prompt_tokens'],
                      completion_tokens=usage['completion_tokens'])
        pricing = self.config['pricing']
        record['estimated_no_cache_cny'] = (usage['prompt_tokens'] * pricing['input'] +
                                           usage['completion_tokens'] * pricing['output']) / 1e6
        self.save_calls()
        if usage['completion_tokens'] > 512:
            raise RuntimeError('Provider exceeded requested output limit; stop')
        text = data['choices'][0]['message'].get('content') or ''
        finish_reason = data['choices'][0].get('finish_reason')
        reason = diagnose_action(text, finish_reason)
        record.update(finish_reason=finish_reason, action_diagnosis=reason, policy=self.policy)
        self.save_calls()
        try:
            actions = [parse_action(text)]
        except ValueError:
            actions = []
        # Shared safety gate for both arms; recovery changes feedback only.
        if finish_reason == 'length':
            actions = []
        extra = {'cost': record['estimated_no_cache_cny'], 'usage': usage,
                 'actions': [{'command': actions[0]}] if len(actions) == 1 else []}
        message = {'role': 'assistant', 'content': text, 'extra': extra}
        print(f"Model call {len(self.calls)}: {usage['prompt_tokens']} input / {usage['completion_tokens']} output tokens")
        if len(actions) != 1:
            feedback = recovery_feedback(reason) if self.policy != 'baseline' else 'Return exactly one fenced bash action.'
            raise FormatError(message, {'role': 'user', 'content': feedback})
        return message

    def save_calls(self):
        (self.run_dir / 'requests.json').write_text(json.dumps(self.calls, indent=2), encoding='utf-8')
        if self.ledger and self.calls:
            record = self.calls[-1]
            self.ledger.record(f'{self.run_dir.name}:{record["index"]}', record)

    def format_observation_messages(self, message, outputs, template_vars=None):
        return [{'role': 'user', 'content': json.dumps(output, ensure_ascii=False)[:6000]}
                for output in outputs]


def verify(image, source):
    cid = docker('run', '-d', '--network', 'none', '--memory', '256m', '--cpus', '1',
                 '--pids-limit', '64', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                 '-w', '/workspace', image, 'sleep', '300').stdout.strip()
    try:
        docker('cp', str(source), cid + ':/workspace/ranges.py')
        docker('cp', str(ROOT / 'tasks/smoke/verify.py'), cid + ':/workspace/verify.py')
        result = docker('exec', '-w', '/workspace', cid, 'python', '-I', '-c',
                        "import sys;sys.path.insert(0,'/workspace');import runpy;runpy.run_path('/workspace/verify.py',run_name='__main__')",
                        check=False)
        return {'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
    finally:
        docker('rm', '-f', cid, check=False)


def main():
    config = json.loads((ROOT / 'configs/model.json').read_text())
    if config['first_run_budget_cny'] < 1:
        raise RuntimeError('Smoke reserves 1 CNY including prior probe allowance')
    env = dict(line.split('=', 1) for line in (ROOT / '.env').read_text().splitlines()
               if '=' in line and not line.startswith('#'))
    if not re.fullmatch(r'sk-[A-Za-z0-9_-]{16,}', env.get('OPENAI_API_KEY', '')):
        raise RuntimeError('Invalid key format')
    commit = subprocess.run(['git', '-c', f'safe.directory={UPSTREAM.as_posix()}', '-C', str(UPSTREAM),
                              'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    if commit != '04d809ceab9df28f9adaed044884180159172930':
        raise RuntimeError('Upstream commit changed')
    image = docker('image', 'inspect', 'python:3.12-slim', '--format', '{{index .RepoDigests 0}}').stdout.strip()
    RUN.mkdir(parents=True, exist_ok=False)
    original = ROOT / 'tasks/smoke/workspace/ranges.py'
    before = verify(image, original)
    (RUN / 'before.json').write_text(json.dumps(before, indent=2))
    if before['returncode'] == 0:
        raise RuntimeError('Broken fixture unexpectedly passed')
    agent_env = WindowsDockerEnvironment(image=image, executable=DOCKER, cwd='/workspace', timeout=20,
        run_args=['--rm', '--network', 'none', '--memory', '512m', '--cpus', '1', '--pids-limit', '64',
                  '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges'], container_timeout='600')
    started = time.monotonic()
    try:
        docker('cp', str(ROOT / 'tasks/smoke/workspace') + '/.', agent_env.container_id + ':/workspace')
        model = DmxModel(config, env['OPENAI_API_KEY'])
        agent = DefaultAgent(model, agent_env, step_limit=8, cost_limit=0.8,
            wall_time_limit_seconds=300, output_path=RUN / 'trajectory.json',
            system_template='You fix Python code in /workspace. Return one brief action description and exactly one fenced bash command. Inspect files, edit the implementation, run tests. No network is available. When done issue only: echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT',
            instance_template='{{task}}')
        result = agent.run('Fix inclusive_range(start, stop) in ranges.py. It must return all integers from start to stop inclusive, ascending or descending as appropriate, and one element when equal. Preserve the function interface. Run visible tests. Do not edit test_visible.py.')
        docker('cp', agent_env.container_id + ':/workspace/ranges.py', str(RUN / 'ranges.py'))
    finally:
        agent_env.cleanup()
    after = verify(image, RUN / 'ranges.py')
    patch = ''.join(difflib.unified_diff(original.read_text().splitlines(True),
                     (RUN / 'ranges.py').read_text().splitlines(True), fromfile='a/ranges.py', tofile='b/ranges.py'))
    (RUN / 'patch.diff').write_text(patch)
    summary = {'task': 'synthetic-inclusive-range-smoke', 'benchmark_result': False,
        'upstream_commit': commit, 'image': image, 'agent_exit': result.get('exit_status'),
        'enable_thinking': False, 'max_output_tokens': 512,
        'before': before, 'after': after, 'verified_success': after['returncode'] == 0,
        'api_calls': len(model.calls), 'estimated_no_cache_cny': sum(c.get('estimated_no_cache_cny', 0) for c in model.calls),
        'cost_note': 'User quote estimate, not provider bill; no cache discounts assumed.',
        'reserved_cny': len(model.calls) * 0.1,
        'elapsed_seconds': round(time.monotonic() - started, 3),
        'patch_sha256': hashlib.sha256(patch.encode()).hexdigest()}
    (RUN / 'result.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({k: summary[k] for k in ('verified_success', 'api_calls', 'estimated_no_cache_cny', 'elapsed_seconds')}, indent=2))


if __name__ == '__main__':
    main()
