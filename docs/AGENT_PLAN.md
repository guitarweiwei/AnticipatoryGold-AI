# Six-agent implementation and review plan

User authorization: import supplied ZIP, develop on a separate branch, six agent roles, prioritize P0, run available tests and submit a PR without merging or enabling live trading. Login and material risk parameter changes require user confirmation.

Each implementation agent used a dedicated local git worktree/branch. Main integrated committed diffs sequentially. Independent risk reviewer did not implement the features under review.

| Role | Scope | Result |
|---|---|---|
| Strategy | read-only implementation review; docs/STRATEGY_SPEC.md | Actual heuristic semantics, units, unimplemented features and validation plan |
| MQL5 | MQL5/ only | Hard execution lock, fail-closed macro input, safer volume/caps, risk-check ordering and close logging |
| AI API | mac_ai/ only | Strict frozen contract, authentication, freshness, model validation, redacted audit, 62 mocked tests |
| Macro data | config/ only | Manual validated atomic publisher, provenance, canonical sample, 10 tests |
| Backtest | tests/ and CI only | Static safety checks, repeatable runner, Windows evidence scaffolding; no performance claims |
| Risk audit | read-only baseline and integrated code review | Release blockers and explicit containment assessment |

No file ownership conflict occurred during integration. The API contract file was not changed. Material new risk policies are proposed separately, not implemented. Main updated status/readme and decision/defect/test documents.

Available integrated tests passed: Python compileall, 6 static MQL5 source checks, 10 macro unit tests, 62 mocked API tests. Windows compilation/backtests not available. A Draft PR is appropriate while blockers remain; no release approval is claimed.
