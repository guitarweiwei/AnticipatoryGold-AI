> Latest Windows result (2026-10-21): the user accepted the EULA; actual signed MetaEditor 5.0.0.6274 was invoked and FAILED with 1 error / 0 warnings (missing official Include/Trade/Trade.mqh), no successful EX5. Both log parsing and numeric report were verified by real run 39652983425. PowerShell execution is now evidenced. Earlier NOT RUN statements below are retained historical snapshots, superseded only for Windows helper execution and compiler invocation. MT5 backtests/runtime, real providers and trading remain NOT RUN. See tests/windows/CLOUD_COMPILE.md and its evidence aggregate; compilation is still a release blocker. No MQL content or risk parameter changed.

# Actual validation evidence — current Stage 3 and historical runs

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

## Authorized Stage 3 — current frozen source

User authorization: implement proposed items 1–3, preserve important risk parameters and every execution lock. Current implementation is described in STAGE3_IMPLEMENTATION.md; earlier statements about absent source implementations above are historical and superseded by that record. Runtime evidence remains absent.

The main reviewer ran `/workspace/scratch/d1385acbcda2/testenv/bin/python tests/run_checks.py` from the project root; exit **0**. **175 checks passed**:

| Type | Count | What executed |
|---|---:|---|
| MQL5 source regressions | 18 | 10 earlier guard checks plus 8 Stage3 source invariants; no MQL execution |
| Independent Python policy fixtures | 45 | 22 Stage2 risk cases plus 23 abstract journal/fill/cash-ledger cases |
| Macro tests | 15 | CSV2, original source age, calendar expiry, strict input, provenance and atomic publisher fixtures |
| Advisory API tests | 97 | Mocked provider and API1.1/macro2 validation, pre/post review validity and identical canonical observations |

Python compileall and git diff --check passed. One upstream Starlette TestClient/httpx deprecation warning remains. The isolated environment uses Python3.12, FastAPI0.156.4, httpx0.28.1, Pydantic2.14.1, pytest9.1.1 and Starlette1.9.0. Requirements remain ranged, not a locked dependency reproducibility claim.

Independent risk auditor also ran the full175 suite successfully against the frozen source, and separately checked API/CSV field sets, 35 original input declarations and the execution boundaries. Initial source-test harness matching was corrected to anchor actual function definitions rather than if-blocks following a same-named call. Main reviewer strengthened the existing8 invariants with post-close risk ordering, pre-send ledger validation and absence of unchecked single-argument position property reads, then reran the full175 successfully. Source implementation was unchanged by those harness additions.

Frozen MQL source SHA256 (not compiler/output hashes):

- Experts/AnticipatoryGold_AI_v1.mq5: `669f2ab269e6451bbdd32bb0f8bc272bf93b6b5c49ce4edcbd638ef521145e0d`
- Experts/Include/ResearchLifecycle.mqh: `3d11d861a3c6f1402cabf631bf8881bb4c3e3dac5118716bda74e676f29062fd`

Independent source review permits this execution-disabled Draft PR only. API source validity does not authenticate real observations; abstract fault fixtures do not prove the MQL journal or broker history; source checks do not compile it. MetaEditor, PowerShell, MT5, Windows crash/fault/partial-fill tests, actual provider calls, real broker costs and performance/forward results remain **NOT RUN**. A verified prospective-cost bound is still absent, with its unknown gate and independent false veto retained. Do not remove locks to obtain performance data. Remote CI must be verified separately from these local results.
