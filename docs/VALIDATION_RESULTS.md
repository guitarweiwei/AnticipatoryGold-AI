# Actual validation evidence

Integrated local source at local commit 24ed8e6 (before status/documentation-only edits).

Command from project root: `/tmp/agai-api-venv/bin/python tests/run_checks.py`

Result: exit 0. Python compileall succeeded. 6 MQL5 source safety unittest checks passed; 10 macro unittest cases passed; 62 mocked API pytest cases passed. One Starlette TestClient/httpx deprecation warning was emitted. The private temporary venv path identifies this run; use `.venv/bin/python tests/run_checks.py` after installing requirements to reproduce elsewhere.

The static MQL5 checks verify source guard patterns; they do not execute MQL5 or prove compilation, order behavior, stop arithmetic, safety under broker failure or profitability.

- MetaEditor compilation: NOT RUN.
- PowerShell compile helper: NOT RUN.
- MT5 Strategy Tester: NOT RUN. Current source intentionally blocks every new order, even in tester.
- Actual online model/provider connectivity: NOT RUN; all model HTTP responses mocked.
- Real-time macro/calendar integration: NOT IMPLEMENTED/NOT RUN.
- Out-of-sample, walk-forward, demo forward and performance metrics: NOT RUN.
- Remote GitHub CI: assess its actual status separately; local passing tests do not imply remote CI passed.

No account credentials, trading account connection, live order, paid model call or auto-merge was used.
