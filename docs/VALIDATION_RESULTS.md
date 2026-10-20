# Actual validation evidence — Stage 2

Reviewed integrated implementation source: local commit `03b2a3b` (D1/D2 source implementation plus metadata hardening and tests; subsequent edits are documentation only). Local commit hashes are not GitHub's per-file web-upload commit hashes.

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
