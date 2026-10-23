# AnticipatoryGold AI v1 — strategy semantics and research gates

Status: static specification of the imported source at commit `f8f2fe674ae43b84c1fb83ae99a8760807d66fc5`. No profitability, MetaEditor compilation, or MT5 backtest evidence is asserted. Later safety fixes must be assessed against their actual diff; this document does not authorize a parameter or strategy change.

Sources: `MQL5/Experts/AnticipatoryGold_AI_v1.mq5`, `docs/PROJECT_SPEC.md`, `docs/CODE_AUDIT.md`, `docs/API_CONTRACT.json`, `prompts/00_orchestrator.md`, and `tests/acceptance_checklist.md`.

## 1. Observed signal and timing

The intended execution symbol is `InpSymbol` (default XAUUSD). The strategy evaluates entry candidates on the first received tick with a different current M5 bar timestamp. It does not queue a candidate for later in that bar if spread, macro, news, or API checks reject it. Protective basket management and risk checks run on every received chart tick before the entry gate. Attaching to another symbol's chart makes evaluation cadence depend on that chart's ticks; use the traded symbol's chart for reproducible testing.

Indicator inputs use shift 1, the most recently closed bar of each timeframe. H1 trend uses EMA(20), EMA(50), and ADX(14), main buffer. M5 trigger uses ATR(14), Bollinger Bands(20, 2 standard deviations), close[1], close[2], and open[1]. The level window is M5 shifts 2 through 13 inclusive at default lookback 12; the candidate candle itself is excluded.

Define:

- `F`, `S`: closed H1 fast and slow EMA prices.
- `A`: closed H1 ADX, dimensionless indicator value.
- `V`: closed M5 ATR, in symbol quote-price units.
- `C1`, `C2`, `O1`: M5 close[1], close[2], open[1].
- `HH = max(high[2..lookback+1])`; `LL = min(low[2..lookback+1])`.
- `SQZ = (upper_band[1] - lower_band[1]) / V < InpSqueezeATRRatio`.
- `BULL = C1 > C2 AND C1 > O1`; `BEAR = C1 < C2 AND C1 < O1`.

Strict comparisons mean equal EMAs, equal closes, and doji candles do not qualify. Nonpositive ATR or unavailable copied indicator values produce no candidate.

| Candidate | Exact imported condition |
| --- | --- |
| BUY | `F > S AND BULL AND (A >= minADX OR SQZ) AND (C1 >= HH - 0.35*V OR SQZ)` |
| SELL | `F < S AND BEAR AND (A >= minADX OR SQZ) AND (C1 <= LL + 0.35*V OR SQZ)` |
| HOLD | Neither condition, missing inputs, or a later veto |

The `0.35` proximity multiple is hard-coded. A BUY need not close above HH and a SELL need not close below LL. With SQZ true, both the ADX threshold and proximity test are bypassed. Consequently `SQZ+LVL_BREAKOUT` / `SQZ+LVL_BREAKDOWN` are code labels, not evidence of a confirmed breakout, a squeeze release, momentum calculation, or a proprietary SQZ algorithm. Likewise the comment about a lower high is not an implemented high-to-high comparison. These semantics are documented, not changed.

The base score is `0.60 + min(0.18, max(0, A - minADX)*0.006)`, ranging from 0.60 to 0.78 for ordinary finite inputs. The slope is score units per ADX unit. A squeeze can therefore produce a score of 0.60 with ADX below 18. The score is an uncalibrated heuristic, not a probability. After the optional API gate, the EA requires score at least `InpAIMinConfidence` and repeats EMA direction alignment.

## 2. Candidate invalidation and advisory boundaries

A candidate is eligible only during its evaluation event; rejection does not establish a pending order. Spread, news, macro, risk halt, missing data, confidence, existing basket direction, and exposure limits may each veto an entry. No separate reversal exit or trend-change exit exists in the imported source; a changed regime alone does not close a basket.

The frozen project contract permits AI to confirm or veto the original candidate only. The imported EA's response parser can replace direction and lacks request/time validation, so the API contract and imported EA are not yet equivalent. EA-side same-direction validation and fail-closed parsing are required safety work; they must not be treated as proven until tested. Online AI is skipped in Strategy Tester. With AI disabled, the base heuristic is compared to the same confidence threshold.

The imported macro gate rejects absolute DXY change greater than 0.35 percent or absolute nominal US10Y yield change greater than 12 basis points. Equality is allowed. News blocks when the configured switch is on and the CSV flag is nonzero. These are volatility/news vetoes, not directional forecasts. Real yield is read as text but not applied to the imported EA signal or payload. Timestamp freshness, malformed numeric fields, and point-in-time availability require explicit validation; the original parser does not provide it. A valid schema example is not a live or historical feed.

