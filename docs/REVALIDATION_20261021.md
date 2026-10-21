# Six-agent revalidation — 2026-10-21

Outcome: a disabled research Draft PR, not a completed trading release. Existing branch/PR reused to retain the already-approved D1/D2 work. Source reviewed from GitHub head 08310e53f31e0c19a17c0f37b598456827c95f60.

| Agent | Finding / action | Evidence boundary |
|---|---|---|
| Strategy | Closed-bar OHLC and indicator validity checks remain incomplete; SQZ and profitable-only time exit semantics unchanged | Source review only; no edge/performance claim |
| MQL5 | Tester-only boundary and unconditional new-order lock retained; fill/SL verification, durable intents and full realized basket costs still incomplete | No MetaEditor or MT5 execution |
| AI API | Fixed stale macro approval during provider await; re-read latest snapshot, veto missing/blocked/changed values | Eight new mocked regressions; no actual provider call |
| Macro | Current CSV drops per-source observation times/calendar expiry; consumers can accept a snapshot after its underlying source expires | Synthetic review reproduces calendar expiry at T+1s accepted at T+14m; not live data |
| Backtest | Offline suite passes 112 checks; corrected claim that a Windows workflow exists | Python/reference/source tests, not MT5 backtest |
| Independent risk | New regression passes 8/8; pre-fix comparison fails seven mutation cases; original 35 inputs unchanged | Full API rerun 70/70; trading/release not approved |

## Changes in this update

Only API post-review snapshot validation, eight tests and review documentation changed. No EA input, ATR policy, risk limit, scope/reset policy, frozen API contract or trade-execution lock changed. The Windows document now explicitly states the compiler workflow is absent; scripts are preparation only.

## Remaining implementation and evidence gates

1. Extend/review macro source-validity contract and recheck source observation age/calendar expiry at consumption, with Python/EA parser parity. The post-provider API fix does not solve metadata absent from CSV.
2. Reject invalid or incomplete closed OHLC/indicator windows before producing a candidate; verify closed-bar/no-lookahead behavior in actual MQL5.
3. Implement durable pending-order and consumed-signal reconciliation, actual fill/volume/SL verification, complete realized basket fees and verified future-cost bounds. The current cost gate rejects all entries.
4. Add and review a Windows compiler workflow. Before installing MetaQuotes software, obtain explicit EULA consent and verify the actual installer/signature. No such consent or installation occurred. Obtain genuine compile logs; then runtime fault evidence.
5. Keep new entries disabled until prerequisites are reviewed. Only subsequently run an authorized deterministic MT5 baseline with actual broker specifications and costs, then resilience/out-of-sample/forward validation. Never remove locks merely to manufacture performance data.

Important risk-policy changes, trade unlocking and EULA acceptance require user confirmation. No broker credentials, paid model call, live/demo connection, automatic merge or real order occurred.
