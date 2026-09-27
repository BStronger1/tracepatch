"""Offline, synthetic walkthrough of real TracePatch modules; no API or Docker."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from tracepatch.editing import replace_source, validate_edit
from tracepatch.lifecycle import completion_status
from tracepatch.memory import EvidenceMemory
from tracepatch.window import request_payload


def walkthrough(output):
    output.mkdir(parents=True, exist_ok=False)
    fixture = output / 'example.py'
    fixture.write_bytes(b'def example():\r\n    return missing\r\n')

    def snapshot():
        return {'example.py': hashlib.sha256(fixture.read_bytes()).hexdigest()}

    def reader(ranges):
        return [dict(r, version=snapshot()['example.py'], excerpt=fixture.read_text(encoding='utf-8'),
                     excerpt_truncated=False) for r in ranges]

    memory = EvidenceMemory(['example.py'], output / 'memory.json', reader)
    initial = snapshot()
    memory.observe(1, 'sed -n 1,2p example.py',
                   {'output': fixture.read_text(encoding='utf-8'), 'returncode': 0}, initial, initial)
    _, before = memory.recall(initial)
    assert before[0]['source_status'] == 'current'

    # Fixed local fixture only. Do not execute source or consume model output.
    old = 'def example():\n    return missing'
    edit = validate_edit({'path': 'example.py', 'old': old, 'new': 'def example():\n    return 7'})
    exact_matches = fixture.read_bytes().decode('utf-8').count(old)
    assert exact_matches == 0
    changed = replace_source(output, ['example.py'], edit)
    assert changed['status'] == 'applied' and changed['match_mode'] == 'line-ending-normalized'
    assert changed['acceptance_verified'] is None
    assert fixture.read_bytes() == b'def example():\r\n    return 7\r\n'
    updated = snapshot()
    assert initial != updated
    stale_text, stale = memory.recall(updated)
    assert stale[0]['source_status'] == 'stale' and 'return missing' not in stale_text

    rejected = replace_source(output, ['example.py'], validate_edit(
        {'path': 'example.py', 'old': 'return 7', 'new': 'return ('}))
    assert rejected['status'] == 'syntax_error' and snapshot() == updated
    memory.observe(2, 'sed -n 1,2p example.py',
                   {'output': fixture.read_text(encoding='utf-8'), 'returncode': 0}, updated, updated)
    notice, reread = memory.recall(updated)
    assert reread[0]['source_status'] == 'current' and 'return 7' in notice

    history = [{'role': 'system', 'content': 'Synthetic offline demonstration.'},
               {'role': 'user', 'content': 'Inspect the example function.'}]
    for i in range(4):
        history.extend([{'role': 'assistant', 'content': f'synthetic read {i}'},
                        {'role': 'user', 'content': 'x' * 1800}])
    payload, context = request_payload('offline-demo', history, 'recent-turns', 3600, memory_notice=notice)
    assert len(payload) <= 3600 and context['memory_included'] and context['omitted_messages'] > 0
    memory.save_recall(notice)

    # Hypothetical verifier metadata: no actual repair scores are generated.
    outcomes = [completion_status('Submitted', {'returncode': 1}),
                completion_status('LimitsExceeded', {'returncode': 0}),
                completion_status('Submitted', {'returncode': 0}),
                completion_status('Submitted', None)]
    assert [o['state'] for o in outcomes] == ['failed_submitted', 'verified_unsubmitted',
                                            'verified_submitted', 'unverified_submitted']
    report = {'synthetic': True, 'model_api_calls': 0, 'docker_used': False, 'source_executed': False,
              'scope': 'Real module mechanism checks on a fixed toy fixture; not model repair evidence.',
              'editing': {'initial_exact_matches': exact_matches, 'accepted': changed, 'rejected': rejected,
                          'initial_snapshot': initial, 'final_snapshot': updated, 'crlf_preserved': True},
              'memory': {'before': before, 'after_edit': stale, 'after_reread': reread,
                         'payload_bytes': len(payload), 'byte_limit': 3600, 'context': context},
              'hypothetical_completion_states': outcomes,
              'implementation_hashes': {n: hashlib.sha256((ROOT / 'src/tracepatch' / n).read_bytes()).hexdigest()
                                        for n in ('editing.py', 'memory.py', 'window.py', 'lifecycle.py')}}
    (output / 'demo-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (output / 'WALKTHROUGH.md').write_text(
        '# TracePatch 离线演示结果\n\n'
        '合成示例，零 API、零 Docker，未执行候选源码，不属于模型修复成绩。\n\n'
        '1. LF 参数成功替换 CRLF 源码，保留原换行；语法错误修改被拒绝，文件不变。\n'
        '2. 旧源码卡片由 current 变为 stale，重新读取后恢复 current。\n'
        f'3. 历史删减后补回有效证据，请求为 {len(payload)}/3600 字节。\n'
        '4. 模拟验收失败但提交、验收通过未提交、通过且提交、验收未知四种状态。\n\n'
        '逐项哈希和元数据见 demo-report.json；真实模型实验见仓库 reports/edit-study-001.md。\n',
        encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True, help='New directory; existing paths are never overwritten')
    args = parser.parse_args()
    report = walkthrough(args.output_dir)
    print('SYNTHETIC DEMO | API calls: 0 | Docker: no | source execution: no')
    print('EDIT: CRLF preserved; syntax error rejected; acceptance remains unknown.')
    print('MEMORY: current -> stale -> current; obsolete source excluded.')
    print(f"CONTEXT: {report['memory']['payload_bytes']}/3600 bytes; evidence included after pruning.")
    print('OUTCOMES: submission, acceptance failure, success and unknown stay separate.')
    print('PASS | Read WALKTHROUGH.md and demo-report.json in ' + str(args.output_dir))
