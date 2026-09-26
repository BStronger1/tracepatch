"""Strict single-bash function calls and complete tool/result history."""
import json

TOOL_OPTIONS = {
    'tools': [{'type': 'function', 'function': {'name': 'bash',
        'description': 'Run one shell command in the isolated task container.',
        'parameters': {'type': 'object', 'properties': {'command': {'type': 'string'}},
                       'required': ['command'], 'additionalProperties': False}}}],
    'tool_choice': {'type': 'function', 'function': {'name': 'bash'}},
    'parallel_tool_calls': False,
}

TEST_TOOL_OPTIONS = {
    'tools': TOOL_OPTIONS['tools'] + [{'type': 'function', 'function': {
        'name': 'python_check',
        'description': 'Run your focused Python assertions directly, without shell exit-code logic. Returns process status, output and source-version hashes. Agent-authored checks are not independent acceptance. Does not submit.',
        'parameters': {'type': 'object', 'properties': {'code': {'type': 'string'}},
                       'required': ['code'], 'additionalProperties': False}}}],
    'tool_choice': 'required', 'parallel_tool_calls': False,
}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def parse_tool_call(message: dict, finish_reason: str | None, *, allow_python_check=False) -> tuple[str, dict]:
    if finish_reason == 'length':
        raise ValueError('output_limit')
    if finish_reason not in ('tool_calls', 'stop'):
        raise ValueError('unsupported_finish_reason')
    calls = message.get('tool_calls')
    if not isinstance(calls, list) or len(calls) != 1:
        raise ValueError('expected_one_tool_call')
    call = calls[0]
    if not isinstance(call, dict) or call.get('type') != 'function' or not isinstance(call.get('id'), str) or not call['id'].strip():
        raise ValueError('invalid_tool_call')
    function = call.get('function')
    allowed = ('bash', 'python_check') if allow_python_check else ('bash',)
    if not isinstance(function, dict) or function.get('name') not in allowed or not isinstance(function.get('arguments'), str):
        raise ValueError('invalid_function')
    try:
        args = json.loads(function['arguments'], object_pairs_hook=unique_object)
    except ValueError:
        raise ValueError('invalid_arguments_json') from None
    field = 'command' if function['name'] == 'bash' else 'code'
    if not isinstance(args, dict) or set(args) != {field} or not isinstance(args[field], str) or not args[field].strip():
        raise ValueError('invalid_command_schema')
    if '\x00' in args[field] or (field == 'code' and len(args[field].encode()) > 16000):
        raise ValueError('invalid_command_schema')
    canonical = {'id': call['id'], 'type': 'function',
                 'function': {'name': function['name'], 'arguments': json.dumps(args)}}
    return args[field], canonical


def native_history(messages: list[dict], *, allow_python_check=False) -> list[dict]:
    wire = []
    for message in messages:
        item = {'role': message['role'], 'content': message.get('content', '')}
        if message.get('tool_calls'):
            item['tool_calls'] = message['tool_calls']
        if message['role'] == 'tool':
            item['tool_call_id'] = message.get('tool_call_id')
        wire.append(item)
    validate_history(wire, allow_python_check=allow_python_check)
    return wire


def validate_history(messages: list[dict], *, allow_python_check=False):
    pending = None
    for message in messages:
        if pending is not None:
            if message.get('role') != 'tool' or message.get('tool_call_id') != pending:
                raise ValueError('Tool call must be followed by its matching result')
            pending = None
            continue
        if message.get('role') == 'tool':
            raise ValueError('Orphan tool result')
        if message.get('tool_calls'):
            if message.get('role') != 'assistant':
                raise ValueError('Only assistants issue tools')
            _, call = parse_tool_call(message, 'tool_calls', allow_python_check=allow_python_check)
            pending = call['id']
    if pending is not None:
        raise ValueError('Missing tool result')
