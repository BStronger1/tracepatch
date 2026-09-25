"""Audit Git-visible publication files without printing credential contents."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
git = ['git', '-c', f'safe.directory={ROOT.as_posix()}', '-C', str(ROOT)]
names = subprocess.check_output(git + ['ls-files', '--cached', '--others', '--exclude-standard', '-z']).decode().split('\0')
problems = []
count = 0
for name in sorted(set(filter(None, names))):
    path = ROOT / name
    if not path.is_file():
        continue
    count += 1
    if (set(path.relative_to(ROOT).parts) & {'runs', 'artifacts', '.venv', '__pycache__'}
            or path.name.startswith('.env') and path.name != '.env.example'):
        problems.append((name, 'private path'))
        continue
    data = path.read_bytes()
    if re.search(rb'(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----)', data):
        problems.append((name, 'credential-shaped value'))
if problems:
    for name, reason in problems:
        print(f'FAIL: {name}: {reason}')
    raise SystemExit(1)
print(f'PASS: {count} Git-visible files; no excluded private paths or recognized credential patterns. Heuristic check only.')
