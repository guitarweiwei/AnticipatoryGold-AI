# Stage 2 independent risk review

## Scope and approval boundary

D1/D2 approval was relayed by the orchestrator for this implementation stage.
The exact policy is retained in `docs/DECISIONS_REQUIRED.md`: 2.0 closed-M5 ATR
protective distance, existing numeric ceilings, entry-to-stop basket loss budget,
account-equity daily/fixed-initial drawdown, UTC days, durable scoped state, and
operator-controlled halt reset. Approval permits implementation and review, not
trading, profitability claims, or automatic merge.

This document records independent source review and acceptance/failure scenarios.
It changes no trading code or numeric parameters. **Decision: suitable for an
execution-disabled research review PR; no merge/release/trading approval.** Existing
terminal-action, online-EA/API, and unconditional new-order locks must remain.

## Final source review

Reviewed integrated implementation commit:
`03b2a3bf06184a0cc95d1d996658669c435ca361`, incorporating implementation
`ff5f9de` plus finite-metadata follow-up `29db1c8` and independent fixture
commit `5a595d0`. Review covers changes from parent `3b520d5`. All EA references below are to
`MQL5/Experts/AnticipatoryGold_AI_v1.mq5` in that implementation commit.

No new uncontained P0 was found. D1/D2 are now source implementations behind
multiple intentional vetoes; they are not certified broker/runtime controls.

### Verified at source level

- `:57,60,62,79,231,298,310`: tester-only terminal-action checks and the
  unconditional false new-entry lock remain, including the final order boundary.
  `GetAISignal` remains a HOLD/veto stub. No live or demo execution is enabled.
- `:69,249–275`: separate closed-M5 ATR handle, shift 1, approved 2.0 multiplier,
  Ask/Bid entry quote, outward tick alignment, supported-SL and broker stop/freeze
  rejection without widening; account-currency `OrderCalcProfit` loss, risk sizing
  and downward volume normalization. Basket/total/base ceilings are applied.
- `:277–295`: budget sums original entry-to-stop price losses, adds negative
  recorded entry costs/swaps and proposed risk, and never offsets floating gains.
  Unknown prospective costs deliberately force false even when price-only risk
  fits 35. This prevents claiming that missing broker costs equal zero.
- `:98–126,127–177`: checksummed scoped serialization, staged write/readback and
  replacement/readback, independent halt barrier, retained exclusive scope handle,
  full-identity bootstrap marker and fail-closed initialization. Any account
  position/pending order blocks clean bootstrap when state is absent. Optimizations
  are rejected; explicit test-run/UTC fixture provisioning is required.
- `:179–186,309–333`: old baseline is assessed before UTC rollover; halted days
  do not automatically reset. Halt/barrier persistence precedes risk-triggered
  closes; failed close logs and durably latches review before returning. No manual
  or automatic reset implementation silently clears the latch.
- During review, an orphan `.tmp` could have been overwritten during clean
  bootstrap before being checked. The final commit now checks it at `:141`, before
  any marker/baseline write, and rejects an orphan halt barrier too. This review
  correction changes no approved parameter or reset policy.

### Remaining findings, ordered by severity

**High, execution-enablement blocker — actual fill and order reconciliation.**
At `:303–306`, the source still lacks durable consumed-bar/order intent, complete
transaction/partial-fill recovery, and verification of actual fill price, volume
and server SL. A successful retcode is not proof that post-fill risk remains
inside the quote-based budget. Required fix/retest: retain both vetoes, implement
durable intent and deal/position verification, then exercise adverse slippage,
partial fill, timeout-after-acceptance, missing SL and crash/restart. There is no
currently reachable entry path, so this is contained for a disabled review PR.

**High, execution-enablement blocker — all-cost risk and basket ledger.**
`BasketStopBudget` correctly always vetoes at `:291–295`, because fees/future swap
have no verified prospective bound. Existing open-position accounting at
`:207,211–220,277–290` is not a complete realized-plus-open basket/partial-exit
ledger. Required fix/retest: define justified costs without inventing a new
allowance, reconcile all basket deals, and test prior realized losses, partial
exits, fees and swap. Do not remove the false return merely to obtain trades.

**High, release blocker — unavailable MQL/runtime/durability evidence.**
Persistence at `:98–177` detects many incomplete writes but cannot prove
hardware-durable ordering, atomic replacement or true restart recovery. A local
tester run ID and `UTC` declaration do not prove the dataset clock or sandbox
isolation. Required retest: actual MetaEditor compilation, Windows abrupt-crash,
disk fault, simultaneous instance, corrupt/missing/stale file and test-run
isolation cases, then broker-specific failure scenarios. No such results exist.

**Medium, dormant-path hardening — quote freshness and scope boundaries.**
The follow-up commit now rejects nonfinite quotes/point, invalid stop/freeze levels,
and unavailable critical metadata (`:249–274`); candidate direction/requested size
are validated too. Explicit quote-age/recheck and actual-fill validation remain
part of future execution work. Per-symbol/magic/run files monitor account-wide
equity but are not a single coordinated account-wide latch across multiple
different EA scopes. Dedicated isolated tests and the current locks contain that
limitation. Shared-account/multiple-scope use needs a separately verified policy;
do not infer cross-scope persistence from an exclusive per-scope file handle.

### Independent available tests

- Independently ran `/tmp/agai-api-venv/bin/python tests/run_checks.py` against
  final integrated `03b2a3b`: all **104** checks passed (10 EA source regression
  checks, 22 independent D1/D2 Python reference fixtures, 10 macro tests, 62 mocked
  API cases). Python syntax compilation also passed.
