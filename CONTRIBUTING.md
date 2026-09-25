# Contributing

Run offline checks with Python 3.12+, setting `PYTHONPATH=src`, then
`python -m unittest discover -s tests -v`. Offline checks need no model key or Docker.

Useful contributions include reproductions of rejected-action failures, additional
trajectory formats, and independently specified multi-file tasks. State whether
cases are synthetic, observed on a development task, or held out from tuning.
Never upload API keys, `.env`, private repositories, or unreviewed raw trajectories.

Recovery must never execute an incomplete response. A clean agent submission does
not prove a correct patch: report independent verification separately. Keep unknown
request costs unknown; do not convert missing usage into zero cost.

For paid experiments preserve model, task hashes, prompts, dependency revisions,
limits, and implementation snapshots. Retain failures and disclose small samples.
