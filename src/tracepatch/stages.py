"""Evidence-bound stage guidance; no automatic edits, tests or submission."""
from copy import deepcopy

from tracepatch.progress import snapshot_digest, validate_snapshot


def decide_stage(initial, current, checks, public, calls_used, call_limit, *, inspect_calls=6):
    if (type(calls_used) is not int or type(call_limit) is not int or
            not 0 <= calls_used < call_limit or type(inspect_calls) is not int or inspect_calls < 1):
        raise ValueError('Invalid stage counters')
    initial = validate_snapshot(initial, initial)
    remaining = call_limit - calls_used
    state = {'stage': 'observation_unknown', 'calls_remaining': remaining,
             'source_sha256': None, 'net_changed_files': None, 'public_status': 'unknown',
             'check_status': None, 'check_sha256': None, 'required_tool': None}
    if current is None:
        return state
    current = validate_snapshot(current, initial)
    if any(value is None for value in current.values()):
        return state
    digest = snapshot_digest(current)
    changed = sum(current[k] != initial[k] for k in current)
    state.update(source_sha256=digest, net_changed_files=changed)
    if public and public.get('source_sha256') == digest and public.get('status') in ('passed', 'failed'):
        state['public_status'] = public['status']
    latest = next((record for record in reversed(checks)
        if record.get('provenance') == 'agent-authored-python' and record.get('source_state') == 'unchanged'
        and record.get('source_before_sha256') == record.get('source_after_sha256') == digest), None)
    if latest:
        state.update(check_status=latest['status'], check_sha256=latest['check_sha256'])
    if remaining <= 2:
        state['stage'] = 'final_review'
    elif latest is None and (changed or calls_used >= inspect_calls):
        state.update(stage='check_patch' if changed else 'check_hypothesis', required_tool='python_check')
    elif latest is None:
        state['stage'] = 'inspect'
    elif latest['status'] in ('unknown', 'timed_out'):
        state['stage'] = 'diagnose_check'
    elif changed and latest['status'] == 'process_passed' and state['public_status'] == 'passed':
        state['stage'] = 'review_submission'
    elif changed:
        state['stage'] = 'repair_or_recheck'
    else:
        state['stage'] = 'implement'
    return state


def stage_notice(state):
    instructions = {
        'observation_unknown': 'Source observation is incomplete. Inspect or restore the relevant files; no prior check certifies the current state.',
        'inspect': 'Inspect the relevant implementation and identify one falsifiable explanation; keep room for a focused edit, test and submission.',
        'check_hypothesis': 'The inspection allowance has been used without a version-matched structured check. This reply must call python_check with a small assertion that tests the public reproduction or your current hypothesis. Use the real checkout APIs. Do not edit source inside this check.',
        'check_patch': 'The source has changed and lacks a matching structured check. This reply must call python_check with focused assertions for the change and relevant original requirements. Do not edit source inside this check.',
        'implement': 'A structured check has run but there is no net source change. If the task still needs fixing, use bash to make one focused edit at a location confirmed in the actual checkout. If evidence is insufficient, choose one targeted diagnostic rather than another broad listing. Do not invent replacement text or make cosmetic edits to reset this stage.',
        'repair_or_recheck': 'Review the most recent check and public reproduction. Check whether the failing expectation matches the original requirements, then repair the implementation or the mistaken check. Do not assume a self-test pass overrides a public failure.',
        'diagnose_check': 'The structured check timed out or had an execution problem. Diagnose that problem or simplify the check; do not count it as a pass and do not submit on this evidence.',
        'review_submission': 'The current source has a zero-exit self-check and a passing narrow public reproduction. Review ALL original requirements and compatibility before submitting. If ready, use a separate bash action containing only echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT.',
        'final_review': 'Only the final calls remain. Resolve the most important known failure or check the current patch, reserving submission when feasible. Submit in a separate bash action only if ready; never claim completion merely because the budget is ending.',
    }
    return (f"Harness stage: {state['stage']}; {state['calls_remaining']} calls remain; "
            f"net changed files={state['net_changed_files']}; public={state['public_status']}; "
            f"agent-authored check={state['check_status']}. " + instructions[state['stage']] +
            ' These are execution observations, not independent acceptance or proof of a stall. '
            'Only you choose code changes and submission; a passing self-check does not prove correctness.')


def stage_tool_options(options, state, *, enabled):
    result = deepcopy(options)
    if enabled and state['required_tool'] is not None:
        names = {tool['function']['name'] for tool in options['tools']}
        if state['required_tool'] not in names:
            raise ValueError('Required stage tool is unavailable')
        result['tool_choice'] = {'type': 'function', 'function': {'name': state['required_tool']}}
    return result