## 3. Position and grid semantics

Only positions matching `InpSymbol` and `InpMagic` are counted in EA basket functions. A first entry uses normalized base lots; the risk-percentage input is unused in the imported sizing. Subsequent adds need a new same-direction signal that passed all entry gates. They are not unconditional price-grid orders.

For an existing basket, an add also requires:

1. Position count below `InpMaxGridLayers`, including the initial position.
2. Candidate direction matching the existing basket direction.
3. Adverse move from the most recently opened matching position of at least `InpGridATRStep * latest closed M5 ATR`: BUY uses current ask at or below that position price minus the distance; SELL uses current bid at or above price plus distance.
4. Proposed lot size `baseLots * lotMultiplier^n`, then normalized, where n is current matching position count.
5. Post-add matching lots not above total or basket lot limits.
6. Current basket P/L not strictly below `-0.50 * InpBasketStopMoney`; equality passes this add gate.

ATR spacing floats with the latest completed M5 bar; it is not locked at basket inception. The price reference is the most recent entry, not the basket average. No stop-based worst-case basket-loss computation exists in the imported add logic. `BasketLots()` equals `LotsTotal()` in the original, making those two scopes identical for its single symbol/magic basket. The initial-entry path checks total lots but not the basket lot cap. The original lot normalization can round a request up to broker minimum and assumes two volume decimal places.

Position count is not equivalent to entry-layer count on a netting account, where repeated entries merge into one position. Until a tested durable layer ledger or explicit hedging-only restriction exists, the count-based layer cap cannot be assumed effective on netting accounts. Multiple opposite-side positions discovered on restart also require reconciliation rather than inferring direction from whether any BUY exists.

## 4. Exit semantics and absent features

Imported basket P/L sums matching position profit, swap, and an attempted position commission property. Availability/correctness of that property requires actual MetaEditor verification and deal-history accounting. Do not silently claim this is a complete net-of-cost P/L implementation.

Exit order on each tick is basket take profit at P/L >= 8 account-currency units, then basket loss at P/L <= -35, then age exit. The age exit requires oldest matching position age strictly greater than 180 minutes AND positive P/L. It is not an unconditional maximum holding time; flat or losing baskets remain open until another exit acts. ATR, trend, and candidate invalidation do not close existing positions. All imported exits attempt full closes; close success and partial fills need verification.

Daily loss is current account equity below equity at day initialization, measured in account currency. Imported day boundaries use broker `TimeCurrent()` midnight, not UTC. Drawdown is below EA-start account equity, not a rolling equity high-water mark. Both can be affected by manual trades, other EAs, deposits and withdrawals. Their state is in memory and resets at restart. Risk halt is sticky for that EA session even after daily baseline reset. The default close-on-breach flag already closes on drawdown breach despite the separate emergency-DD flag being false.

No broker-side SL/TP is submitted in the imported order calls. Basket stop money is an observed trigger, not an enforceable maximum loss during gaps, outages or rejected closes.

**PEEL partial close is absent.** The orchestrator prompt mentions it, but there is no partial-close implementation or approved trigger, volume fraction, minimum remainder, layer attribution, or interaction with risk limits. Leave it absent pending an explicit specification and user review. No automatic parameter tuning, learning system, multi-horizon forecast, news fetching, or demonstrated ML model is implemented by these entry formulas.

## 5. Input units and imported defaults

These values are an inventory, not recommendations or revised risk settings. For XAUUSD, quote-price units are commonly USD per troy ounce; confirm the broker's actual symbol contract. Account currency may differ from USD. One point equals `SYMBOL_POINT`; the EA does not define a pip. A basis point is 0.01 percentage point of yield; a 0.35 percent change is not a 0.35 price-dollar move.

