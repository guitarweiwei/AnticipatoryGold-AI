# Validation plan (no profitability claim)

The frozen interface and release gates are defined in `../docs/PROJECT_SPEC.md`; known code issues are tracked in `../docs/CODE_AUDIT.md`.

1. Compile the EA in MetaEditor; fix broker-specific symbol/volume issues.
2. Strategy Tester: `InpUseOnlineAI=false`; begin with one layer and no grid adds.
3. Use real ticks where available and configure spread, commission, swap, and slippage assumptions.
4. Test trending, range-bound, high-volatility/news, and unseen out-of-sample periods.
5. Record net profit, profit factor, max balance/equity drawdown, max floating loss, worst basket, average win/loss, trades per month, exposure, and rejected signals.
6. Stress test spread x2, slippage, missing/stale macro feed, API timeout, invalid response, network disconnect, gap through stop, order rejection, and restart with open positions.
7. Do not enable grid adds until single-entry baseline and risk controls pass.
8. Online AI is intentionally skipped in Strategy Tester. AI uplift requires archived, time-aligned historical AI decisions and macro data.
9. Run demo forward tests for several weeks before considering any live deployment.
