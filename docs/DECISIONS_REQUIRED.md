# Risk decisions — D1/D2 implementation authorized, execution still locked

The user instructed “直接实施下一阶段” after reviewing the proposed 2×ATR stop and persistent halt policy on 2026-10-20 (Europe/London). This authorizes implementation of D1/D2 below. It does not authorize unlocking execution, live trading, merging or claiming unrun validation. Original numeric EA inputs remain unchanged; the approved 2.0 ATR factor is implemented as a fixed research policy.

## D1 — protective stop and stop-based sizing (implementation authorized)

Proposed research policy: disaster stop distance = **2.0 × the last fully closed M5 ATR**, measured from the actual executable entry quote and aligned outward to the symbol tick size. Reject the order if broker minimum-stop rules cannot accept that stop; do not silently widen it.

Use broker `OrderCalcProfit(entry, stop)` in account currency to determine modeled loss per volume. Round volume down to the broker volume step, then apply existing ceilings: **0.25%** initial equity risk, **0.01** base lot, **0.03** basket lots and **0.05** total lots. Reject if minimum volume would exceed any ceiling. The user authorized this **2.0 ATR** implementation in this conversation.

Before a grid addition, sum modeled losses at every protective stop, including the proposed order, and require total within the existing **35 account-currency** basket budget. Include broker costs conservatively; gaps/slippage may exceed the modeled amount. Keep existing maximum 3 layers and multiplier 1.0. Acceptance of this policy is not acceptance of profitability or live trading.

## D2 — persistent risk scope and reset (implementation authorized)

Proposed research policy: use account-wide equity for the existing **75 account-currency daily loss** and **5% drawdown** limits, with a dedicated test account. Persist day-start equity, fixed initial equity, day ID and halt latch keyed by account/server/symbol/magic. Use a UTC day boundary. Keep the existing initial-equity drawdown definition rather than changing it to high-water mark without a separate decision.

Conservative proposed reset: breached halt remains latched until explicit operator reset; normal day rollover updates day baseline only when not halted. Missing/corrupt persisted state with existing exposure blocks entries and requests review. The user authorized these day-boundary/scope/reset semantics in this conversation. No operator reset mechanism is exposed by this build; it remains a future separately reviewed operation.

## Approval consequence

Implementation is authorized; review these policies independently, continue durable order reconciliation and strict EA/API integration, then obtain real Windows compiler/runtime logs. New trading backtests still remain disabled until their prerequisite implementation and Windows safety checks pass. Live execution remains forbidden and no PR is automatically merged.

## Evidence boundary

Source implementation and reference-model tests are not MetaEditor compilation or MT5 runtime evidence. The hard false entry lock and tester-only terminal boundary must remain. Broker costs and fill reconciliation must fail closed where unavailable. See MQL5/STAGE2.md and docs/STAGE2_RISK_REVIEW.md for actual implementation details and residual limitations.
