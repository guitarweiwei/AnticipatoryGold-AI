# Independent D1/D2 reference fixtures

`risk_reference.py` and `test_risk_reference.py` specify approved arithmetic and state-transition examples in Python. They neither execute translated MQL5 nor prove that the EA implements these rules. Existing source regression checks catch selected wiring regressions; MetaEditor compilation, Windows storage failures, restart behavior, broker calculations and order outcomes still require real evidence.

Run `python -m unittest discover -s tests -p test_risk_reference.py -v`, or the complete `python tests/run_checks.py` after integrating source changes.

## Fixture assumptions

- Stops use **2 × fully closed M5 ATR** from the executable quote, rounded outward to tick size. Broker minimum distance uses the closing bid/ask (the quote equals entry only in zero-spread fixtures). A broker minimum that is still unmet rejects the stop; it is never widened to obtain an order.
- Python uses exact decimal fixture arithmetic. Loss-per-lot inputs are supplied in account currency. `fixture_stop_loss` is a deliberately simple linear scenario generator, **not an OrderCalcProfit replacement**. Actual MQL must query the broker calculation and reject unavailable/invalid results.
- Initial modeled stop loss is capped by **0.25% equity** and lot limits **0.01 base**, **0.03 basket**, **0.05 total**. Broker volume minimum never rounds risk up; step **0.001** is covered.
- The basket budget sums each position's **original entry to protective stop** full modeled loss plus candidate loss and an explicitly supplied nonnegative cost reserve, with total **≤35 account currency**. Floating profit never subsidizes this sum. Unknown costs reject; fixtures do not assert that a zero reserve applies to any real broker. A crossed stop also rejects. Already realized basket losses require a trustworthy ledger and remain an execution blocker until reconciled.
- State uses account equity, a fixed initial-equity reference, UTC day, daily limit **75** and fixed-initial drawdown **5%**. Assess a previous baseline breach before rolling the day forward. A halt remains latched through day change, equity recovery and restart; these fixtures expose no automatic reset operation.
- A valid prior-day record may undergo approved rollover. Missing state with exposure, malformed/future records or mismatched scope reject. Clean missing state may initialize only while flat in a first-ever explicit scope. A create-once scope marker precedes initial commit: missing state in an already bootstrapped scope rejects even when flat, and state without a matching marker rejects. Partial bootstrap/retry must not create a fresh baseline. A stale/incomplete transaction barrier always rejects.
- `MemoryStore` models an **abstract durable barrier written before commit**. Failed commit retains the barrier across reconstruction. If even the barrier write fails, the current action rejects; Python cannot guarantee evidence survives complete storage failure. Actual storage/media durability, write ordering and recovery must be verified on Windows. A test store passing is not proof that terminal global variables or files provide those semantics.

No fixtures enable the hard-coded trading lock, authorize trading, produce return figures, or satisfy a Windows acceptance gate.
