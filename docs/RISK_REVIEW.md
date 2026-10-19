# Independent risk review

## Integrated review — 2026-10-20

Reviewed implementation: `24ed8e6e644b414709bc49654d9987ce7c312977`.
The baseline review is preserved below as historical evidence; its old line
references and findings must not be read as an inventory of the integrated code.

**Decision: appropriate for a clearly labeled, execution-disabled research review
PR. Merge/release acceptance is not granted. Demo/live execution and a meaningful
trading backtest remain blocked.** No new unmitigated P0 was found in this pass.
Safety containment is a code lock, not completion of the risk implementation.

### Independently verified containment and changes

- EA `MQL5/Experts/AnticipatoryGold_AI_v1.mq5:54–60,75–76,151–155,162`:
  non-tester initialization, ticks, orders and closes are guarded by a tester-only
  check without an input override. `EntryRiskPolicyApproved()` is unconditionally
  false at `:58`, and both `ProcessEntry` (`:133`) and final send (`:152`) check it.
  Therefore new orders are blocked **even inside Strategy Tester**. Existing
  order calls still contain zero SL and are unreachable under these guards.
- EA `:219–224`: online AI integration is a veto-only stub; no `WebRequest` call
  exists. The standalone Python API can review candidates but cannot trade.
- EA `:62,124–130,148,154`: unsupported netting mode is rejected, volume below
  broker minimum is rejected instead of rounded up, and initial/final paths
  enforce basket/total lot caps. `:78` checks/latches risk before basket closes,
  addressing the baseline close-before-detection sequence.
- EA `:163–217`: macro state is reset conservatively on every read, malformed,
  missing, stale and future observations block entries, and canonical column
  names replace the old schema. Real yield is retained as context. `:112–122`
  replaces the invalid position commission lookup with entry-deal costs, while
  explicitly acknowledging incomplete partial-exit cost accounting.
- API `mac_ai/app.py:63–116,153–165,168–190,199–232,235–263`: strict field/type,
  finite-value and model-output checks; response request ID and timestamp; fresh
  bar/macro checks before and after model wait; no opposite-direction acceptance;
  placeholder-secret rejection and constant-time authentication; failure-to-HOLD;
  redacted audit/provider errors; unwritable-audit veto; bounded process-local
  rate/replay/in-flight guards. These are advisory controls, not durable order
  idempotency. Provider output duplicate keys and nonfinite constants are rejected.
- Publisher `config/macro_feed.py:60–88,99–161`: validates single-row snapshot,
  freshness, finite values, strict news flag, human-recorded provenance and
  availability ordering before atomic replacement. It supplies no invented live
  observations and does not claim an automated licensed news/market feed.

### Finding disposition

| Baseline finding | Integrated disposition |
| --- | --- |
| R01 no SL/stop sizing | Unresolved; contained by unconditional entry lock. Requires approved stop-distance/risk policy and broker verification. |
| R02 accidental real execution | Contained by tester-only terminal-action guards and unconditional entry lock; source regression tests pass. |
| R03 persistence/breach sequencing | Sequencing corrected; durable baselines, reset semantics and restart recovery unresolved and execution-blocking. |
| R04 layer/basket limits | Netting rejected and immediate lot caps improved; worst-case stop risk and full input policy unresolved; entry lock retained. |
| R05 fill/close reconciliation | Failures now logged and incomplete entry halts; durable operation IDs, partial fills/closes and reconciliation unresolved. |
| R06 macro fail-open | Core malformed/stale/future validation improved; cross-component format/provenance/calendar consistency needs follow-up below. |
| R07 weak AI response binding | API checks improved; EA protocol intentionally disabled, not completed. |
| R08 default authentication | Default/placeholder acceptance corrected and errors redacted; secure remote transport remains an operational deployment gate. |
| R09 historical contamination | Current observations are freshness-checked and new tester orders blocked; archived point-in-time replay remains unimplemented. |
| R10 compile/runtime evidence | Position-property issue corrected in source; real MetaEditor and MT5 evidence still absent. |
| R11 exit/scope ambiguity | Existing behavior retained; holding, account scope, drawdown baseline and reset policies require explicit review before enabling. |

