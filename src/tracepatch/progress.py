"""Source-change observations, independent of command wording or model claims."""
import hashlib
import json
import subprocess
from pathlib import PurePosixPath


# Run with python -I inside the existing offline container; never import project code.
SNAPSHOT_PROGRAM = '''import hashlib,json,pathlib,sys
root=pathlib.Path('/workspace')
result={}
for name in json.loads(sys.argv[1]):
    path=root
    for part in pathlib.PurePosixPath(name).parts:
        path=path/part
        if path.is_symlink():
            raise ValueError('Linked source')
    if not path.exists():
        result[name]=None
    elif not path.is_file() or path.stat().st_size>2000000:
        raise ValueError('Unsupported source')
    else:
        result[name]=hashlib.sha256(path.read_bytes()).hexdigest()
print(json.dumps(result,sort_keys=True))
'''


def validate_snapshot(snapshot, paths):
    if not isinstance(snapshot, dict) or set(snapshot) != set(paths):
        raise ValueError('Incomplete source snapshot')
    for name, digest in snapshot.items():
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name or path.suffix != '.py':
            raise ValueError('Invalid source path')
        if digest is not None and (not isinstance(digest, str) or len(digest) != 64
                                   or any(c not in '0123456789abcdef' for c in digest)):
            raise ValueError('Invalid source digest')
    return dict(snapshot)


def snapshot_digest(snapshot):
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


def docker_snapshot(executable, container_id, paths):
    validate_snapshot(dict.fromkeys(paths), paths)
    result = subprocess.run([executable, 'exec', container_id, 'python', '-I', '-c',
                             SNAPSHOT_PROGRAM, json.dumps(list(paths))],
                            capture_output=True, text=True, timeout=10, check=True)
    return validate_snapshot(json.loads(result.stdout), paths)


class ObservedEnvironment:
    """Same action behavior; save observations even when submission raises."""
    def __init__(self, environment, monitor, snapshot, output, memory=None):
        self.environment = environment
        self.monitor = monitor
        self.snapshot = snapshot
        self.output = output
        self.memory = memory
        self.save()

    def __getattr__(self, name):
        return getattr(self.environment, name)

    def save(self):
        self.output.write_text(json.dumps(self.monitor.report(), indent=2), encoding='utf-8')

    def execute(self, action, *args, **kwargs):
        result = None
        before = self.monitor.previous
        try:
            result = self.environment.execute(action, *args, **kwargs)
            return result
        finally:
            try:
                snapshot, error = self.snapshot(), None
            except Exception as failure:
                snapshot, error = None, type(failure).__name__
            self.monitor.observe(snapshot, returncode=result.get('returncode') if result else None,
                                 command=action.get('command', ''), error=error)
            self.save()
            if self.memory is not None:
                self.memory.observe(len(self.monitor.events), action.get('command', ''),
                                    result, before, snapshot)


class ProgressMonitor:
    """An unchanged streak is a review signal, never a success/stall verdict."""
    def __init__(self, initial, *, threshold=6):
        if not initial or type(threshold) is not int or threshold < 2:
            raise ValueError('Nonempty initial snapshot and threshold >= 2 required')
        self.initial = validate_snapshot(initial, initial)
        self.previous = dict(self.initial)
        self.threshold = threshold
        self.unchanged = 0
        self.events = []

    def observe(self, snapshot, *, returncode=None, command='', error=None):
        if error is not None or snapshot is None:
            current = None
        else:
            current = validate_snapshot(snapshot, self.initial)
        event = {'action': len(self.events) + 1,
                 'command_sha256': hashlib.sha256(command.encode()).hexdigest(),
                 'tool_returncode': returncode if type(returncode) is int else None,
                 'test_passed': None, 'observation_error': error,
                 'changed_paths': None, 'net_changed_paths': None,
                 'snapshot_sha256': None, 'signal': None}
        if current is None:
            self.unchanged = 0
            event['state'] = 'unknown'
        else:
            event['snapshot_sha256'] = snapshot_digest(current)
            event['net_changed_paths'] = sorted(k for k in current if current[k] != self.initial[k])
            if self.previous is None:
                self.unchanged = 0
                event['state'] = 'reanchored'
            else:
                changed = sorted(k for k in current if current[k] != self.previous[k])
                event['changed_paths'] = changed
                self.unchanged = 0 if changed else self.unchanged + 1
                event['state'] = 'changed' if changed else 'unchanged'
                if self.unchanged and self.unchanged % self.threshold == 0:
                    event['signal'] = 'unchanged_source_review'
        event['unchanged_streak'] = self.unchanged
        self.previous = current
        self.events.append(event)
        return event

    def notice(self):
        if not self.events or not self.events[-1]['signal']:
            return None
        event = self.events[-1]
        return (f"Harness progress observation: the last {event['unchanged_streak']} executed actions "
                f"left the tracked existing Python files unchanged between action boundaries. "
                f"{len(event['net_changed_paths'])} tracked files currently differ from the starting source. "
                "This does not prove a stall; inspection and tests can be useful without edits. "
                "Review your current hypothesis. If a fix is still needed, choose one relevant location, "
                "check the actual code before editing, make a focused change and run the visible reproducer. "
                "If already fixed, check and submit according to the submission protocol. "
                "Do not modify files merely to reset this signal. Tool exit zero is not independent verification.")

    def report(self):
        return {'schema_version': 'tracepatch-progress-0.1', 'threshold': self.threshold,
                'initial': self.initial, 'initial_sha256': snapshot_digest(self.initial),
                'events': self.events,
                'summary': {'actions': len(self.events),
                            'changed_actions': sum(e['state'] == 'changed' for e in self.events),
                            'unknown_actions': sum(e['state'] == 'unknown' for e in self.events),
                            'review_signals': sum(e['signal'] is not None for e in self.events),
                            'max_unchanged_streak': max((e['unchanged_streak'] for e in self.events), default=0)},
                'limitations': ['Source changes do not establish correctness or useful progress.',
                    'Only existing exported Python files are tracked, at action boundaries.',
                    'Temporary edits reverted within an action are invisible.',
                    'Tool return codes are not trusted test results; test_passed remains unknown.',
                    'Observations inside an agent-writable container are not adversarially tamper-proof.']}
