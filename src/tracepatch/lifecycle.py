"""Budget guidance is advisory; submission and external correctness remain separate."""


def budget_notice(calls_used: int, call_limit: int, *, submission_aware=False) -> str:
    if (type(calls_used) is not int or type(call_limit) is not int
            or call_limit <= 0 or not 0 <= calls_used <= call_limit):
        raise ValueError('Invalid model-call counters')
    remaining = call_limit - calls_used
    if not remaining:
        raise ValueError('No model calls remain')
    notice = (f'Harness budget: {remaining} model calls remain INCLUDING this reply. '
              'Rejected or truncated replies also consume a call. ')
    if submission_aware and remaining <= 3:
        notice += ('Prioritize required fixes and focused checks; avoid adding optional tests. '
                   'The environment recognizes submission ONLY when the marker is the FIRST output line '
                   'and the command exits zero. After checks pass, use a separate bash call containing only '
                   'echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT. '
                   'If checks must run in this same call, capture BOTH stdout and stderr to a log, '
                   'print the marker first ONLY on success, and on failure show the log and exit nonzero. '
                   'Do not hide failures behind a pipeline or print a marker unconditionally. '
                   'Never claim completion when required checks fail. ')
        return notice + 'Submission is a completion signal, not proof of independent verification.'
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
    if policy not in ('baseline', 'recovery', 'recovery-budget', 'recovery-submit'):
        raise ValueError('Unknown policy')
    wire = [{'role': m['role'], 'content': m.get('content', '')} for m in messages]
    notice = budget_notice(calls_used, call_limit, submission_aware=policy == 'recovery-submit') if policy in ('recovery-budget', 'recovery-submit') else None
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
