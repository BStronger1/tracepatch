# Second repository: Click repeated defaults

TracePatch now registers two repository layouts explicitly:

| Repository | Local vendor directory | Exported package | Import directory |
| --- | --- | --- | --- |
| Requests | `../vendor/requests` | `requests/` | repository root |
| Click | `../vendor/click` | `src/click/` | `src/` |

The Click task comes from [upstream PR 1687](https://github.com/pallets/click/pull/1687).
The pinned base is `b631e5a5794369f03d57719a446a65e423366f36`, and the reference is
`c067af761a70a6cbb91fa49083a41511207297da`. That PR has broader changes than this
task: our task evaluates the repeated-default/type-conversion behavior, not every
change in the PR or the full upstream test suite.

Ten custom contracts cover scalar/list defaults, composite inference, command-line
overrides for scalar and composite values, missing/optional values, explicit types,
numeric input errors, default_map and environment precedence. The initial broken
revision fails; the reference passes all ten. A minimal visible reproducer exposes
only the scalar-default symptom. The independent verifier remains outside the
agent container. Task authoring inspected upstream changes; this is not a blind
held-out benchmark and training-data exposure to this old public code is possible.

## Execution and evidence

The model receives a full clean source archive without Git history or the future
reference revision. `PYTHONPATH=/workspace/src` is set for ordinary agent Python
commands, while independent verification explicitly adds that path under `python -I`.
The image is the same pinned Python 3.9 image used for Requests. No network, pytest
installation, remote execution service or local model GPU is required.

Only existing Python files under the registered source directory are reconstructed
over a clean base. Agent-created source files, modified upstream tests and non-Python
files are not included in the candidate. Missing allowed files and linked exports
are rejected. These restrictions are part of the evaluation scope, not a general
patch-application service for every possible issue.

Both the source layout and its implementation snapshot are stored and checked by
the comparison tool. Re-evaluation also uses the registered import layout. The
existing Requests v2 preflight is repeated to check compatibility.

## Frozen development run plan

Two clean repeats with `qwen3.8-flash`, `recovery-submit`, native tool calling,
recent-turns, the visible reproducer, 1024 output tokens, 24 maximum calls,
24000 request bytes and the existing 300-second agent wall-time limit.
No task, verifier or prompt edits after starting; no outcome-dependent retry.
Both successes and failures will be reported. This extends execution to a second
repository, but one new problem cannot establish general cross-repository quality.

## Reproduce

Follow [runtime setup](REPRODUCE.md) first, then:

```powershell
git clone --no-checkout https://github.com/pallets/click.git ../vendor/click
docker pull python@sha256:2d97f6910b16bd338d3060f261f53f144965f755599aab1acda1e13cf1731b1b
python scripts/run-repo.py --task click-1687 --batch repo-click-check-local --visible-reproducer --verify-only
python scripts/run-repo.py --task click-1687 --batch repo-click-local-a --policy recovery-submit --action-protocol native --context-policy recent-turns --visible-reproducer --max-calls 24 --max-output-tokens 1024
python scripts/run-repo.py --task click-1687 --batch repo-click-local-b --policy recovery-submit --action-protocol native --context-policy recent-turns --visible-reproducer --max-calls 24 --max-output-tokens 1024
python scripts/compare-runs.py runs/repo-click-local-a runs/repo-click-local-b --output reports/my-click-repeats.json
```

Use fresh batch IDs. `--verify-only` is offline; the next two runs use your ignored
local API key and the shared reservation ledger. Identical configurations are
repeats, not a treatment-versus-control comparison.
