# Initial Code Audit — AnticipatoryGold AI v1

Audit scope: generated v1 source snapshot. This is a static review, not a MetaEditor compile or MT5 runtime test.

## Blockers before any live use

1. **No broker-side SL on positions.** `OpenPosition()` sends orders with SL/TP set to zero. Basket management depends on the terminal/EA staying alive. Add per-position disaster SL and verify broker-side placement/modification.
2. **Risk-percent sizing is not implemented.** `InpRiskPctPerInitialTrade` is declared but not used to calculate volume from stop distance/tick value. Do not present it as an effective risk cap.
3. **Macro freshness is not checked.** CSV parser reads a timestamp but never parses or validates age/future time. Old observations may remain eligible indefinitely.
4. **Macro field contract is incomplete.** `real_yield_change_bps` is in the CSV/Python model but not used by the EA veto or payload. The macro CSV parser also assumes a single data row after the header.
5. **Daily/drawdown halt semantics need hardening.** Baseline equity/day state is in memory only and can reset after EA restart. Account-wide equity drawdown and EA-specific basket risk are mixed; define scope and persist halt state.
6. **No restart reconciliation/idempotency.** There is no durable basket state, unique request ID, or robust recovery policy for open positions after terminal restart/API retry.
7. **Order-result handling is incomplete.** `OpenPosition()` checks retcode but does not verify final position state/volume; `CloseAll()` does not robustly retry or report every failed close.
8. **Potential risk sizing edge cases.** `NormalizeLots()` forces the broker minimum even when requested lots are below minimum; it should reject an invalid size rather than silently round risk upward. Volume normalization is hard-coded to 2 decimal places.
9. **AI response validation is weak.** EA parser does not validate response request ID, timestamp, schema/version, or stale response. The response parser is hand-written and should be replaced with strict, tested parsing or a minimal well-defined protocol.
10. **No compile evidence.** Python syntax check is possible here, but MetaEditor/MT5 is unavailable in this environment; MQL5 compilation and Strategy Tester execution remain pending on Windows.

## Strategy-quality concerns

- The squeeze/level condition is a heuristic, not a demonstrated Squeeze Momentum implementation. `squeeze` can make the entry trigger permissive even without a clear level break.
- `InitialLots()` does not use the risk-percentage input despite its name/comment.
- Grid adds are gated by current basket P/L and ATR distance, but not by stop-based worst-case loss at the new layer.
- `InpMaxHoldMinutes` closes only if the basket is profitable; losing baskets can remain open until a different exit/risk check triggers.
- The macro thresholds veto large absolute changes; they do not establish directional macro confirmation.
- The sample macro CSV intentionally blocks trading; it is a schema example, not live data.

## Required fixes before Gate A/B

1. Implement strict macro timestamp parsing and maximum-age checks in both EA and API; reject future timestamps.
2. Make the macro schema identical in EA request and API response/logs; include real-yield value and source timestamp.
3. Add per-position disaster SL and stop-distance-based sizing, or explicitly disable all live-trading claims until implemented.
4. Reject invalid lot size rather than rounding up to broker minimum; normalize by volume step precision.
5. Persist daily baseline/halt state and recover open basket state from live positions.
6. Add request ID, response timestamp, schema version, timeout/stale-response checks.
7. Add Python unit tests for authorization, stale/missing macro feed, opposite-direction model response, API failure, malformed model output, and confidence threshold.
8. Compile in MetaEditor and test using the broker's exact symbol specification.
