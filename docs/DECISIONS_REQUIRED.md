# Risk decisions required before further execution work

No values below are implemented. Original numeric EA input defaults remain unchanged. Do not remove the entry lock as part of document approval alone.

## D1 — protective stop and stop-based sizing (approval required)

Proposed research policy: disaster stop distance = **2.0 × the last fully closed M5 ATR**, measured from the actual executable entry quote and aligned outward to the symbol tick size. Reject the order if broker minimum-stop rules cannot accept that stop; do not silently widen it.

Use broker `OrderCalcProfit(entry, stop)` in account currency to determine modeled loss per volume. Round volume down to the broker volume step, then apply existing ceilings: **0.25%** initial equity risk, **0.01** base lot, **0.03** basket lots and **0.05** total lots. Reject if minimum volume would exceed any ceiling. The new **2.0 ATR** distance needs explicit user approval.

Before a grid addition, sum modeled losses at every protective stop, including the proposed order, and require total within the existing **35 account-currency** basket budget. Include broker costs conservatively; gaps/slippage may exceed the modeled amount. Keep existing maximum 3 layers and multiplier 1.0. Acceptance of this policy is not acceptance of profitability or live trading.

## D2 — persistent risk scope and reset (approval required)

Proposed research policy: use account-wide equity for the existing **75 account-currency daily loss** and **5% drawdown** limits, with a dedicated test account. Persist day-start equity, fixed initial equity, day ID and halt latch keyed by account/server/symbol/magic. Use a UTC day boundary. Keep the existing initial-equity drawdown definition rather than changing it to high-water mark without a separate decision.

Conservative proposed reset: breached halt remains latched until explicit operator reset; normal day rollover updates day baseline only when not halted. Missing/corrupt persisted state with existing exposure blocks entries and requests review. The day-boundary/scope/reset semantics require user approval.

## Approval consequence

After user confirmation, implement and independently review these policies, continue durable order reconciliation and strict EA/API integration, then compile on HP Windows with real logs. New trading backtests still remain disabled until their prerequisite implementation and Windows safety checks pass. Live execution remains forbidden and no PR is automatically merged.
