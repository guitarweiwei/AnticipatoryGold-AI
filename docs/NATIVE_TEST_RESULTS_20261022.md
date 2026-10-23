# Native MQL fault-test results — 2026-10-22

**50/50 native cases passed in actual offline MT5 build 6274, with zero sender attempts.** Production EA and native script were both compiled by signed MetaEditor 5.0.0.6274 with **0 errors / 0 warnings**. This is production-function fault-test evidence, not EA lifecycle, broker-fill or historical performance evidence.

## Actual run and identity

- Final Windows [run 39709650044](https://github.com/guitarweiwei/AnticipatoryGold-AI/actions/runs/39709650044), source commit `8c4533da21059318afe8eb36d1a80acd02ff0df0`; total run 1m32s.
- Downloaded artifact ZIP SHA256 `1a1ce3cf10eb1c9d3489e322eea9cc069010b358c08fbbca06448a476f80ca45`, matched to Actions.
- Native script EX5 SHA256 recorded at compilation and independently checked against the deployed-file hash by the Windows wrapper: `EAA681B7CE3E5226419A728AFC1943D5B10C44DF42FD58BBA8265BB050BB16FF`. EX5 is not redistributed; the auditor cannot rehash that unavailable binary independently.
- Native compiled source bytes SHA256 `4D83E143513FCFE15D64B4FCBF087C35653E235BE73524C657A2C6D4194E8F9E`; Windows checkout uses CRLF. Included production main and lifecycle hashes map exactly to the frozen LF source hashes below.
- Native JSONL SHA256 `FF1BAE2687D842CA3928FA31F32EC4BFED29F589F574BAFABB79EA3622B1C2A3`.
- The terminal loaded only `Scripts/AnticipatoryGoldNative/AnticipatoryGold_NativeTests.ex5`; production events are renamed, never registered/called by the script. Production EA was compiled, not deployed or run. No account supplied; firewall and terminal exit were verified.
- Native startup 02:09:08.1786455Z; exit confirmation/report 02:09:11.3173368Z. Terminal log shows script loaded, script-triggered shutdown with code 7, exit/shutdown 7. Success is established by complete case output, not by assuming process exit zero. Requested Experts/live-trading/DLL settings are not independent proof of each applied setting.

## Executed scope

| Coverage | Actual observation and boundary |
|---|---|
| Native number/date/indicator-sentinel parsers | Real production functions reject malformed values; scalar cases do not execute real indicator/history feeds. |
| Macro CSV2 | Actual sandbox reads, fresh/900s/901s/old-source/future/calendar/news/schema/invalid-row cases; clock and bar identities are fixed test adapters. No real macro provenance is authenticated. |
| Journal persistence and reload | Actual write/flush/read/move, truncated/checksum/orphan/missing files, unresolved OPEN/CLOSE intent halt barriers and duplicate consumed-bar refusal. Reload occurs within one process, not an actual crash/restart. |
| File publication fault | Real exclusive `.tmp` handle makes production `PublishRecord` fail; observed MQL error **5004**. This does not prove host power-loss durability or every caller's halt path. |
| Fill-result veto | Synthetic PARTIAL/TIMEOUT/unknown retcodes for OPEN/CLOSE directly call production verifiers. Getter counters require retcode/order/deal reads 1/0/0; DONE-with-real-zero-order control requires 1/1/0. Intent and stored journal remain unchanged. No broker fill, network timeout, full correlated fill or caller halt is exercised. |
| Containment | Production entry gate false, ordinary-terminal research guard false, future costs unknown/veto, disabled AI rejects BUY/SELL/aliased output, locked ProcessEntry does not invoke sender. Sentinel send attempts=0; outside-prefix file opens=0. |

Expected IDs are in `MQL5/Tests/Native/expected_cases.json`; actual original JSONL, both compiler logs, per-source/library manifests, terminal logs, synthetic file fixtures and original byte hashes are preserved in [the evidence bundle](../tests/windows/evidence/20261022-native-tests.json). The bundle also retains earlier actual run 39708708759 (42/42), whose narrower harness is historical. The unexecuted intermediate 49-case source is not assigned an execution result. Acceptance groups in [NATIVE_TEST_ACCEPTANCE.md](NATIVE_TEST_ACCEPTANCE.md) beyond these concrete cases remain NOT RUN.

## Python and API evidence

The final local `tests/run_checks.py` actually passed **188** checks: 70 source/reference/harness-structure unittest cases, 15 macro cases and 103 Python API cases. Six API cases use a real localhost HTTP server and unchanged HTTPX transport. They exercise valid approval, malformed outer/content JSON, invalid schema/contrary direction and a genuine socket read timeout returning HOLD. Only the test timeout configuration is shortened to 0.05s; production remains 12s. This is Python transport evidence, not MQL5 network handling or production deadline timing. One existing TestClient deprecation warning remains.

## Unchanged controls and remaining work

Production canonical LF hashes remain main `669f2ab269e6451bbdd32bb0f8bc272bf93b6b5c49ce4edcbd638ef521145e0d` and lifecycle `3d11d861a3c6f1402cabf631bf8881bb4c3e3dac5118716bda74e676f29062fd`. All 35 original inputs, approved 2x closed-M5 ATR, basket/daily/drawdown/lot limits and every execution/cost veto remain unchanged. No production code was edited for these tests.

EA-side online timeout/JSON parsing remains NOT IMPLEMENTED: GetAISignal is an unconditional veto without WebRequest. Actual process crash/restart, broker partial fills and correlated fill/SL/history/ledger behavior, true data authenticity, prospective cost bounds, historical replay/performance and live/demo trading remain NOT RUN. Native all-green is insufficient to release trading or merge.

Step 3 deliverables are [the historical backtest plan](HISTORICAL_BACKTEST_PLAN.md) and [non-executable planning manifest](../config/backtest_research_manifest.template.json). They specify data availability/vintages, bid/ask/UTC/contracts/costs, sample splitting and stress evidence. Broker, deposit/currency/leverage, licensed data, costs, replay adapters and economic acceptance remain unresolved. The manifest deliberately stays BLOCKED_NOT_RUN/false/null. No tester-order unlock, strategy tester run, important risk change or merge was performed.
