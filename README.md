> **2026-10-22:** Actual offline native tests **50/50 passed**; production EA and test script compiled with **0 errors / 0 warnings**. Python/source/API checks **188 passed**. Historical backtest plan prepared; performance backtest **NOT RUN**. Trading remains locked. See [native evidence](docs/NATIVE_TEST_RESULTS_20261022.md).

> **2026-10-21 latest:** Genuine signed MetaEditor 5.0.0.6274 compilation PASSED: **0 errors, 0 warnings**, fresh EX5 hash recorded. Authorized offline initialization generated the official standard library; firewall and process exit verified. Backtest/EA execution remain NOT RUN; all trading locks and risk limits remain unchanged. Earlier compilation failures below are historical. See [Windows evidence](tests/windows/CLOUD_COMPILE.md).

# AnticipatoryGold AI v1 — research development, trading blocked

This branch imports the supplied project and six-agent P0 hardening work. **It is not a completed trading system and must not be merged as release-ready.** No profitability or maximum-loss claim is made.

## Current execution status

- The EA refuses initialization outside MT5 Strategy Tester. No demo or live terminal trading is enabled.
- `EntryRiskPolicyApproved()` is hard-coded false, independently blocking both `ProcessEntry` and `OpenPosition`, including in the tester. The current EA can inspect signals but generates **zero new trades**. Approved D1/D2 research source now implements 2×closed-M5-ATR protective stops, stop-distance sizing and a scoped persistent risk latch, but execution evidence and other release gates remain missing.
- Online EA-to-AI integration is an explicit veto stub. The Python advisory API is tested independently; it cannot execute orders.
- All original EA input declarations and numeric defaults are preserved. The user approved the documented 2.0 ATR policy; it is a fixed research rule. No existing numeric risk ceiling was relaxed.
- Real signed MetaEditor 5.0.0.6274 compilation was attempted on Windows: **FAILED, 1 error / 0 warnings**, missing official `Include/Trade/Trade.mqh`. No successful EX5. MT5 Strategy Tester remains **NOT RUN**. See [compiler evidence](tests/windows/CLOUD_COMPILE.md). Static Python checks cannot substitute for compilation.

## Implemented safeguards

Strict advisory API schemas match `docs/API_CONTRACT.json`, correlate request IDs, reject invalid/nonfinite model output, enforce UTC freshness, reject placeholder authentication, prevent model reversal, use bounded provider timeouts and redact audit logs. Failed gates return HOLD or a non-200 response, which future EA integration must veto.

The manual macro publisher validates single-row canonical CSV, explicit UTC timestamps, finite numbers, strict news flags and 15-minute freshness; publication requires a provenance manifest. It does not download live data. The example is intentionally expired and news-blocked.

MQL5 source changes reject below-minimum volume rather than rounding up, enforce initial basket lot caps, check risk before basket exits, restrict account mode, log close failures and remove the invalid position commission property. These remain uncompiled source changes.

## Run available checks

Python 3.12 recommended. From project root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r mac_ai/requirements.txt pytest
.venv/bin/python tests/run_checks.py
```

The Stage 3 suite has 18 MQL5 **source** checks, 45 independent Python policy fixtures (22 Stage 2 + 23 lifecycle/ledger examples), 15 macro tests and 97 mocked API cases (175 total). See docs/VALIDATION_RESULTS.md for actual run status. One upstream Starlette TestClient deprecation warning remains. Tests use no paid model calls. CI uses read-only repository permissions and runs these checks; its remote status must be verified separately.

## Advisory service only

Read `mac_ai/README.md`; configure a private `.env` from `.env.example` with a random shared token of at least 32 characters and your own optional provider key. Do not commit secrets. For isolated local API testing:

```bash
cd mac_ai
uvicorn app:app --host 127.0.0.1 --port 8000
```

Set environment variables using your preferred secure method before starting. No actual provider connectivity or billing was tested here. Cross-machine service access and TLS are not configured by this PR. Do not attach this EA to a trading account expecting it to run.

## Decisions and release blockers

See `docs/DECISIONS_REQUIRED.md`, `docs/DEFECT_REGISTER.md`, `docs/RISK_REVIEW.md` and `docs/AGENT_PLAN.md`. D1/D2 have source implementations, with Windows compilation/runtime still unverified. Durable intents, fill/SL verification, lifecycle accounting and original-source validity now have Stage 3 research implementations. Actual Windows/broker evidence, verified prospective costs and active strict EA/API integration remain blockers. See MQL5/STAGE2.md and docs/STAGE2_RISK_REVIEW.md. The cost gate independently rejects every candidate until verified cost data exists. Do not remove the order lock to obtain performance results.

`tests/windows/` contains compile instructions and an empty evidence template, not evidence of execution. Baseline source strategy semantics are documented in `docs/STRATEGY_SPEC.md`. `docs/CODE_AUDIT.md` is the retained historical import audit.

## Authorized Stage 3 implementation

The user authorized source-validity, order reconciliation and basket accounting work. CSV schema 2 carries original source times/calendar expiry; API 1.1 requires those fields and identical candidate/canonical observations before and after review. Old schemas reject. The EA adds closed OHLC/indicator checks and a pre-send durable intent/consumed-bar journal. Incomplete/partial/restart ambiguity halts without resending. Complete supported deal cash flows, conservative recorded debits and flat-basket archives are implemented in `MQL5/Experts/Include/ResearchLifecycle.mqh`; copy the complete source tree for eventual compilation.

Unknown future fees remain unknown: no broker reserve or zero-cost assumption was invented, and the independent cost veto remains false. Every original EA input and execution lock is unchanged. Source/fixture tests do not establish compilation, MQL execution, broker history completeness or durable storage. See [docs/STAGE3_IMPLEMENTATION.md](docs/STAGE3_IMPLEMENTATION.md), [docs/DEFECT_REGISTER.md](docs/DEFECT_REGISTER.md) and [docs/VALIDATION_RESULTS.md](docs/VALIDATION_RESULTS.md). Earlier six-agent review is retained in `docs/REVALIDATION_20261021.md` as historical context.
