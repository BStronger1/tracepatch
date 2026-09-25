# Two additional Requests tasks

This study adds distinct historical behaviors within **one repository**, not a
cross-repository benchmark. Tasks and custom independent tests were prepared
before model runs. We inspected upstream fixes to validate the tasks; the model
receives only the issue description, base source archive and a minimal visible
reproducer. Future commits, Git history and the independent verifier stay outside
its container. Historical public code may be present in model training data.

| Task | Provenance | Independent contracts |
| --- | --- | --- |
| requests-2504 | [Issue 2503](https://github.com/psf/requests/issues/2503), [PR 2504](https://github.com/psf/requests/pull/2504) | Custom options, multiple hops, standard options, disabled redirects, POST 302 conversion, POST 307 body preservation |
| requests-2527 | [Issue 2527](https://github.com/psf/requests/issues/2527), [fix](https://github.com/psf/requests/commit/36093e69c70b9b24dd1e007befa35ad891313f51) | Standard CookieJar, independent Cookie objects for both jar types, update isolation, scope/request fields, empty/absent jars |

Each has six test methods. The Cookie task requires behavior spanning prepared
requests and cookie updates; a fix for the missing `copy` method alone is not
sufficient. No live HTTP service is used. Both tasks use the pinned Python 3.9
image already used by the original Requests task.

## Preflight and exclusions

- Redirect task: broken revision has four test failures; reference passes all six.
- Cookie task: broken revision has three failures and two errors; reference passes
  all six. Both visible reproducers fail on the base and pass on the reference.
- The first redirect preflight exposed a missing `release_conn` method in our
  in-memory transport. Both base and reference errored. The fixture was corrected
  before any model call; the failed preflight remains in local evidence.
- Ordered-parameter PR 2706 was inspected but excluded before model evaluation:
  modern Python dictionary ordering can mask its original failure. No result is
  counted for it.

## Frozen run policy

One fresh run per task, no outcome-dependent retry. Both use `qwen3.8-flash`,
native bash function calls, `recovery-budget`, `recent-turns`, a visible reproducer,
24-call maximum, 512 output tokens and a 24,000-byte request limit. No prompt or
verifier changes are made after observing a model result. The two runs measure
coverage under this configuration; they are not a comparison between policies.

The runner archives base/reference commits, hashes task/reproducer/verifier files,
and snapshots runtime modules. Source exports are independently checked in a new
container. Passing these contracts does not establish full upstream compatibility.

## Reproduce

Follow [real repository setup](REAL_REPOSITORY.md) and use a fresh batch ID:

```powershell
.\.venv\Scripts\python.exe scripts/run-repo.py --task requests-2504 --batch repo-redirect-check-local --visible-reproducer --verify-only
.\.venv\Scripts\python.exe scripts/run-repo.py --task requests-2527 --batch repo-cookie-check-local --visible-reproducer --verify-only
.\.venv\Scripts\python.exe scripts/run-repo.py --task requests-2504 --batch repo-redirect-native-local --action-protocol native --context-policy recent-turns --visible-reproducer --max-calls 24
.\.venv\Scripts\python.exe scripts/run-repo.py --task requests-2527 --batch repo-cookie-native-local --action-protocol native --context-policy recent-turns --visible-reproducer --max-calls 24
```

The first two commands are offline checks. The last two call the paid API using
your local ignored `.env`. Each attempted request reserves 0.1 CNY before network
access, including failures. Reservations are planning limits, not actual charges.
