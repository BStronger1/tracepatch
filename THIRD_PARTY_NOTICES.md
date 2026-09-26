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

The optional real-repository experiment separately downloads Requests from
https://github.com/psf/requests at frozen commits listed in tasks/repos/requests-2317/task.json.
Requests is Apache-2.0 licensed. Its source archives and reference solution remain
local in ignored runs/ directories and are not redistributed in TracePatch.
The custom offline verifier uses Requests' public adapter interface; it is not the
upstream test suite or the official SWE-bench harness.

The optional Click experiment separately downloads https://github.com/pallets/click
at the frozen base and reference commits in tasks/repos/click-1687/task.json.
Click is BSD-3-Clause licensed. Retain its LICENSE.rst and copyright notices with
any redistributed upstream source. TracePatch does not redistribute those source
archives or the reference solution; they remain in ignored local runs/ directories.
The custom verifier uses Click's public APIs and CliRunner, and evaluates a subset
of historical PR behavior rather than the complete upstream test suite.