- One upstream Starlette/TestClient `httpx` deprecation warning; no test failures.
- `git diff --check` passed. Pending orchestrator README/status changes were
  documentation only and are not a new MQL implementation evidence claim.

These are offline Python/source checks. Reference fixtures intentionally model
abstract arithmetic and durable barriers, not MQL execution. They do not emulate
the filesystem, broker costs or fills. For example, a Python linear stop fixture
rejects profit-locked stops while MQL models their nonnegative loss as zero; they
are not claimed to be equivalent engines. No MetaEditor compile, MT5 backtest,
actual broker stop, Windows storage-fault test or live/provider call was performed.

## D1 acceptance and adversarial scenarios

| Scenario | Required result |
| --- | --- |
| BUY versus SELL candidate | Use the actual executable Ask or Bid respectively, not candle close/midpoint or the opposite quote. |
| ATR unavailable, nonfinite, zero or current bar | Reject. Approved distance uses the last fully closed M5 ATR, independent of an arbitrarily changed entry timeframe. |
| Stop between broker ticks | Align away from executable entry to tick size; report resulting modeled loss, never round inward to improve apparent risk. |
| Broker stop-level would require a farther stop | Reject instead of silently widening beyond approved construction. Validate stop side, tick grid, quote precision, stop/freeze constraints and metadata. |
| Tick size/value, equity or account-currency calculation invalid | Reject rather than substitute fixed lots or currency assumptions. |
| Volume step larger than risk-allowed volume or broker minimum | Reject; never round up to minimum. Volume must satisfy broker min/max/step and every existing ceiling. |
| Risk-sized volume differs from base lot | Take the minimum allowed valid size; 0.25% equity risk is a ceiling, not an entitlement to increase above 0.01 base lot. |
| Initial entry versus grid addition | Enforce basket 0.03 and total 0.05 lot ceilings at final send, maximum 3 layers and multiplier 1.0. Unsupported netting remains rejected. |
| Existing basket has unrealized gains | Sum nonnegative modeled original-entry-to-protective-stop losses with the proposal; do not offset by floating gains, omit positions, or use current-quote-to-stop loss. |
| Basket already has missing/invalid SL or unknown cost | Reject proposed additions and require reconciliation; do not assign zero risk. |
| Commissions, fees or future costs unavailable | Price-only `OrderCalcProfit` is insufficient proof of full budget compliance. Keep readiness false where a conservative cost allowance cannot be established without a new user-approved assumption. |
| Fill differs from preflight quote or volume | Reconcile actual execution price, protective order and filled volume. A quote-based pass is not evidence of post-fill budget compliance. Ambiguous/partial/unprotected exposure requires persistent freeze and documented handling. |
| Gap, spread change, rejection or disconnection | No hard maximum-loss guarantee; retain failure latch, inspect actual broker state before any retry. |
| Entry requested through any alternate caller | Final execution boundary retains unconditional lock and checks caps. No tester order may bypass the lock. |

## D2 acceptance and adversarial scenarios

| Scenario | Required result |
| --- | --- |
| Normal initialization without any prior state or exposure | Any baseline creation must be explicit and durably committed before readiness; persist current UTC day, fixed initial equity and day-start equity. |
| Restart with valid state | Load the original baseline and latch; do not rebase drawdown to new account equity. |
| Missing/corrupt/unsupported/inconsistent state with exposure | Freeze, request review, do not silently create a replacement baseline. Exposure detection must not silently ignore pending/unknown operations. |
| Invalid baseline number or mismatched scope | Reject zero/nonfinite/negative equities and wrong account/server/symbol/magic; no imported state from another account or EA instance. |
| Torn write, disk full, permissions, crash or concurrent writer | Preserve last valid state or fail closed; do not report successful persistence without verifying completion. Detect stale/partial state rather than quietly overwriting it. |
| Daily loss 75 or fixed-initial-equity drawdown 5% reached | Latch breach at equality, durably store it before any close attempt, block all new entries even if closes succeed. |
| Equity recovers or basket closes | Retain latch; neither favorable ticks, terminal restart nor successful closes constitute operator reset. |
| Ordinary UTC day rollover while unhalted | Update daily baseline according to approved policy and persist it; retain fixed initial equity. |
| UTC rollover while halted | Do not clear latch or rebase in a way that removes breach evidence. |
| Broker server date differs from UTC | Use documented UTC day identity. Do not claim historical broker/server time is UTC without verified conversion. |
| Clock rollback, future state, multi-day outage | Reject ambiguous state or request review; never infer permission to resume. |
| Manual trades, another EA or deposits/withdrawals | Account-wide equity scope is explicit; changes can affect limits. No cash-flow adjustment policy may be invented. |
| Strategy Tester, optimization, separate runs or terminal | State must be isolated to prevent importing a prior run's equity, latch or simulated future day, or mutating live-account state. Reproducibility requires recorded state-fixture policy. |
| Operator reset requested | Require explicit review/reset protocol; no automatic reset parameter or default may clear the latch. |

## Evidence requirements

Independent final review must cite the actual implementation commit and exact
file lines, inspect both reachable and currently locked paths, and distinguish
source regression tests from executed MQL behavior. Python reference arithmetic
tests can check policy examples but cannot prove MQL equivalence, filesystem
durability, broker validation, protective SL placement, or actual fills.

MetaEditor zero-error compile evidence and MT5 failure/runtime tests remain
required separately. No such execution evidence is claimed here. A zero-order
run under the hard lock is not a strategy performance backtest.
