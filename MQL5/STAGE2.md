# Stage 2 MQL5 implementation and evidence boundary

D1/D2 have been implemented as research code. **Every new entry is still blocked by `EntryRiskPolicyApproved() == false`; online AI remains disabled, terminal execution is rejected, and no MetaEditor compilation or MT5 runtime test has been performed.** This is not a trading backtest release.

## D1: stop and sizing model

`BuildProtectiveStop` uses a dedicated M5 ATR handle, shift 1, with the approved 2.0 multiplier. BUY opens at Ask, SELL at Bid; stops are tick-aligned outward. Invalid quotes, unsupported SL, invalid ATR/tick specification and stop/freeze constraints reject the proposal without widening the stop. `RiskSizedLots` uses broker `OrderCalcProfit` in account currency, rounds down and enforces the existing equity-risk, base-lot, basket-lot and total-lot ceilings. Original inputs/defaults are unchanged. The final order calls carry a nonzero protective stop, but remain unreachable behind the entry lock.

`BasketStopBudget` adds original entry-to-SL modeled losses for all scoped open positions plus the proposed order, without offsetting them by floating gains. Missing/crossed stops reject additions. Already recorded entry commission/fees and negative accrued swaps increase the model loss; positive rebates/swaps never reduce it. The existing 35 currency basket budget is checked.

`OrderCalcProfit` omits prospective commissions/fees and future swaps. There is no verified cost bound in this project, so the cost gate **always rejects** candidates. No arbitrary reserve or zero-cost assumption was added. Broker costs, fill-price/SL verification, pending order intent and consumed-bar reconciliation must be implemented and independently verified before considering removal of either entry barrier. Gaps/slippage can exceed modeled losses.

## D2: persistent risk state

Account-wide equity is used for the existing daily-loss and fixed-initial-equity drawdown limits. The UTC day baseline rolls only when not halted, after checking the previous baseline for a breach. A halted state never automatically resets at rollover or restart. Risk-triggered closures require the halt state to be persisted first. All closes additionally require a healthy state and successful pre-close write.

State paths are local tester `MQL5/Files` paths, **not `FILE_COMMON`**. Identity includes account login, broker server, symbol, magic and an explicit independent-test run ID. A retained exclusive lock prevents two instances from opening the same scope concurrently. Optimization is refused.

Before a deliberately isolated, dedicated-account research test, provision this exact two-line local file as `anticipatory_test_scope.txt`:

```text
synthetic_research_run_0001
UTC
```

This is a synthetic schema example, not broker data or test evidence. Line 1 must contain 1–64 ASCII letters, digits, underscores or hyphens. Line 2 must be exactly `UTC`; only empty trailing lines are accepted. Missing/malformed files fail initialization and are never generated or overwritten by the EA. The tester dataset/server clock must actually be UTC: in the tester `TimeGMT` follows simulated server time. The declaration does not convert time or prove that the data is UTC.

Use a distinct ID for every independent test pass; retain the same ID only when intentionally testing restart/reinitialization of that run. Reusing an ID retains old baselines and latches and is not a fresh backtest. The operator/harness is responsible for run provisioning; no automatic random ID silently defeats restart tests.

For a scope key `<key>`, files are:

- `AG2_<key>.state`: version, scope key, UTC day, day equity, fixed initial equity, halt bit and corruption checksum.
- `.state.started`: create-once full identity marker, written before the first state. Existing marker plus missing state fails even when flat; state without a matching marker fails.
- `.state.halt`: independently written halt barrier; it forces the latch on reload. Missing or unreadable halt persistence blocks current side effects.
- `.state.tmp`: staged state publication; leftover temporary files fail reload rather than choosing an older baseline.
- `.state.lock`: exclusive open file handle for lifecycle concurrency control.

Missing state with any account position or pending order fails initialization. Corrupt/mismatched/future-dated state fails initialization. Existing halted state cannot be reset through an input or code path. There is **no operator reset implementation**: retain the files and logs for review. A separately approved review/reset procedure would be needed; deletion is not a supported reset.

Serialization uses checksums, flushes, read-back validation, replacement and final read-back. These detect many corruption and I/O failures; they do not prove crash-proof or hardware-durable storage. If all storage writes fail, a halt cannot be guaranteed to survive a subsequent host loss. Tester runtime, restart, race, abrupt-crash and file-fault cases still require Windows evidence. The checksum is for accidental corruption, not a security boundary against deliberate file manipulation.

## Official references

- [OrderCalcProfit](https://www.mql5.com/en/docs/trading/ordercalcprofit): estimates account-currency trading profit, not a verified all-cost risk bound.
- [FileMove](https://www.mql5.com/en/docs/files/filemove): move/replace API; no assumption of fsync or crash-atomic publication.
- [Testing trade strategies](https://www.mql5.com/en/docs/runtime/testing): tester clock and sandbox behavior require explicit validation.
