"""Two-call native-protocol handshake; tool outputs are explicitly simulated."""
import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from tracepatch.budget import BudgetLedger

spec = importlib.util.spec_from_file_location('runtime', ROOT / 'scripts/run-smoke.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--name', required=True)
args = parser.parse_args()
if not re.fullmatch(r'native-probe-[a-z0-9-]{1,40}', args.name):
    parser.error('Use a new native-probe-... run name')
run = ROOT / 'runs' / args.name
run.mkdir(exist_ok=False)
config = json.loads((ROOT / 'configs/model.json').read_text())
local = dict(line.split('=', 1) for line in (ROOT / '.env').read_text().splitlines()
             if '=' in line and not line.startswith('#'))
ledger = BudgetLedger(ROOT / 'artifacts/budget-ledger.json', str(config['first_run_budget_cny']))
model = runtime.DmxModel(config, local['OPENAI_API_KEY'], run_dir=run, ledger=ledger, action_protocol='native')
messages = [{'role': 'system', 'content': 'This is a tool protocol test. Call bash exactly as instructed. No actual shell execution will occur; tool results are simulated.'},
            {'role': 'user', 'content': 'Call bash with command exactly: printf TRACEPATCH_TOOL_OK'}]
result = {'model': config['model'], 'simulated_tool_outputs': True, 'executed_commands': 0,
          'round_trip_verified': False}
try:
    first = model.query(messages)
    if first['extra']['actions'][0]['command'] != 'printf TRACEPATCH_TOOL_OK':
        raise ValueError('Unexpected probe command')
    messages.append(first)
    messages.extend(model.format_observation_messages(first, [{'returncode': 0, 'output': 'TRACEPATCH_TOOL_OK', 'simulated': True}]))
    messages.append({'role': 'user', 'content': 'Confirm receipt of the simulated tool result by calling bash with command exactly: printf TRACEPATCH_ACK'})
    second = model.query(messages)
    if second['extra']['actions'][0]['command'] != 'printf TRACEPATCH_ACK':
        raise ValueError('Unexpected acknowledgement command')
    result['round_trip_verified'] = True
except Exception as error:
    result['error_type'] = type(error).__name__
result.update(api_calls=len(model.calls), estimated_no_cache_cny=sum(c.get('estimated_no_cache_cny', 0) for c in model.calls),
              observations=[{k: c.get(k) for k in ('index', 'status', 'finish_reason', 'action_diagnosis')} for c in model.calls])
(run / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
if not result['round_trip_verified']:
    raise SystemExit(1)