| Inputs | Default | Units / meaning |
| --- | --- | --- |
| InpSymbol | XAUUSD | Broker symbol identifier; suffix must match |
| InpTrendTF / InpEntryTF | H1 / M5 | Indicator timeframes |
| InpFastEMA / InpSlowEMA | 20 / 50 | Trend-timeframe bars |
| InpATRPeriod | 14 | Entry-timeframe bars |
| InpADXPeriod | 14 | Trend-timeframe bars |
| InpMinADX | 18 | ADX units |
| InpLevelLookback | 12 | Completed entry bars excluding signal candle |
| InpSqueezeATRRatio | 0.75 | Band width divided by ATR, dimensionless |
| InpGridATRStep | 1.2 | ATR multiple |
| InpMaxGridLayers | 3 | Position-count cap including initial entry; hedging assumption |
| InpBaseLots | 0.01 | Broker lots, not ounces or account currency |
| InpLotMultiplier | 1.0 | Dimensionless multiplier per add |
| InpMaxLotsPerBasket / InpMaxTotalLots | 0.03 / 0.05 | Matching broker lots |
| InpBasketStopMoney / InpBasketTakeProfitMoney | 35 / 8 | Account-currency trigger amounts |
| InpDailyLossLimitMoney | 75 | Account-currency equity-decline trigger |
| InpMaxEquityDrawdownPct | 5 | Percent below startup equity |
| InpRiskPctPerInitialTrade | 0.25 | Intended equity percent; unused in imported sizing |
| InpMaxSpreadPoints | 80 | Symbol points, not pips or price dollars |
| InpMaxHoldMinutes | 180 | Minutes, profitable-basket age gate only |
| InpMagic | 26101401 | EA position identifier |
| InpUseOnlineAI | false | Boolean advisory gate |
| InpAIEndpoint | http://192.168.1.20:8000/decision | Configured URL, illustrative LAN host |
| InpAIBearerToken | CHANGE_ME_SHARED_TOKEN | Placeholder secret; must not authorize requests |
| InpAIMinConfidence | 0.58 | Score in [0,1], not calibrated probability |
| InpUseMacroCSV / InpMacroCSV | true / macro_feed.csv | Boolean and FILE_COMMON filename |
| InpMaxDXYChangePct | 0.35 | Absolute percent change over documented 1-day horizon |
| InpMaxUS10YChangeBps | 12 | Absolute nominal-yield change in basis points over same horizon |
| InpBlockOnHighImpactNews | true | Boolean news veto |
| InpCloseOnRiskBreach | true | Boolean full-close attempt on risk breach |
| InpEmergencyCloseOnDD | false | Additional drawdown close attempt switch |

Other hard-coded values: Bollinger period 20 entry bars and deviation 2.0, proximity 0.35 ATR, grid stress veto at 50% of basket stop money, trade deviation 30 points, API timeout 5,000 ms. None is an approved optimization result.

## 6. No-lookahead and validation acceptance

For any historical harness, evaluate at the first eligible tick after entry-bar close. Use H1 bars closed by that tick, never the final H1 value backfilled across its earlier M5 bars. Use only level bars 2..lookback+1 available at that instant. Entry fills occur at executable bid/ask after the decision and include spread, commission, swap and declared slippage. Missing bars, indicator buffers or incomplete history must reject a candidate, not create zero-valued synthetic levels.

Historical macro and event records must include publication/availability times and be joined as-of the decision time; observation timestamps alone do not prevent leakage. Exclude later revisions unless archived vintages prove availability. Do not replay today's CSV through past ticks. Do not send historical candles to a current online model and call the output a contemporaneous AI backtest. Compare AI uplift only with archived time-aligned decisions or a separately declared reproducible historical model procedure.

Before tuning, record fixed chronological in-sample, validation and final holdout dates, data source/version, timezone/DST, broker symbol specification, costs and tick model. Do not invent date ranges without inspecting available data. Freeze parameters before final holdout; retain a record of every trial and do not repeatedly tune on holdout. Walk-forward training/selection must use only earlier windows.

Falsifiable research hypotheses and required tests (all performance results remain NOT RUN):

| Hypothesis / safety property | Required test and acceptance evidence |
| --- | --- |
| Code semantics are reproducible | Synthetic closed-bar cases at equality boundaries, bullish/bearish symmetry, squeeze with low ADX/far from level, missing history; candidate ledger agrees with actual MT5 implementation |
| Closed-bar timing prevents future leakage | Alter all future bars and unavailable macro records; earlier decisions must remain unchanged |
| Rule signal has useful net expectancy | One-layer, AI-off baseline across predeclared trend/range/news and unseen windows, with costs and uncertainty; reject edge claim if evidence is inadequate |
| Grid improves a risk-adjusted objective | Compare 1, 2 and 3 layers on identical periods after safety gates; report worst basket, floating drawdown, exposure and tail sensitivity, not only win rate |
| AI confirmation adds value | Archived same-candidate matched comparison including HOLDs, failures, latency, costs and rejection rates; do not label heuristic scores probabilities |
| Exits and risk halts are effective | MT5/demo tests of profitable versus losing age exits, gaps, close rejection, restart, daily rollover, netting/hedging and concurrent trades; verify broker-side protections separately |

Release requires the full `tests/acceptance_checklist.md`, actual MetaEditor compilation, broker-specific MT5 execution tests, independent risk review and user approval where required. Static Python tests or formula simulations cannot substitute for EA compilation or real-tick Strategy Tester evidence. No live trading is authorized by this specification.
