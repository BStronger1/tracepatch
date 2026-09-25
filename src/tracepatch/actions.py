"""Explicit, narrow compatibility for text-form bash actions."""
import re


def parse_action(text: str) -> str:
    fenced = re.findall(r'```bash\s*\n(.*?)```', text, re.S)
    native = re.findall(
        r'<tool_call>\s*<function=bash>\s*<parameter=command>\s*\n(.*?)\s*</parameter>\s*</function>\s*</tool_call>',
        text, re.S)
    if '<tool_call>' in text:
        if fenced or text.count('<tool_call>') != 1 or len(native) != 1:
            raise ValueError('Expected exactly one complete bash tool call')
        return native[0]
    if len(fenced) != 1:
        raise ValueError('Expected exactly one bash code block')
    return fenced[0]
