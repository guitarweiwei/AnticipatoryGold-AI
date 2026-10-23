# Defect register — review build

Severity refers to the latent trading implementation. Containment does not mean those defects are fully fixed.

| ID | Priority | Evidence | Current disposition | Required validation |
|---|---|---|---|---|
| P0-01 | P0 | EA OpenPosition sends no SL; InitialLots ignores risk percentage | D1 research source implemented after approval; all new orders hard-locked, unverified; costs still fail closed | Approved stop distance, OrderCalcProfit sizing, server-side SL and broker-specific tests |
| P0-02 | P0 | OnInit/ResetDay reset baselines; no durable restart state | D2 scoped file/marker/barrier state implemented; terminal/entry lock remains; durability unverified | Approved account/day reset scope; durable latch and restart simulations/MT5 evidence |
| P0-03 | P0 | Original EA can trade real account without dedicated gate | Source fixed: non-tester initialization/order/close forbidden, no input override | Actual MetaEditor and demo rejection evidence pending |
| P0-04 | P0 | Original NormalizeLots rounds risk up to minimum; initial path misses basket cap | Source fixed: reject below min, step rounding down, entry/basket cap checks | Static tests pass; real symbol precision/order acceptance pending |
| P0-05 | P0 | Original stale/future/malformed values; published CSV drops source observation times and calendar expiry | PARTIAL/CONTAINED: snapshot validators exist, but source/calendar validity is not preserved through consumption; all orders locked | Carry source validity through a reviewed contract and revalidate on every consumption; parser parity and EA runtime pending |
| P0-06 | P0 | Original placeholder token accepted; model response weakly validated | Python fixed: secret requirement, strict schemas, finite values, same-direction only, freshness and timeout | 62 mocked API tests pass; actual provider calls not run |
| P0-07 | P0 | Original EA loose response parser permits correlation/age/schema/reversal defects | CONTAINED: unsafe parser removed; GetAISignal always vetoes | Active strict EA protocol + integration tests before any enablement |
| P1-01 | P1 | Position-count grid cap invalid for netting accounts | Hedging-only guard added; hard entry lock | Durable layer/order ledger and actual broker mode tests |
| P1-02 | P1 | ManageBaskets before breach latch; failed closes ignored | CheckRiskLimits moved first; failure logs/retries on later tester ticks | Inject partial fills/rejections, durable reconciliation and commission history tests |
| P1-03 | P1 | API replay cache is bounded and process-local | Documented limitation; duplicate IDs vetoed in process | Durable idempotency and restart policy before enabling EA |
| P1-04 | P1 | CSV/API lexical and single-row semantics differ | Safe publisher canonical output; active integration unavailable | Shared adversarial corpus/parity before active feed/EA integration |
| P1-05 | P1 | Macro source/feed/calendar unavailable | Manual provenance publisher only; expired blocked sample retained | Licensed source, real observations, calendar coverage and point-in-time archive |
| P1-06 | P1 | Strategy squeeze can bypass level/ADX; no PEEL, profitable-only time exit | Baseline semantics documented; not silently changed | Separate approved strategy change and holdout testing |
| GATE-A | Blocker | No MetaEditor executable or Windows broker environment here | NOT RUN | Real compiler log, warnings review and symbol specification |
| GATE-B-D | Blocker | No MT5 tester/forward evidence; order lock remains | NOT RUN, no performance metrics | Approved implementation then deterministic baseline, costs, unseen data, resilience and demo evidence |

Code findings and exact baseline line references are retained in docs/RISK_REVIEW.md. Review must remain blocked while Critical/High defects persist. Neither local tests nor CI provide live approval.

## Stage 2 update

The user authorized D1/D2 implementation. Stop construction and sizing code, full original-entry→SL basket budgeting and persistent day/initial-equity/halt state are present in source. They are not runtime-verified fixes. Prospective costs remain unknown and independently block every entry. No consumed-bar/pending-order ledger, actual-fill/SL verification or crash-proof durability is claimed. See docs/STAGE2_RISK_REVIEW.md and MQL5/STAGE2.md.

## 2026-10-21 six-agent revalidation

- **P0-08 (API source fix tested):** provider review previously approved the old macro snapshot if the CSV changed while awaiting the model. The API now re-reads the canonical file after the await and vetoes missing, blocked or changed observations. Eight added mocked regression cases cover mutations and unchanged republication. This does not solve missing source-validity metadata (P0-05), cross-process atomicity or active EA integration.
- **P1-07 (open, trading blocked):** EA CopyVal/BuildSignal does not fully validate finite/EMPTY_VALUE indicator results or the complete closed OHLC window. Missing/zero history can create a false candidate. Require complete validated closed-bar data before any execution unlock; changing the SQZ strategy itself requires separate review.
- **DOC-01 (corrected):** CLOUD_COMPILE.md previously claimed a metaeditor-compile.yml workflow existed. It is absent; the document now explicitly describes scripts and proposed follow-up only. No Windows compile evidence exists.

All 35 original EA input declarations remain identical to the supplied ZIP. No risk policy, order lock, EULA consent, live/demo authorization or merge status changed. See REVALIDATION_20261021.md.

## Stage 3 — user-authorized items 1–3

This update supersedes implementation-status observations above, while keeping their runtime/release gates open.

| Finding | Stage 3 source disposition | Remaining evidence / blocker |
|---|---|---|
| P0-05 original source/calendar validity loss | CSV2 carries numeric/calendar observation times and expiry; shared Python policy and EA consumer recheck originals, not only assembly | Source authenticity/licensing/archive review, actual MQL parsing and historical replay remain unverified |
| P1-07 invalid signal data | Complete closed OHLC window and finite/EMPTY_VALUE indicator guards added; formulas unchanged | Actual MT5 timing/history quality, nondefault timeframe testing |
| Durable intents and actual fill/SL | Pre-send persistent OPEN/CLOSE intent + consumed bar, retained pending on failure/restart, order/deal/position/SL/price-risk checks | Uncompiled; actual Windows I/O, lost ack, partial fill and failure recovery evidence; no operator reset/unlock |
| Complete known basket cash flows | Registered full position histories, signed profit/commission/fee/swap plus remaining open value; conservative debits cannot be offset by gains/rebates; finalized archive precedes retirement | Broker history completeness/cost attribution and actual partial-close evidence; unsupported INOUT/OUT_BY or unallocated charges veto |
| Unknown prospective costs | Explicit authorized/verified/known/currency/provenance/expiry scaffold; flags remain false, plus independent unconditional veto | A justified broker cost bound is still absent. No arbitrary reserve or zero-cost assumption; all candidates remain blocked |

API1.1 / nested macro2 are explicit breaking validity upgrades; old requests/CSV reject. All original35 EA input declarations, numeric ceilings and all terminal/entry/online-AI locks remain unchanged. Tests:175 offline checks; MetaEditor/MT5/Windows/provider/broker execution NOT RUN. Read STAGE3_IMPLEMENTATION.md and VALIDATION_RESULTS.md for the actual evidence boundary. Historical Stage2 and early 2026-10-21 reviews are not retroactive proof of Stage3 execution.
