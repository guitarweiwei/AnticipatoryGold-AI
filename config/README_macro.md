# Manual macro snapshot: validation and publication

This v1 adapter fetches no data. The checked-in `macro_feed.csv` is an **expired,
synthetic schema example** with news blocking enabled. Do not relabel it with
today's timestamp. No licensed provider, automatic calendar or paid service is
configured.

The exact ordered header is:

```csv
timestamp_utc,dxy_change_pct,us10y_change_bps,real_yield_change_bps,high_impact_news_block
```

Exactly one complete row is required. UTC ISO-8601 timestamps must end with `Z`
or `+00:00`. Non-UTC offsets and naive times fail. Numbers must be finite, and
news block must be exactly `0` or `1`. Future observations and observations older
than **15 minutes** fail closed. This is the unchanged project specification
default; the utility provides no override. Missing, malformed, duplicate or
out-of-order multirow feeds are rejected, never sorted or filled with zeros.

| Field | Unit and window | Manual source identification |
| --- | --- | --- |
| `dxy_change_pct` | DXY 1-day change, percent; 0.1 means 0.1% | Actual DXY instrument, source and prior-close convention |
| `us10y_change_bps` | US 10-year nominal yield 1-day change, basis points | Exact nominal benchmark and source |
| `real_yield_change_bps` | Real yield 1-day change, basis points | Exact real-yield tenor/instrument and separate source |
| `high_impact_news_block` | Calendar veto boolean | Event coverage, blocking window and validity expiry |

Nominal yield is not real yield. Changes are context or veto inputs, not
mechanical directional gold forecasts.

## Provenance and validity

Retain original source evidence and a JSON manifest alongside each candidate.
The manifest requires `mode: "manual"` and a `feeds` object keyed by all four
field names. Each feed requires nonempty `source`, `instrument`,
`observation_window`, `license_note`, `observed_at_utc`, `published_at_utc`,
`received_at_utc` and `unit`. Units in CSV order are `percent`, `basis_points`,
`basis_points`, `boolean`. Numeric windows must be `1-day`; additionally describe
the exact prior-close and timezone convention in the source/instrument text.

- Observation time is when the market value or calendar assessment was observed.
- Publication time is when the source made that observation available.
- Receipt time is when the operator actually received it.
- CSV timestamp is the assembled snapshot time, after all receipts.
- Calendar provenance also requires `valid_until_utc`; its `observation_window`
  describes the covered events and before/after blocking interval.

All times must be UTC. The publisher enforces observation ≤ publication ≤
receipt ≤ snapshot ≤ now, numeric observations no older than 15 minutes, and
unexpired calendar validity. It cannot verify human-entered provenance or full
calendar coverage. Do not invent unavailable publication times. No current-source
manifest is shipped because no actual source observations were supplied. Review
licensing, use restrictions, cost and update limits before any provider integration.

## Publication and consumption

From the repository root, using independently sourced candidates:

```bash
python -m config.macro_feed candidate.csv config/macro_feed.csv --provenance candidate.provenance.json
```

Validation happens before destination mutation. A same-directory temporary file,
flush/fsync and `os.replace` publish the CSV atomically. Rejection leaves the old
CSV untouched. Retain the provenance in the research archive; the utility never
rewrites it. Each replacement is atomic, but two-machine publication is not a
distributed transaction.

MT5 reads its `FILE_COMMON` copy; writing the project copy alone does not update
Windows. Transfer the same candidate and provenance, then validate and publish on
Windows to the terminal common-files destination. Delayed transfer may expire.
Every consumer must revalidate freshness on every entry attempt, and block if
its local copy is missing or invalid. An old destination does not permit entry.

Python consumers can call `load_snapshot(path, now=aware_utc_datetime)` and treat
`ValueError` as HOLD/block. It returns immutable `Snapshot`; `as_dict()` uses API
field names and a JSON boolean. `validate_csv()` handles in-memory content.
These helpers do not place trades or enable execution.

## Point-in-time tests

Archive the source evidence, timestamps, calendar versions and available vintage
of revised series. At each historical decision, select only snapshots already
received then and pass that historical UTC clock to validation. Never replay
today's CSV across historical bars or substitute today's revised series.

```bash
python -m unittest discover -s config/tests -v
python -m py_compile config/macro_feed.py
```

Tests use synthetic dated fixtures and explicit clocks. They cover schema,
boolean, finite numeric and UTC validation, age boundaries, future-data rejection,
provenance order/calendar expiry and atomic replacement failure. These are adapter
tests, not MT5 backtest, provider-reliability or profitability evidence.
