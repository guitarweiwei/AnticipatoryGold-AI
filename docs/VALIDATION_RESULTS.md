# Actual validation evidence — Stage 2 and 2026-10-21 revalidation

Historical Stage 2 run — reviewed integrated implementation source: local commit `03b2a3b` (D1/D2 source implementation plus metadata hardening and tests; subsequent edits are documentation only). Local commit hashes are not GitHub's per-file web-upload commit hashes.

Command from project root: `/tmp/agai-api-venv/bin/python tests/run_checks.py`.

Result: exit 0. Python compileall succeeded; **104 checks passed**: 10 MQL5 source regression checks, 22 independent Python risk-policy fixtures, 10 macro unit tests and 62 mocked API pytest cases. Main and independent risk reviewer both ran the complete suite successfully. One upstream Starlette TestClient/httpx deprecation warning remains.

Observed test environment: Python 3.12.14, FastAPI 0.150.0, httpx 0.28.1, Pydantic 2.14.1, pytest 9.1.1, Starlette 1.9.0. Recreate a local venv and install mac_ai/requirements.txt plus pytest before running tests/run_checks.py. These are observed versions, not a claim that unpinned future installs reproduce the same versions.

The MQL5 checks inspect selected source wiring only. Python risk fixtures are an independent arithmetic/state specification using synthetic account-currency loss slopes and an abstract fault-injected store. Neither executes MQL5, emulates the broker's OrderCalcProfit nor proves actual file durability or execution safety.

Original 35 EA input declarations/defaults were compared with imported baseline and are unchanged. The user explicitly authorized the new fixed 2.0×M5 ATR rule; existing numeric risk ceilings were not relaxed. `git diff --check` passed.

- MetaEditor compilation: NOT RUN; executable not available.
- MT5 Strategy Tester and actual orders: NOT RUN; MT5/Wine unavailable and new entries remain hard-locked.
- PowerShell helper: NOT RUN; pwsh unavailable.
- Actual provider/paid model calls: NOT RUN; model responses mocked.
- Real macro/calendar feed: NOT IMPLEMENTED/NOT RUN.
- Broker future-cost bound, actual-fill/SL verification and pending-order/restart ledger: not completed.
- Performance, out-of-sample, walk-forward and demo-forward evidence: NOT RUN.

The cost gate independently rejects every candidate until verified future-cost data exists. The hard entry lock remains false even in tester. No live/demo connection or automatic merge is authorized. Remote GitHub CI status must be reported from actual remote evidence, separately from these local results.

## 2026-10-21 current-tree revalidation

Started from GitHub development head `08310e53f31e0c19a17c0f37b598456827c95f60`, downloaded through the authenticated browser. The input ZIP was separately retrieved and extracted, but was not uploaded over later fixes. Six agents reviewed strategy, MQL5, advisory API, macro, verification and independent risk.

Command: `testenv/bin/python tests/run_checks.py` from the project root using a temporary Python 3.12 virtual environment (use the absolute path to that environment, or `.venv/bin/python` after creating your own). Exit **0**: compileall succeeded; **112 checks passed** — 10 MQL5 source checks, 22 Python policy fixtures, 10 macro cases and 70 mocked API cases. This includes eight new post-provider macro-change regression cases. Observed FastAPI 0.156.4, httpx 0.28.1, Pydantic 2.14.1, pytest 9.1.1 and Starlette 1.9.0. One upstream TestClient deprecation warning remains.

Independent risk reviewer reran the eight new cases (8 passed) and complete API suite (70 passed). With the downloaded pre-fix app and new cases in a disposable tree, seven mutation cases failed as expected while unchanged republication passed (7 failed / 1 passed); no working-tree file was replaced during this comparison. This establishes the regression, not broker behavior.

All 35 EA input declarations remain byte-for-byte equal to the input ZIP. MQL5 source and execution locks were unchanged. Remaining source-validity, order reconciliation and Windows gates are recorded in REVALIDATION_20261021.md. MetaEditor, PowerShell, MT5 backtests, real model calls, live/demo trading and performance validation remain **NOT RUN**. Only Python/static CI exists; no Windows compiler workflow is present.