### Follow-up gates before any integration or execution is enabled

1. Retain the locks until user-approved stop distance, account-currency sizing,
   protective SL verification, worst-case basket risk, durable halt/idempotency,
   and broker-specific reconciliation exist. No numeric risk default was changed
   by this independent review.
2. Unify macro format acceptance: EA/publisher require one row while API accepts
   a monotonic archive (`app.py:121–147`); exponent/fractional-time/offset/news-flag
   lexemes differ. This currently vetoes some otherwise valid input and does not
   bypass the execution lock. Require common cross-language fixtures and one
   documented format before connecting components.
3. API currently validates two fresh macro snapshots but does not enforce their
   equality or deterministically reject conflicting numeric values (`:201–208`).
   Publisher checks event-calendar expiry but consumers do not carry/check that
   provenance validity alongside CSV. Define a single authoritative publisher and
   require calendar validity through the observation validity period; freshness
   alone does not prove the news gate is valid.
4. API replay/rate guards are process-local and evict after 1,024 IDs (`:241–263`).
   They reset at restart and do not replace durable EA order idempotency. Request
   body parsing uses FastAPI's JSON parser; `strict_json` applies to provider
   content only, so duplicate inbound JSON keys are not explicitly rejected.
   These are integration follow-ups for the advisory-only service, not evidence
   that an active trade path exists. Use a single local worker and protected
   transport; do not expose this research service as production infrastructure.
5. Do not mark the acceptance checklist complete. A zero-order tester run under
   the lock is a safety behavior check, not a strategy performance backtest.
   Obtain real MetaEditor compile and broker-specific MT5 failure/runtime evidence
   after approved implementation; preserve all unavailable gates honestly.

### Independent test evidence

Executed from the integrated source using
`/tmp/agai-api-venv/bin/python tests/run_checks.py`:

- Python syntax compilation completed.
- 6 EA source regression tests passed (not MQL compilation/runtime tests).
- 10 macro unittest tests passed.
- 62 mocked API pytest cases passed.
- One upstream Starlette/TestClient `httpx` deprecation warning; no test failures.

The initial run under the default interpreter stopped because pytest was absent;
the configured test virtual environment then completed the entire suite above.
No provider network/billing call, MetaEditor build, MT5 backtest, demo or live trade
was executed. Integration README/status reconciliation was being handled by the
orchestrator separately and is outside this implementation snapshot review.

---

## Historical baseline review

Reviewed baseline: `f8f2fe674ae43b84c1fb83ae99a8760807d66fc5`.
Scope: source and frozen specification inspection only. The line references below
refer to that baseline, not subsequent fixes. This pass changes no implementation.
No MetaEditor compilation, MT5 execution, broker connection, or profitability test
was performed. **Decision: blocked for release and live execution.** Critical and
High findings require resolution before merge; a review PR may contain unresolved
findings if they remain clearly marked and cannot enable trading.

## Critical

### R01 — Unprotected orders and ineffective percentage sizing

- Evidence: `MQL5/Experts/AnticipatoryGold_AI_v1.mq5:32,101,114–115`.
- Failure: orders explicitly carry zero SL. Terminal failure leaves exposure
  without a broker-side protective exit. The percentage input never enters the
  sizing calculation; normalization can round a requested size up to broker
  minimum and increase intended risk.
- Required fix: compute valid protective stops and account-currency loss using
  broker symbol specifications, reject invalid/below-minimum volume, enforce all
  lot/risk caps, and verify resulting protective orders. Reject entries when a
  stop or its monetary risk cannot be calculated. Stop distance is unspecified:
  do not invent a numeric distance or silently reinterpret an existing budget.
  Keep execution disabled until the user approves required risk parameters.
- Retest: BUY/SELL, non-USD account, min/max/step sizes, invalid tick properties,
  stops/freeze distances, gap/slippage, broker rejection, partial fill, and missing
  post-fill SL. A gap can exceed the modeled stop loss.

