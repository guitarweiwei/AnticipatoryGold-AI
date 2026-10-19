# Acceptance Checklist

## Gate A — Code and contract
- [ ] Frozen spec reviewed
- [ ] Python compile passes
- [ ] API unit tests pass
- [ ] EA compiles with zero errors in MetaEditor
- [ ] No unreviewed compiler warnings
- [ ] Macro timestamps validated and stale/future feeds fail closed
- [ ] EA/API contract includes request ID and timestamp

## Gate B — Baseline strategy
- [ ] One layer only
- [ ] Online AI disabled
- [ ] Macro data point-in-time aligned or disabled for baseline
- [ ] Closed-bar signals only
- [ ] Real tick data and broker costs configured
- [ ] Out-of-sample window reserved before tuning

## Gate C — Risk and resilience
- [ ] Stop-distance-based position sizing tested
- [ ] Broker-side disaster SL verified
- [ ] Daily loss halt survives restart
- [ ] Equity drawdown halt survives restart
- [ ] Missing/stale macro data blocks entries
- [ ] AI timeout/invalid response blocks entries
- [ ] Duplicate signal/retry does not duplicate order
- [ ] Open basket is reconciled after restart
- [ ] Close failure and partial close are logged and retried safely
- [ ] Grid layer obeys worst-case basket risk budget

## Gate D — Evidence
- [ ] Trending, ranging, news/high-volatility and unseen periods tested
- [ ] Net profit, PF, max DD, worst basket, max floating loss reported
- [ ] Spread/commission/slippage stress tests run
- [ ] Two-layer and three-layer grid tested separately
- [ ] Demo forward test completed
- [ ] Independent risk review signed off
