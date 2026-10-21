# Advisory API safety gates

From the repository root, run `uvicorn mac_ai.app:app --host 127.0.0.1 --port 8000` after installing `mac_ai/requirements.txt`. The standalone `cd mac_ai; uvicorn app:app --host 127.0.0.1 --port 8000` form imports the same repository validator. Set environment variables explicitly; `.env.example` is documentation and is not automatically loaded. `MACRO_CSV` paths are relative to the launch directory when explicitly configured; its default is the repository's canonical `config/macro_feed.csv`. Use a random shared token of at least 32 characters. Missing/example tokens disable the endpoint with HTTP 503; wrong credentials return 401. Bind to localhost or a secured private network, never an unauthenticated public listener.

## Protocol and source validity

`docs/API_CONTRACT.json` defines API **1.1**. Both requests and responses contain `schema_version: "1.1"`; legacy/missing/unknown request versions are rejected. The nested `macro` object independently uses CSV **schema 2**, with exactly these fields:

| Field | Type and meaning |
| --- | --- |
| `schema_version` | String `"2"` |
| `timestamp_utc` | Assembled snapshot time |
| `dxy_change_pct` | Finite number, DXY percent change |
| `us10y_change_bps` | Finite number, nominal yield change in basis points |
| `real_yield_change_bps` | Finite number, real yield change in basis points |
| `high_impact_news_block` | JSON boolean |
| `dxy_observed_at_utc` | Original DXY source observation time |
| `us10y_observed_at_utc` | Original nominal yield observation time |
| `real_yield_observed_at_utc` | Original real yield observation time |
| `news_observed_at_utc` | Original calendar assessment time |
| `news_valid_until_utc` | Calendar coverage expiry |
| `provenance_sha256` | 64 lowercase hexadecimal characters binding the archived manifest |

Macro timestamps must use exact UTC seconds (`YYYY-MM-DDTHH:MM:SSZ`). Snapshot and every numeric source observation must each be no older than 15 minutes, with observation ≤ snapshot ≤ now. News observation must not be after the snapshot, and calendar validity must include now. Refreshing only the assembled timestamp does not refresh observations or calendar coverage. Missing metadata, malformed fields, invalid digest, source expiry or calendar expiry vetoes entry. The digest binds a manually supplied manifest; it cannot prove source authenticity, licensing or complete calendar coverage. No real source or coverage is configured by these changes.

API and publisher use the same `config.macro_feed` validators. The canonical CSV requires the exact ordered v2 header and exactly one complete row; legacy five-column files and historical-plus-fresh multirow feeds fail closed. See `config/README_macro.md` for publication, provenance and point-in-time constraints. Requests require a unique request ID and explicit UTC candidate bar time. Unknown fields, nonfinite numbers and incorrect types return HTTP 422. The EA must treat every non-200 response as veto.

Before model review, the request macro object must match the validated canonical snapshot, including source times, calendar validity and digest. After the provider await, the service revalidates request source validity and reloads canonical data. Missing, blocked, expired or changed canonical data invalidates approval. Rewriting identical canonical observations does not invalidate an otherwise fresh review. This is a decision-time check, not a transaction with MT5; the EA remains responsible for freshness and its own final risk/execution gates.

The service confirms direction or returns HOLD. Confidence cutoff remains 0.58. Model output is locally schema validated, regardless of provider structured-output support. A failed provider, malformed output, stale feature, opposite-direction result or unwritable audit file vetoes entry. The service emits UTC ISO timestamps and echoes request IDs. It cannot size or execute trades.

## Operational limits and tests

A process-local 60-request/minute guard and 1,024-ID replay guard bound resource use. Replays return HOLD, including a repeated ID with a changed payload. They reset on restart and do not replace the EA's durable order idempotency. Use one worker for these process-local controls. Audit records include only request ID, signal, confidence, timestamp and mode, never request/model free text or exception details. Rotate/restrict logs operationally.

Run mocked tests from the repository root: `python -m pytest mac_ai/tests -q`. Tests use no paid calls, provider network, broker or MT5. MetaEditor compilation, MT5 Strategy Tester, real provider availability and production deployment remain unverified. EA execution and live integration remain locked.