### R02 — No enforced prohibition on real-account execution

- Evidence: EA `:53–76,115`; `README.md:55` instructs demo use but code does not
  enforce account mode.
- Failure: attaching this EA to a real account can place orders if macro checks
  pass or are switched off. `InpUseOnlineAI=false` disables AI, not execution.
- Required fix: refuse real-account execution in this research release; retain
  explicit execution opt-in for tester/demo with safe defaults. This task does
  not authorize a real-account override.
- Retest: simulated real-account mode must never reach an order send; demo and
  tester must also remain inactive until their explicit research gates pass.

## High

### R03 — Risk state resets on restart and basket-stop detection can disappear

- Evidence: EA `:48,61,67,78–79,116–118`.
- Failure: initialization resets daily/start equity and halt state. Restart can
  therefore erase incurred losses. `ManageBaskets` closes a stopped basket before
  `CheckRiskLimits` observes it; a successfully closed basket can show zero P/L
  and permit immediate new entry if broader limits have not been hit.
- Required fix: latch breach before close, durably store account/symbol/magic
  scoped state, define account-wide daily and drawdown baselines/reset policy,
  reconcile open positions after startup, and fail closed on corrupt/missing
  state when exposure exists. Do not silently introduce a new daily reset policy.
- Retest: restart during loss/close/partial close, lost persistence, multiple EA
  instances, day rollover, deposits/withdrawals, and basket loss without daily DD.

### R04 — Layer and basket limits are incomplete

- Evidence: EA `:98,100,103–114`; frozen spec `docs/PROJECT_SPEC.md:48–55`.
- Failure: initial orders check total lots but not `InpMaxLotsPerBasket`; grid
  sizing considers present P/L rather than worst loss at protective stops.
  Counting open positions as layers fails on netting accounts where multiple
  entries aggregate into one position. Input values are not validated, so a
  multiplier above 1 admits martingale despite the frozen no-martingale rule.
- Required fix: enforce caps on initial and added orders at the final send
  boundary, model existing plus proposed stop risk, validate inputs, and either
  reject unsupported netting mode or use durable fill-based layer accounting.
  Preserve approved numeric budgets and prohibit layers while risk is undefined.
- Retest: basket cap lower than base lot, netting/hedging, adverse fills,
  multiplier above 1, invalid negative/zero budgets, multiple charts and restart.

### R05 — Close/order results and pending operations are not reconciled

- Evidence: EA `:69,103–117`.
- Failure: `CloseAll` ignores every close result. An accepted or partial order
  is not reconciled to actual positions, SL, or residual volume. Restart clears
  the bar guard; duplicate or ambiguous submissions may add exposure.
- Required fix: persist unique candidate/operation IDs before send, reconcile
  transactions and residual volume, log retcodes without secrets, retry only
  after checking actual state, and prevent new entries while close/reconciliation
  is unresolved. A failed close must retain the risk halt.
- Retest: timeout after accepted order, partial fill/close, placed result,
  rejection, connection loss, crash before acknowledgment, duplicate instance.

### R06 — Macro parser fails open for stale/malformed observations

- Evidence: EA `:120–127`; `mac_ai/app.py:47–60,74–78`;
  `config/macro_feed.csv:1–2`; frozen spec `:35–43`.
- Failure: neither parser checks timestamp age or future dates. EA coerces
  malformed numbers/news into zero; Python supplies missing numeric fields as
  zero. CSV uses `timestamp` while spec requires `timestamp_utc`. EA consumes the
  first row and Python the last; the two files can disagree and real yield is
  omitted from EA state/payload. A stale calm snapshot can allow an entry.
- Required fix: one strict schema, timezone-aware timestamps, finite values,
  strict binary news field, explicit source/window, maximum-age enforcement, and
  a documented single-row or latest-row rule shared by EA/API. Reject missing,
  malformed, stale, future, or inconsistent data. No invented live data source.
- Retest: corrupt headers, empty/extra rows, malformed/NaN/Infinity values,
  timezone-free/old/future timestamps, invalid news flag, mismatched copies.

