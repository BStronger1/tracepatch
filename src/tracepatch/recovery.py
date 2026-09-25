"""Deterministic feedback for rejected actions; never repair or execute partial code."""
from tracepatch.actions import parse_action


def diagnose_action(text: str, finish_reason: str | None = None) -> str:
    # A provider-declared truncated response is rejected even with a closed fence.
    if finish_reason == 'length':
        return 'output_limit'
    try:
        parse_action(text)
    except ValueError:
        if '<tool_call>' in text:
            return 'malformed_tool_call'
        if text.count('```bash') > 1:
            return 'multiple_actions'
        if '```bash' in text:
            return 'incomplete_action'
        return 'missing_action'
    return 'valid'


def recovery_feedback(reason: str, max_output_tokens: int = 512) -> str:
    prefix = 'Your previous response was rejected. No command from that response was executed. '
    if reason == 'output_limit':
        detail = (f'The provider reported output truncation at the {max_output_tokens}-token limit. '
                  'Split large edits and test scripts across turns; send one short complete command now. ')
    elif reason == 'missing_action':
        detail = ('A prose answer cannot finish this task. If all work is done, use the command '
                  'echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT. Otherwise send your next command. ')
    else:
        detail = 'Send one short complete command; close the code fence and any quotes or heredoc. '
    return prefix + detail + 'Use exactly one fenced bash code block and no tool-call XML.'
