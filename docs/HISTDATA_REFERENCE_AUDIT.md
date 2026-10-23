# Conditional HistData reference study — audit record

This study uses native MT5 indicators and a separate Python quote-execution model. It is not an MT5 Strategy Tester report. It does not authorize live orders or establish production readiness. Draft PR #1 remains unmerged.

## Verified input

- Original source: 15 public HistData XAUUSD tick ZIPs, October 2023 through December 2024. SHA256 identities are pinned in `scripts/research_data/histdata_source_hashes.json`; every ZIP CRC is checked. Original quote archives and metadata are preserved privately.
- Two adjacent repeated one-hour blocks were proved byte-identical. Only the second occurrence of each whitelisted block is removed: 4,136 rows in October 2023 and 7,079 in October 2024. The repair requires original ZIP SHA256, member name, exact row ranges, block hash, and byte equality; it is not generic deduplication.
- Local full derivation completed: **61,451,289 observed ticks**, normalized SHA256 `56034e91d8e3a8a151367dacc5b0a2953869ff89ca8d19acd6641eec12e2f709`, strict input window 2023-11-01 inclusive to 2025-01-01 exclusive UTC. No quote sorting, interpolation or missing-minute fabrication.
- Derived bid M1: **412,951 bars**, SHA256 `1fdb133f897ec4f4e8e269c7f908ef47ceae312dcdb5381305b4036163b94711`. This is derived CSV evidence, not yet an MT5 full-history readback.

## Clock and coverage limitations

HistData's stated fixed-EST convention did not match summer controls against independently acquired Exness quotes. Predeclared minute-change correlations support a conditional research conversion: source-local dates 2024-03-31 through 2024-10-26 use UTC=local+4 hours; all other dates use +5 hours. Eight unaffected main controls met the fixed sample-count, correlation and separation thresholds. Supplementary March 31 evidence had only 293 pairs, below the unchanged 300-pair requirement; it is weak evidence, not a passed control. November 4 was excluded as strong evidence because the independent source had ordering anomalies. The 2023 warmup and every day of the full window are not independently certified.

The acquired Exness annual file stops on December 15 and contains two time reversals. It is a local clock crosscheck, not a complete replacement performance dataset.

The 10,248-hour UTC grid includes 3,358 unobserved hours. Without an authenticated session calendar these remain unknown source gaps; they are not all assumed closed-market periods. Structural checks passing does not certify complete 2024 coverage, provider licensing, broker contract calibration, or empirical clock correctness over the full window.

## Frozen execution assumptions

Capital USD 5,000; leverage 1:30; at most one 0.01-lot position; price-stop risk cap 0.25%; spread limit 80 points with research point 0.001; initial-equity 5% sticky halt. AI and macro inputs stay disabled. Base costs are commission USD20/lot/side, swap debit USD150/lot/day, adverse slippage30 points; stress doubles these assumptions. These are fixed research costs, not authenticated historical broker charges. No final forced liquidation; residual positions are marked to market. Production intent-risk and prospective-cost gates are not validated by this proxy.

Only six observed first ticks of 2024 source M5 bars pass the fixed spread prefilter. This does not establish entry eligibility or zero trades: native original indicator signals still determine entries. Do not widen the threshold to obtain activity. Undefined zero-trade statistics must remain undefined.

## Actual execution evidence

Local tests: 37 data tests and 12 reference-model tests passed. The first cloud run stopped at a source-file hash guard: the web editor added one final LF to the JSON manifest. Downloaded bytes were compared; the parsed JSON and all 15 archive identities were unchanged. Only the manifest file hash guard was updated.

Current isolated run: https://github.com/guitarweiwei/AnticipatoryGold-AI/actions/runs/39969828448 , source commit `30ab02c6b79c745f5f88e5657396258b6447c26c`. Observed native exporter compile: **0 errors, 0 warnings**. At this record the full study is still running; no valid strategy return or drawdown result has been produced. Its final summary must preserve `CONDITIONAL_OBSERVED_TICKS_RESEARCH`, uncertified clock and coverage flags, and exact source bindings. Charts may be generated only from completed, reconciled equity/trade artifacts.
