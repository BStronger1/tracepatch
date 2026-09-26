"""Keep original instructions and recent complete assistant/observation turns."""
import hashlib
import json


def validate_output_limit(value):
    if type(value) is not int or value not in (512, 1024):
        raise ValueError('Output limit must be 512 or 1024 tokens')
    return value


def request_payload(model: str, messages: list[dict], policy: str = 'none', byte_limit: int = 24000, *, tool_options=None, max_output_tokens=512, memory_notice=None):
    validate_output_limit(max_output_tokens)
    if policy not in ('none', 'recent-turns'):
        raise ValueError('Unknown context policy')
    def encode(wire):
        return json.dumps({'model': model, 'messages': wire, 'max_tokens': max_output_tokens,
                           'enable_thinking': False, 'stream': False, **(tool_options or {})}).encode()
    raw = encode(messages)
    metadata = {'context_policy': policy, 'original_request_bytes': len(raw), 'omitted_messages': 0}
    if len(raw) <= byte_limit:
        return raw, metadata
    if policy == 'none':
        raise RuntimeError('Input byte limit reached')
    if len(messages) < 3 or messages[0]['role'] != 'system' or messages[1]['role'] != 'user':
        raise ValueError('Expected original system and task messages')
    # Never cut in the middle of an assistant/observation group. Preserve newest group.
    boundaries = [i for i in range(2, len(messages)) if messages[i]['role'] == 'assistant']
    # Memory competes within the same total budget; never drop the newest tool pair.
    options = [memory_notice, None] if memory_notice else [None]
    for memory in options:
        for start in boundaries:
            if start <= 2:
                continue
            omitted = messages[2:start]
            marker = {'role': 'user', 'content': f'Harness context notice: {len(omitted)} earlier messages omitted to fit input limits. Original task and recent turns retained. Re-read files if needed; do not invent missing facts.'}
            extra = [{'role': 'user', 'content': memory}] if memory else []
            candidate = encode(messages[:2] + [marker] + extra + messages[start:])
            if len(candidate) <= byte_limit:
                metadata.update(omitted_messages=len(omitted),
                    omitted_sha256=hashlib.sha256(json.dumps(omitted).encode()).hexdigest())
                if memory_notice:
                    metadata.update(memory_included=memory is not None,
                        memory_sha256=hashlib.sha256(memory.encode()).hexdigest() if memory else None,
                        memory_bytes=len(memory.encode()) if memory else 0,
                        memory_dropped_for_budget=memory is None)
                return candidate, metadata
    raise RuntimeError('Task and newest complete turn exceed input byte limit')
