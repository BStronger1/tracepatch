"""Exact, syntax-checked edits to an allowlisted existing Python source file."""
import hashlib
import inspect
import json
import subprocess

EDIT_INSTRUCTION = (' An additional replace_text(path, old, new) tool edits one existing exported Python source file. '
    'Use a relative source path and exact old text copied from the checkout. The old text must occur exactly once. '
    'The tool rejects ambiguous, missing, no-op or syntactically invalid edits and reports whether the file was actually changed. '
    'Prefer it for focused source replacements; bash remains available. An applied edit is not a passing test or submission.')


def edit_tool_prompt(system):
    return system + EDIT_INSTRUCTION


def replace_source(root, allowed, edit):
    # This function is also shipped verbatim to isolated Python in the container.
    import hashlib
    import os
    import pathlib
    import tempfile
    digest = lambda raw: hashlib.sha256(raw).hexdigest()
    path, old, new = edit['path'], edit['old'], edit['new']
    result = {'status': 'path_not_allowed', 'path': path, 'file_before_sha256': None,
              'file_after_sha256': None, 'old_sha256': digest(old.encode()), 'new_sha256': digest(new.encode()),
              'matches': None, 'acceptance_verified': None}
    relative = pathlib.PurePosixPath(path)
    if (path not in allowed or relative.as_posix() != path or relative.is_absolute() or
            '..' in relative.parts or '\\' in path or relative.suffix != '.py'):
        return result
    target = pathlib.Path(root)
    for part in relative.parts:
        target /= part
        if target.is_symlink():
            result['status'] = 'linked_source_rejected'
            return result
    info = target.stat()
    if not target.is_file() or info.st_nlink != 1 or info.st_size > 2000000:
        result['status'] = 'unsupported_source'
        return result
    raw = target.read_bytes()
    text = raw.decode('utf-8')
    result['file_before_sha256'] = result['file_after_sha256'] = digest(raw)
    first = text.find(old)
    second = text.find(old, first + 1) if first >= 0 else -1
    result['matches'] = 0 if first < 0 else (2 if second >= 0 else 1)
    if first < 0:
        result['status'] = 'old_text_not_found'
        return result
    if second >= 0:
        result['status'] = 'ambiguous_match'
        return result
    candidate = text[:first] + new + text[first + len(old):]
    if candidate == text:
        result['status'] = 'no_change'
        return result
    try:
        compile(candidate, path, 'exec')  # Compile only; never import or execute it.
    except (SyntaxError, ValueError, OverflowError):
        result['status'] = 'syntax_error'
        return result
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
            temporary = pathlib.Path(handle.name)
            handle.write(candidate.encode('utf-8'))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, info.st_mode & 0o777)
        if target.is_symlink() or target.stat().st_ino != info.st_ino or target.read_bytes() != raw:
            result['status'] = 'source_changed_during_edit'
            return result
        os.replace(temporary, target)
        result.update(status='applied', file_after_sha256=digest(target.read_bytes()))
        if result['file_after_sha256'] != digest(candidate.encode('utf-8')):
            result['status'] = 'write_verification_failed'
        return result
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def validate_edit(edit):
    if not isinstance(edit, dict) or set(edit) != {'path', 'old', 'new'}:
        raise ValueError('invalid_edit_schema')
    if not all(isinstance(edit[k], str) and '\x00' not in edit[k] for k in edit):
        raise ValueError('invalid_edit_schema')
    if not edit['path'].strip() or not edit['old'] or sum(len(v.encode()) for v in edit.values()) > 16000:
        raise ValueError('invalid_edit_schema')
    return edit


def docker_replace(executable, container_id, paths, edit):
    validate_edit(edit)
    program = inspect.getsource(replace_source) + '\nimport json,sys\nprint(json.dumps(replace_source("/workspace", *json.loads(sys.argv[1]))))'
    result = subprocess.run([executable, 'exec', container_id, 'python', '-I', '-c', program,
                             json.dumps([list(paths), edit])], capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=15, check=True)
    return json.loads(result.stdout)


class EditingEnvironment:
    def __init__(self, environment, execute_edit, output_dir):
        self.environment, self.execute_edit, self.output_dir = environment, execute_edit, output_dir
        self.output_dir.mkdir(exist_ok=False)
        self.records = []

    def __getattr__(self, name):
        return getattr(self.environment, name)

    def execute(self, action, *args, **kwargs):
        if action.get('tool') != 'replace_text':
            return self.environment.execute(action, *args, **kwargs)
        edit = validate_edit(action['edit'])
        try:
            result = self.execute_edit(edit)
        except Exception as error:
            result = {'status': 'unknown', 'error_type': type(error).__name__, 'acceptance_verified': None}
        record = {'provenance': 'supervised-source-edit', **result,
                  'edit_sha256': hashlib.sha256(json.dumps(edit, sort_keys=True).encode()).hexdigest()}
        self.records.append(record)
        number = len(self.records)
        (self.output_dir / f'{number:03d}.input.json').write_text(json.dumps(edit), encoding='utf-8')
        (self.output_dir / f'{number:03d}.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        return dict(record, output='Edit persistence only; not test success or submission.')