### R07 — Advisory response is not bound to candidate or validity window

- Evidence: EA `:130–136`; Python `:19–43,88–99`; frozen spec `:14–30`.
- Failure: no request ID or bar timestamp is sent or validated. Hand parsing can
  accept malformed JSON and duplicate/nested keys; response timestamp/schema are
  unchecked. EA itself can accept an opposite direction (trend is a separate
  check, not an authority boundary). Python clamps model confidence instead of
  strictly rejecting malformed output. Replay or malformed responses can pass.
- Required fix: strict bounded schema and complete parsing, finite confidence,
  exact request ID, candidate direction, schema and response freshness checks on
  both sides; invalid or opposite decisions become HOLD. Recheck risk/market
  eligibility after synchronous API waits and before execution.
- Retest: wrong/repeated ID, stale response, duplicate/nested keys, trailing
  garbage, NaN, out-of-range/missing fields, reverse signal and delayed response.

### R08 — Default shared secret and cleartext LAN credentials

- Evidence: EA `:37–38,133`; Python `:11,71–73`; `README.md:43–46,54`.
- Failure: service accepts a known default bearer token when configuration is
  absent. LAN HTTP transmits bearer credentials and decisions without transport
  authentication. Merely copying a sample configuration is not a secure setup.
- Required fix: reject placeholder/absent shared secrets, use constant-time
  comparison, bind to a protected interface by default, and document authenticated
  encrypted transport before remote use. Error logs must not disclose keys.
- Retest: absent/sample/incorrect/correct credentials; inspect failure logs for
  secrets; confirm no unauthenticated call reaches the model.

### R09 — Deterministic tester can consume a current macro CSV

- Evidence: EA `:67,73,121–127`; frozen spec `:10,43,65–68`.
- Failure: only online AI is suppressed in tester. The current common CSV can
  influence every historical bar, introducing future information or blocking a
  run unpredictably as the file changes.
- Required fix: require explicitly disabled macro for deterministic baseline or
  archived observations selected by historical decision time. Record fixture,
  configuration, and costs; no current-data historical replay.
- Retest: changing present-day CSV must not affect baseline tester decisions;
  future observations must never be visible to historical decisions.

## Medium

### R10 — Compiler and runtime acceptance are unproven

- Evidence: EA `:99` accesses `POSITION_COMMISSION`; no executable tests in
  baseline (`tests/test_plan.md` and `acceptance_checklist.md` are checklists).
- Failure: the position-commission property requires verification against the
  installed MQL5 toolchain; deal-history costs may be required. Missing execution
  evidence leaves symbol precision, broker mode, costs and state handling unknown.
- Required fix: add meaningful Python failure tests and static contract checks;
  obtain a real MetaEditor build and broker-specific MT5 acceptance evidence
  separately. Static checks cannot certify MQL compilation or execution.
- Retest: MetaEditor zero errors with reviewed warnings, then deterministic
  no-grid baseline, failure/restart tests, and out-of-sample/demo gates.

### R11 — Time exit and equity terminology are ambiguous

- Evidence: EA `:27–29,45,116,118`.
- Failure: maximum holding duration only closes profitable baskets. Drawdown is
  relative to initialization equity, not a high-water mark, and uses account-wide
  equity while closes affect only EA positions. The word "hard" overstates the
  basket limit, which relies on ticks and successful closes.
- Required fix: document scope and rename misleading claims. Ask the user before
  changing holding/close/reset behavior or numeric risk parameters. No guarantee
  of a hard loss cap should appear in UI/documentation.
- Retest: loss-making basket past max hold, another strategy's losses, equity
  gain then drawdown, wide spread, and account cash flows.

## Release evidence and follow-up

This review found no evidence of a completed build/backtest. Baseline checklist
items remain unfulfilled. A final independent pass must inspect the integrated
diff and actual test output, verify closure by finding ID, and clearly identify
remaining unavailable MetaEditor/MT5 evidence. Python/static tests do not establish
safe live execution, calibrated AI probabilities, or profitability.
