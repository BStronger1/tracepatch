# Reproduce development experiments

Offline analysis needs Python 3.12+ only. Paid experiments currently target Windows
with Docker Desktop and a separate mini-swe-agent checkout. CI covers offline
tests on Windows and Linux; local validation has only run on Windows.

From the directory containing tracepatch:

```powershell
git clone https://github.com/SWE-agent/mini-swe-agent.git vendor/mini-swe-agent
git -C vendor/mini-swe-agent checkout 04d809ceab9df28f9adaed044884180159172930
cd tracepatch
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-smoke.lock
```

Start Docker Desktop. Pull the image digest pinned in scripts/run-dev.py.
Copy .env.example to .env and set your key locally. The runner reads the key from
.env; endpoint, model, prices and budget come from configs/model.json. Other .env
settings are informational for now. Direct HTTPS is used without system proxies;
redirects are disabled. DMXAPI is tested; other compatible providers are untested.

```powershell
.\.venv\Scripts\python.exe scripts/run-dev.py --batch dev-check-local --verify-only
.\.venv\Scripts\python.exe scripts/run-dev.py --batch dev-control-local --policy baseline
.\.venv\Scripts\python.exe scripts/run-dev.py --batch dev-recovery-local --policy recovery
.\.venv\Scripts\python.exe scripts/compare-runs.py runs/dev-control-local runs/dev-recovery-local --output reports/local-comparison.json
```

Use new batch IDs. Preflight verifies every broken fixture fails and its reference
implementation passes before paid calls. Both arms allow 8 requests per task and
512 output tokens per request. Review prices and reservations before changing limits.
Each attempted call reserves 0.1 CNY, retained even on failure; this is not billing.
A fresh ledger conservatively reserves 1.2 CNY for the original study's historical
allowance; this default also applies to fresh clones.

runs/ stores raw evidence and snapshots, artifacts/ stores the ledger; both are
ignored by Git. Docker has no network and receives only task files. Verification
runs separately with reference tests. This is development isolation, not a hardened
adversarial submission service. Legacy run-smoke.py and probe-api.py preserve early
experiments; use run-dev.py for further paid work to retain shared ledger coverage.
