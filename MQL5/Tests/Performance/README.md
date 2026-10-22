# Offline bid/ask importer — not a performance result

`ImportBidAskTicks.mq5` is an independent script. It imports a reviewed tick
package into a **new**, dataset-specific custom symbol in a disposable offline
terminal. It never loads the production EA, logs into an account, sends orders or
enables trading. Production code and its three entry/cost barriers are unchanged.

The script has not yet been compiled or executed. Its source-level review is not
MetaEditor or MT5 evidence. A historical performance baseline remains blocked on
usable data, reviewed economic assumptions and an actual tester charge model.

## Input package and exact parameters

Put the normalized file in the disposable terminal's local `MQL5/Files` sandbox.
Use a basename beginning `AG_PERF_`, without path separators or `..`. Its exact
header is:

```csv
time_utc_msc,bid,ask
```

Each row must contain a positive Unix UTC millisecond integer and two original,
positive, finite decimal quotes with `ask >= bid`. Scientific notation, quoting,
signed prices, missing fields and extra rows are rejected. Prices must fit the
configured digits exactly; the importer never rounds the data to a broker's
display precision. Timestamps must be nondecreasing. Every same-millisecond tick
is retained in its original row order. The final row count must equal the
externally validated expected count.

| Input | Required setting / meaning |
|---|---|
| `InpDatasetFile` | `AG_PERF_*.csv` local sandbox basename. Default `AG_PERF_ticks.csv`. |
| `InpCustomSymbol` | Unique `AG_PERF_*` identifier, at most 64 ASCII alphanumeric/underscore/hyphen characters. Existing symbols are refused. Default `AG_PERF_XAUUSD`. |
| `InpExpectedTicks` | Exact validated positive row count, at most `INT_MAX`. Default zero deliberately blocks execution. |
| `InpDatasetSHA256` | External runner's validated lowercase 64-character SHA256 binding. Default `UNVERIFIED` deliberately blocks execution. The script checks its shape, not file SHA256 or provenance. |
| `InpRunId` | Unique explicit run identifier using the same restricted identifier characters. Default `UNCONFIGURED` is only a placeholder; supply the reviewed run ID. |
| `InpPriceDigits` | Exact dataset/contract precision; default 2 is unverified. Do not change to 3 merely to obtain trades or silently reinterpret the production 80-point spread gate. |
| `InpContractSize` | Fixed synthetic contract size; default 100, pending review. |
| `InpTickSize` | Fixed synthetic minimum price increment; default 0.01, pending review. Must fit the configured digits. |
| `InpVolumeMin` | Fixed synthetic minimum volume; default 0.01. |
| `InpVolumeMax` | Fixed synthetic maximum volume; default 100. |
| `InpVolumeStep` | Fixed synthetic volume step; default 0.01. |
| `InpSessionScenario` | Must explicitly equal `CONTINUOUS_UTC_IMPORT_ONLY`. Default `UNKNOWN` deliberately blocks execution. |

Compile this script with the real MetaEditor in the approved disposable Windows
installation. Retain the source hash, compiler log and EX5 hash. Deploy the EX5
under that installation's `MQL5/Scripts` and invoke it with the reviewed script
parameter set. The runner must confirm the parameters actually used, enforce
network isolation/no account/no EA, and collect both the terminal journal and
the result below. This document does not claim the launcher or script-parameter
binding has been tested.

## Output and success criteria

One local file `AG_PERF_IMPORT_<wall-clock>_<tick-counter>.json` records the
result; the terminal log prints `AG_PERF_IMPORT_RESULT|filename|PASSED/FAILED`.
The JSON contains:

```json
{
  "schema_version": 1,
  "passed": true,
  "stage": "READBACK",
  "detail": "exact_bid_ask_tick_and_m1_parity_trading_still_disabled",
  "run_id": "reviewed_run_id",
  "symbol": "AG_PERF_dataset_specific_name",
  "dataset_sha256_external_binding": "externally_validated_lowercase_sha256",
  "ticks": "actual_integer_count",
  "m1_bars": "actual_integer_count",
  "first_utc_msc": "actual_integer_timestamp",
  "last_utc_msc": "actual_integer_timestamp",
  "source_authenticity_verified_by_importer": false,
  "contract": "FIXED_SYNTHETIC_SPEC",
  "historical_performance": "NOT_RUN"
}
```

This is an output-shape illustration, not an execution result. Actual counts and
timestamps are JSON integers. The runner must require a fresh nonempty result,
`passed == true`, exact reviewed input hashes/counts/date bounds and the matching
compiler/source/EX5 evidence. A log message, empty output or a zero-order run is
not success evidence.

The script checks every imported tick's millisecond time, bid, ask and stable
tie order using minute-bounded `CopyTicksRange` readback. M1 bars are built from
the observed bid quotes, with counted quote ticks, zero unavailable trade volume
and the final quoted spread; their times/OHLC/tick counts are read back and
compared. No missing minute or quote is interpolated. Tick flags represent
complete two-sided snapshots; original side-update/age metadata must remain in
the externally retained source archive and is not reconstructed here.

## Limits and failure handling

The custom symbol uses XAU base and USD profit/margin currencies, a synthetic CFD
leverage calculation mode, and an explicit continuous UTC import session. Its
trade mode remains **disabled**. These settings do not reproduce IC Markets'
historical specification, calendar, margin, commission or swap rules. No
prospective-cost bound, actual tester charge model, quote-age policy, H1/M5
parity/convergence validation or performance EA is provided by this script.

All ticks are validated in memory before symbol creation. Large packages can
exceed available memory and must fail rather than silently sample or truncate.
Custom-symbol operations can partially succeed; on any failure the newly created
symbol and imported state are retained for investigation. The script never
overwrites an existing symbol or deletes data to reset a failed run. Use a fresh
reviewed symbol identifier for an independent retry and preserve prior evidence.

Reference API signatures were checked against the official documentation for
[CustomTicksReplace](https://www.mql5.com/en/docs/customsymbols/customticksreplace),
[CustomRatesReplace](https://www.mql5.com/en/docs/customsymbols/customratesreplace)
and [CustomSymbolSetDouble](https://www.mql5.com/en/docs/customsymbols/customsymbolsetdouble).
That check does not substitute for compilation or real readback evidence.
