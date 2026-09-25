"""Budget guidance is advisory; submission and external correctness remain separate."""


def budget_notice(calls_used: int, call_limit: int) -> str:
    if (type(calls_used) is not int or type(call_limit) is not int
            or call_limit <= 0 or not 0 <= calls_used <= call_limit):
        raise ValueError('Invalid model-call counters')
    remaining = call_limit - calls_used
    if not remaining:
        raise ValueError('No model calls remain')
    notice = (f'Harness budget: {remaining} model calls remain INCLUDING this reply. '
              'Rejected or truncated replies also consume a call. ')
    if remaining == 1:
        notice += ('This is the final call. If the fix is ready, run the relevant tests and use '
                   '&& echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT only if they pass. '
                   'If the fix is not ready, do the most useful remaining work; do not claim completion. ')
    elif remaining <= 3:
        notice += ('Prioritize required fixes and focused tests; reserve a call for submission. '
                   'Avoid expanding optional test scripts. ')
    else:
        notice += 'Plan inspection, edits, focused tests and submission within this limit. '
    return notice + 'Submission is a completion signal, not proof of independent verification.'


def prepare_messages(messages: list[dict], calls_used: int, call_limit: int, policy: str) -> tuple[list[dict], str | None]:
    if policy not in ('baseline', 'recovery', 'recovery-budget'):
        raise ValueError('Unknown policy')
    wire = [{'role': m['role'], 'content': m.get('content', '')} for m in messages]
    notice = budget_notice(calls_used, call_limit) if policy == 'recovery-budget' else None
    if notice:
        wire.append({'role': 'user', 'content': notice})
    return wire, notice


def completion_status(agent_exit: str | None, verification: dict | None) -> dict:
    code = verification.get('returncode') if verification else None
    verified = code == 0 if type(code) is int else None
    submitted = agent_exit == 'Submitted'
    state = ('verified_submitted' if submitted else 'verified_unsubmitted') if verified is True else (
        ('failed_submitted' if submitted else 'failed_unsubmitted') if verified is False else
        ('unverified_submitted' if submitted else 'unverified_unsubmitted'))
    return {'state': state, 'patch_verified': verified, 'agent_submitted': submitted,
            'agent_exit': agent_exit, 'verification_returncode': code}
