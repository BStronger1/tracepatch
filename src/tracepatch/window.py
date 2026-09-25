"""Keep original instructions and recent complete assistant/observation turns."""
import hashlib
import json


def request_payload(model: str, messages: list[dict], policy: str = 'none', byte_limit: int = 24000, *, tool_options=None):
    if policy not in ('none', 'recent-turns'):
        raise ValueError('Unknown context policy')
    def encode(wire):
        return json.dumps({'model': model, 'messages': wire, 'max_tokens': 512,
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
    for start in boundaries:
        if start <= 2:
            continue
        omitted = messages[2:start]
        marker = {'role': 'user', 'content': f'Harness context notice: {len(omitted)} earlier messages omitted to fit input limits. Original task and recent turns retained. Re-read files if needed; do not invent missing facts.'}
        candidate = encode(messages[:2] + [marker] + messages[start:])
        if len(candidate) <= byte_limit:
            metadata.update(omitted_messages=len(omitted),
                omitted_sha256=hashlib.sha256(json.dumps(omitted).encode()).hexdigest())
            return candidate, metadata
    raise RuntimeError('Task and newest complete turn exceed input byte limit')
