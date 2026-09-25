"""Store full local tool evidence and build a bounded, explicitly truncated preview."""
import hashlib
import json
from pathlib import Path


def preserve_observation(output: dict, evidence_dir: Path, char_limit: int = 6000) -> dict:
    """The excerpt is a preview, not a semantic summary or agent-readable file tool."""
    if char_limit < 800:
        raise ValueError('Observation limit must allow metadata and two excerpts')
    raw = json.dumps(output, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_dir / f'{digest}.json'
    try:
        with path.open('x', encoding='utf-8') as handle:
            handle.write(raw)
    except FileExistsError:
        if path.read_text(encoding='utf-8') != raw:
            raise ValueError('Evidence hash does not match existing file') from None
    if len(raw) <= char_limit:
        return {'content': raw, 'evidence_sha256': digest, 'truncated': False}
    # JSON metadata stays intact. Only the output text is excerpted.
    body = str(output.get('output', ''))
    envelope = {'returncode': output.get('returncode'), 'truncated': True,
                'evidence_sha256': digest, 'original_json_chars': len(raw),
                'notice': 'Head/tail preview; middle omitted. Full evidence stored locally for audit.',
                'head': '', 'tail': ''}
    low, high = 0, len(body) // 2
    while low < high:
        count = (low + high + 1) // 2
        envelope.update(head=body[:count], tail=body[-count:] if count else '')
        if len(json.dumps(envelope, ensure_ascii=False)) <= char_limit:
            low = count
        else:
            high = count - 1
    envelope.update(head=body[:low], tail=body[-low:] if low else '')
    content = json.dumps(envelope, ensure_ascii=False)
    return {'content': content, 'evidence_sha256': digest, 'truncated': True}
