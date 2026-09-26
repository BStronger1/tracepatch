# Re-evaluate an existing patch without calling the model

`scripts/reverify-repo.py` applies a selected verifier to a saved real-repository
candidate in a fresh network-disabled Docker container. It makes no model API
requests and does not change the original result or infer a new submission.

Use the [repository setup](REAL_REPOSITORY.md) first. You need an existing local
`run-repo.py` batch containing its exported `candidate` directory. Raw runs are
ignored by Git and are not included in a fresh clone.

```powershell
python scripts/reverify-repo.py --batch runs/repo-cookie-out512-b --task requests-2527-v2 --output reports/my-cookie-v2-recheck.json
```

Replace the batch with your own run. The command checks that repository, base
commit and Docker image match the evaluation task before starting a container.
It rejects linked candidate entries, existing output files, and report paths
inside the original batch. Choose a new output filename each time.

The JSON report contains the original completion state, new verifier result,
re-evaluated completion state, verifier/task hashes, original result and patch
hashes, and a hash of the actual candidate file tree before verification.
The source-tree hash identifies the candidate currently present on disk; it does
not prove that nobody has edited that directory since the original run.

A patch that passes a new verifier remains **unsubmitted** if the original agent
never submitted it. A previously submitted patch may fail a stronger verifier.
These are additional evaluations, not revisions to historical scores.

Example from this project: [v2 recheck of the saved 512-b patch](../reports/cookie-v2-reverify-example-001.json).
It passes ten contracts but retains its original unsubmitted state. Historical
v1 results and the newer development study remain separately labelled.

Click is also supported via its registered `src/click` layout. For a local Click
run, select `--task click-1687`; the verifier imports that archived candidate's
`src` directory rather than an installed package. Example evidence:
[Click re-evaluation](../reports/click-reverify-001.json).
