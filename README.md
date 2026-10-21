# AnticipatoryGold AI v1 — research development, trading blocked

This branch imports the supplied project and six-agent P0 hardening work. **It is not a completed trading system and must not be merged as release-ready.** No profitability or maximum-loss claim is made.

## Current execution status

- The EA refuses initialization outside MT5 Strategy Tester. No demo or live terminal trading is enabled.
- `EntryRiskPolicyApproved()` is hard-coded false, independently blocking both `ProcessEntry` and `OpenPosition`, including in the tester. The current EA can inspect signals but generates **zero new trades**. Approved D1/D2 research source now implements 2×closed-M5-ATR protective stops, stop-distance sizing and a scoped persistent risk latch, but execution evidence and other release gates remain missing.
- Online EA-to-AI integration is an explicit veto stub. The Python advisory API is tested independently; it cannot execute orders.
- All original EA input declarations and numeric defaults are preserved. The user approved the documented 2.0 ATR policy; it is a fixed research rule. No existing numeric risk ceiling was relaxed.
- MetaEditor compilation and MT5 Strategy Tester execution are **NOT RUN**. Static Python checks cannot substitute for them.

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

Stage 2 adds 22 independent Python risk-policy fixtures and four source linkage checks. The complete suite has 10 MQL5 **source** safety checks, 22 Python policy fixtures, 10 macro tests and 70 mocked API tests (112 total). See docs/VALIDATION_RESULTS.md for actual run status. One upstream Starlette TestClient deprecation warning remains. Tests use no paid model calls. CI uses read-only repository permissions and runs these checks; its remote status must be verified separately.

## Advisory service only

Read `mac_ai/README.md`; configure a private `.env` from `.env.example` with a random shared token of at least 32 characters and your own optional provider key. Do not commit secrets. For isolated local API testing:

```bash
cd mac_ai
uvicorn app:app --host 127.0.0.1 --port 8000
```

Set environment variables using your preferred secure method before starting. No actual provider connectivity or billing was tested here. Cross-machine service access and TLS are not configured by this PR. Do not attach this EA to a trading account expecting it to run.

## Decisions and release blockers

See `docs/DECISIONS_REQUIRED.md`, `docs/DEFECT_REGISTER.md`, `docs/RISK_REVIEW.md` and `docs/AGENT_PLAN.md`. D1/D2 have source implementations, with Windows compilation/runtime still unverified. Prospective broker-cost bounds, actual-fill/SL verification, durable pending-order/restart reconciliation, strict active EA/API integration and real Windows evidence remain blockers. See MQL5/STAGE2.md and docs/STAGE2_RISK_REVIEW.md. The cost gate independently rejects every candidate until verified cost data exists. Do not remove the order lock to obtain performance results.

`tests/windows/` contains compile instructions and an empty evidence template, not evidence of execution. Baseline source strategy semantics are documented in `docs/STRATEGY_SPEC.md`. `docs/CODE_AUDIT.md` is the retained historical import audit.

## 2026-10-21 revalidation

The API now vetoes canonical macro observations changed or lost during model review. Six-agent revalidation and unresolved source-validity, signal-data and Windows gates are recorded in [docs/REVALIDATION_20261021.md](docs/REVALIDATION_20261021.md). All execution locks and original risk inputs remain unchanged.
