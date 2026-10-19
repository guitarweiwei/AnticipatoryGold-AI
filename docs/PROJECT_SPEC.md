# AnticipatoryGold AI v1 — Frozen Interface & Acceptance Specification

Status: Phase 1 specification baseline. Research prototype only; not approved for live trading.

## 1. Architecture and authority boundaries

- **HP Windows / MT5 EA** is the sole execution authority. It owns order placement, sizing, grid-layer count, server-side protective orders, basket management, daily limits, and account-level halt logic.
- **Mac mini / Python API** is advisory only. It may confirm or veto an EA-generated candidate. It must never reverse candidate direction, increase size, add grid layers, or disable risk limits.
- **Macro adapter** supplies timestamped observations. Missing, malformed, stale, or future-dated data fails closed for new entries.
- **Backtest mode** is deterministic and must not call a live LLM. AI uplift can only be evaluated with time-aligned, archived decisions and macro observations.

## 2. Signal contract

EA sends a JSON object with:
- `request_id`: unique ID for idempotency/audit
- `symbol`, `timeframe`, `bar_time_utc`
- `regime`, `setup`, `direction` (`BUY` or `SELL`), `confidence`
- `close`, `atr`, `ema_fast`, `ema_slow`, `adx`
- `macro`: `timestamp_utc`, `dxy_change_pct`, `us10y_change_bps`, `real_yield_change_bps`, `high_impact_news_block`
- `reason`

API returns:
- `request_id`, `signal` (`BUY`, `SELL`, or `HOLD`), `confidence`
- `reason`, `macro_summary`, `model`, `timestamp_utc`

Acceptance rules:
1. Response request ID must match the request.
2. Only a same-direction `BUY`/`SELL` can pass; opposite direction is converted to `HOLD`.
3. Invalid JSON, unknown fields where strict schema is expected, timeout, HTTP error, authentication failure, stale data, or unavailable AI means `HOLD`.
4. The EA must reject stale responses and any response whose signal/confidence fields are missing or invalid.
5. AI confidence is an uncalibrated model score until calibration is demonstrated; it is not a probability of profit.

## 3. Macro data contract

CSV columns, in order:
`timestamp_utc,dxy_change_pct,us10y_change_bps,real_yield_change_bps,high_impact_news_block`

- Timestamp must be UTC ISO-8601 with `Z` or an explicit offset.
- Source and observation window must be documented for each feed.
- Default maximum age: 15 minutes for intraday market observations; event-calendar data must have its own validity rule.
- Missing/stale/future timestamp or parse failure blocks new entries.
- v1 volatility thresholds are configurable vetoes, not directional forecasts. DXY and yields must not be treated as mechanically predictive of gold.
- Historical testing requires point-in-time values, never today's CSV replayed across historical bars.

## 4. Risk controls

Initial research defaults (to be stress-tested, not optimized to a single period):
- Max grid layers: 3 including the initial position; test one layer first.
- Lot multiplier: 1.0; no martingale.
- Maximum total EA lots and per-basket lots are separate enforced limits.
- Risk per initial trade must be computed from stop distance, tick value/size, and account currency; reject entry if stop-based risk cannot be calculated.
- Every position must have a broker-side disaster SL where broker/order rules allow. Basket exits are additional protection, not a substitute.
- Daily loss and equity drawdown halt must persist through EA/terminal restart and use a clearly defined account-vs-EA scope.
- On breach: block new entries, attempt close according to policy, log close failures, and never resume automatically until the reset policy permits it.
- Before adding a grid layer, calculate worst-case basket loss at protective stops and enforce the basket risk budget.
- Never claim a guaranteed hard loss ceiling: gaps, slippage, liquidity, and broker failures can exceed modeled limits.

## 5. Required development gates

### Gate A — static/compile
- Python syntax check and unit tests pass.
- EA compiles in MetaEditor with zero errors; warnings are reviewed.
- Broker symbol precision, tick value, lot min/max/step, hedging/netting mode verified.

### Gate B — deterministic baseline
- Single-entry, no-grid, no-online-AI baseline in MT5 Strategy Tester.
- Real ticks where available; spread/commission/swap configured.
- No future data; signals use closed bars only.

### Gate C — safety tests
- Missing/stale/future macro data, AI timeout, invalid JSON, wrong request ID, disconnect/reconnect, restart with open positions, order rejection, partial close, spread spike, gap through SL.
- Daily halt and equity drawdown state survives restart.

### Gate D — strategy validation
- Trend, range, high-volatility/news and unseen out-of-sample windows.
- Report net profit, profit factor, balance/equity drawdown, worst basket, max floating loss, exposure, average win/loss, trade count, spread/commission sensitivity, and parameter stability.
- Add two layers only after Gate B/C; test three layers separately.
- Demo forward test before any live consideration.

## 6. Explicit non-goals for v1

- No reverse engineering or claim of exact reproduction of the screenshot's proprietary EA.
- No martingale, no unlimited grid, no unbounded AI authority.
- No profitability, win-rate, or maximum-loss guarantee.
