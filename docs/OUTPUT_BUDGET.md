# Output-budget study: fixed plan

The previous Cookie task stopped after seven truncated responses and exported no
patch. This motivates testing a larger output allowance; it does not establish
that output allowance is the only obstacle or that increasing it will fix the task.

## Plan frozen before new paid calls

- Task: `requests-2527`, unchanged base, task text, visible reproducer and six
  independent contracts from the preceding study. It is a development task.
- Model: `qwen3.8-flash`, native bash tool calls, `recovery-budget`, `recent-turns`.
- Compare 512 versus 1024 maximum output tokens, two fresh runs each.
- Order: 512 / 1024 / 1024 / 512. Adjacent runs form two pairs with reversed order.
  This balances order across the two pairs but is not a randomized large trial.
- Each run has 24 maximum calls, a 24,000-byte request limit, 300-second agent
  wall-time limit and the same Docker image. No automatic provider retries.
- Same system/task prompts and same error-feedback wording across both arms.
  Feedback says "configured output limit" rather than stating a different number.
  Consequently old runs with different feedback/runtime are historical context,
  not controls in this experiment.
- Complete all four planned runs regardless of outcomes. Do not tune prompts,
  tests, limits or the protocol after observing outcomes. Infrastructure failures
  stay recorded; no replacement runs silently enter the sample.

Primary result: independent six-contract verification **and** normal submission.
Also report patch verification separately, truncation count, calls, reported token
usage, estimated cost, context omissions and wall time. The larger allowance also
permits greater per-run output and cost; this is not an equal-token-budget study.

The study plan JSON records task and runtime hashes plus batch order. Pairwise
comparison requires equal task hashes, source/image, prompts and implementation
snapshots; `--intervention output-budget` alone allows the output limit to differ
and requires policy/context settings to match. Provider-side model changes or
stochasticity cannot be fully controlled by this local harness.

## Run locally

Follow [setup](REAL_REPOSITORY.md) and [task instructions](NEW_REQUESTS_TASKS.md).
Use distinct new batch IDs and your own ignored local API configuration:

```powershell
python scripts/run-repo.py --task requests-2527 --batch repo-cookie-512-local --action-protocol native --context-policy recent-turns --visible-reproducer --max-calls 24 --max-output-tokens 512
python scripts/run-repo.py --task requests-2527 --batch repo-cookie-1024-local --action-protocol native --context-policy recent-turns --visible-reproducer --max-calls 24 --max-output-tokens 1024
python scripts/compare-runs.py runs/repo-cookie-512-local runs/repo-cookie-1024-local --intervention output-budget --output reports/output-budget-local.json
```

This changes a limit, not the truncation gate: any `finish_reason=length` response
is still rejected and never executed. A provider reporting output beyond the
requested limit stops the run. Default remains 512. Only 512 and 1024 are currently
supported and recorded in each request as well as the run manifest.
