# AI + FVG + ATR Grid: staged research integration

Status: **PARTIAL IMPLEMENTATION — NOT CONNECTED TO EXECUTION**.

## Preserved safeguards
- Keep `ResearchExecutionAllowed()`, `EntryRiskPolicyApproved() == false`, macro/news vetoes, and original risk latches unchanged.
- Do not enable demo/live trading or silently loosen original numerical limits.
- Existing `InpMaxGridLayers=3` remains unchanged until explicit review; research planner accepts up to ten layers, but does not alter the EA input.
- The Python advisory AI remains separate; Strategy Tester does not use live online AI.

## Research modes
1. AI Grid: original signal and existing AI policy, with ATR grid planner.
2. FVG Grid: closed-candle FVG/OB heuristic signal, ATR grid planner.
3. Hybrid: original AI/macro direction must agree with FVG direction; otherwise HOLD.

## Added source
`MQL5/Experts/Include/AIFVGGridResearch.mqh` contains isolated, non-executing research helpers. OB is an approximate candle proxy, not a validated institutional order block. Score is heuristic, capped at 100; not a probability.

## Unfinished before any comparison
- Connect planner to a signal-only EA research path; preserve every existing veto.
- Validate FVG age, mitigation and lookahead-free scoring; replace proxy displacement with middle-candle impulse metrics and independently verify OB logic.
- Build complete pending-order lifecycle and cancellation/reconciliation, broker stop/freeze/volume checks, spread/slippage/commission stress.
- Apply common basket stop, daily equity loss and peak-to-trough drawdown risk rules to **all** grid layers, including existing pending orders.
- Confirm 10-layer request and monetary limits with owner; current 3-layer default must not be silently changed.
- Compile in genuine MetaEditor and run MT5 Strategy Tester, then time-split walk-forward, parameter sensitivity and Monte Carlo; archive raw reports and exact broker symbol specifications.

## Backtest comparison specification
Same broker/symbol, history, modelling, spread/commission assumptions and risk budget across all three modes. Record trade count, net profit, profit factor, max equity drawdown, exposure, tail loss, regime attribution and out-of-sample performance. Never present fabricated results.

## Suggested test scenario (not active settings)
$5,000 starting balance, 1:30 leverage, non-martingale equal lots, 10 maximum layers, ATR(M15) × 1.2 grid, 1% basket risk, 2% daily loss gate, 15% peak-equity drawdown halt. All values require broker validation and explicit approval before activation.

## Ten-layer research update
The isolated planner now has capacity for ten equal-lot layers. This is **not** authorization to raise basket loss, total lots, daily loss, or equity drawdown limits. If the minimum broker lot cannot fit the entire planned worst-case basket risk, reject the plan; do not silently drop risk checks or round size upward. The EA default remains three layers and the planner is not wired to trading. Ten-layer stress tests must include gap-through-stop, margin insufficiency, all-pending-fill scenarios, and broker freeze/stop restrictions.

## Adaptive research planner (2026-10-29)
Added `AGSelectAdaptiveLayers()` and `AGBuildAdaptiveGrid()`. Confidence below 0.58 returns HOLD; relative ATR penalizes high volatility; available monetary risk caps the number of layers. The adaptive builder retries fewer layers if `OrderCalcProfit()`-based whole-basket stop loss exceeds budget. Thresholds are research heuristics, not calibrated probabilities. These helpers are not yet called by the production EA. Remaining gates: integrate with existing AI/macro/news vetoes, compute a defensible minimum-layer risk estimate, verify broker margin and gap loss, compile, test and run MT5 Strategy Tester. No trading lock changed.
