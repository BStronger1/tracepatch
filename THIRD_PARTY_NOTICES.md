# Upstream attribution

The experiment runner imports mini-swe-agent's DefaultAgent and DockerEnvironment.
These components are not implemented by TracePatch. The upstream source is fetched
separately into `../vendor/mini-swe-agent` and is not included in this repository.

- Source: https://github.com/SWE-agent/mini-swe-agent
- Frozen revision: `04d809ceab9df28f9adaed044884180159172930`
- License: MIT, copyright (c) 2025 Kilian A. Lieret and Carlos E. Jimenez;
  retain its `LICENSE.md` with any redistributed upstream source.

TracePatch implements the diagnostics, action compatibility parsing, targeted
recovery feedback, reservation ledger, development tasks and comparison runner.
Harbor integration and standard benchmark scores are not implemented.
