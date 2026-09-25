# Versioned evaluation and submission guidance

Cookie evaluation v1 and its historical results remain unchanged. The new task
`requests-2527-v2` is a **revision of the same development problem**, not a fourth
independent issue. It retains v1's six contracts and minimal visible reproducer,
and adds four contracts:

- preserve standard CookieJar policy settings;
- preserve the rfc2109 flag on update;
- preserve a CookieJar subclass with required constructor arguments and state;
- preserve cookie flags and metadata in a prepared-request copy.

The added assertions were motivated by prior candidate inspection. The v2 task
description explicitly states these behavioral requirements without supplying
the verifier or reference implementation. This is development informed by known
failures, not held-out evaluation. The upstream reference must pass all ten tests
and the broken revision must fail before any new model calls.

## Submission protocol finding

Pinned mini-swe-agent accepts submission only when the first non-whitespace
output line is the exact marker and the command exits zero. `tests && echo MARKER`
may fail to signal completion when tests print output first. The prior final-call
guidance omitted this important constraint. A historical candidate also printed
the marker after an actual test-import error; its failure cannot be attributed
solely to marker placement or retroactively relabelled as successful submission.

New opt-in `recovery-submit` changes the last three calls' guidance: after passing
checks, use a separate submission call; if testing and submitting in the same
call, capture both output streams, print the marker first only after success, and
show the log and exit nonzero on failure. The upstream recognizer is unchanged.
No harness code submits on the model's behalf. Old `recovery-budget` behavior is
retained so historical experiments can be distinguished from the new policy.

Five deterministic Docker checks exercise noisy success, a separate marker,
captured success, captured failure and nonzero exit after a marker. These check
the protocol, not whether a code fix is correct. See
[protocol evidence](../reports/submission-protocol-001.json).

## Prospective development check

After preflight and retrospective re-evaluation of all four output-study patches,
freeze two new runs using task v2, `recovery-submit`, native tools, recent-turns,
the unchanged visible reproducer, 1024 output tokens and a 24-call maximum.
Both runs start from clean base source; no previous candidate is supplied.
No outcome-dependent retry, test edits or policy changes during the two runs.

Task requirements, verifier and submission guidance changed relative to the
earlier study. These two runs test the combined revised setup. They do **not**
isolate the causal effect of the new submission policy. A same-task policy
comparison would be a separate future experiment.

Primary outcome: all ten independent contracts pass AND normal submission.
Preserve failed and unsubmitted candidates, costs, truncations and source hashes.
Default policy and output limit remain unchanged in the runner.

```powershell
python scripts/run-repo.py --task requests-2527-v2 --batch repo-cookie-v2-check-local --visible-reproducer --verify-only
python scripts/run-repo.py --task requests-2527-v2 --batch repo-cookie-v2-local-a --policy recovery-submit --action-protocol native --context-policy recent-turns --visible-reproducer --max-calls 24 --max-output-tokens 1024
python scripts/run-repo.py --task requests-2527-v2 --batch repo-cookie-v2-local-b --policy recovery-submit --action-protocol native --context-policy recent-turns --visible-reproducer --max-calls 24 --max-output-tokens 1024
```

See the existing [setup](REAL_REPOSITORY.md). Use fresh batch IDs and a local API
key. Independent tests and reference revisions are never copied into the agent
container. All ten contracts still represent limited custom coverage, not the
complete upstream suite or a standard benchmark score.
