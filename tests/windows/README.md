# Windows evidence collection — NOT RUN

Linux Python/static checks cannot establish that MQL5 compiles or that a strategy is profitable. All compilation, tester metrics and terminal resilience scenarios below remain **NOT RUN** until actual Windows evidence is reviewed.

1. Use a dedicated research MT5 installation with no broker credentials. Keep Algo Trading disabled. Copy the EA to its `MQL5/Experts` folder. Record source commit/hash and MetaEditor/MT5 builds.
2. Run the compiler script from PowerShell, supplying absolute paths:

   ```powershell
   .\tests\windows\compile.ps1 -MetaEditor 'C:\ResearchMT5\metaeditor64.exe' -Source 'C:\ResearchMT5\MQL5\Experts\AnticipatoryGold_AI_v1.mq5' -IncludeRoot 'C:\ResearchMT5\MQL5' -EvidenceDirectory 'C:\ResearchEvidence\compile-new'
   ```

   Inspect the real log for zero errors and review every warning. Process success alone is insufficient. Retain the log and source hash. This script does not launch a test. It copies the complete sibling `.mq5`/`.mqh` source tree to a fresh evidence directory, uses the documented `/log` adjacent-log option, requires an unambiguous zero-error/zero-warning compiler Result line and a newly generated nonempty EX5, and records source/compiler/output hashes and compiler versions. Exit code alone never establishes success.
3. Verify the source refuses initialization outside Strategy Tester, and that order/close paths have the tester-only guard. Do not test this on a logged-in real account.
4. **Current P0 restriction:** `EntryRiskPolicyApproved()` is hard-coded false. Every new order is blocked even in Strategy Tester. Any baseline run now must be labeled non-trading diagnostics; no strategy-performance conclusion is possible. D1/D2 source implementations now exist, but prospective broker costs, actual-fill/SL verification, durable pending-order intent, real compilation and human review remain prerequisites for execution tests. Do not change this lock to obtain results.

   For future approved execution tests, in Strategy Tester, select one layer and online AI disabled. Changing these **test-only** settings does not change committed defaults. Export the exact `.set` and tester configuration; attach symbol contract details (digits, tick size/value, lot min/max/step, stops/freeze levels, account currency and netting/hedging mode).
5. Reserve unseen dates before tuning. Select fixed training, validation and final holdout windows and walk-forward splits; never tune on the final holdout. Cover trend, range and news/high-volatility regimes.
6. Select real ticks where available. Record actual data coverage/quality, server time zone, spread, commission and swap assumptions. Test slippage and doubled spreads separately; state limitations when the tester cannot model a cost or outage faithfully.
7. Macro data must be point-in-time aligned. The current single-row snapshot is unsuitable for historical replay. Use macro disabled for a clearly labeled baseline until a historical adapter exists. Never claim AI uplift: the EA's online AI path is deliberately unavailable; archived, time-aligned decisions and a separately reviewed replay adapter are required.
8. Export HTML/XML tester report, journal and configuration for each run. Copy `evidence_template.json` per run, replace only fields backed by evidence, and leave unavailable metrics `null` with status **NOT RUN**. Compare rules-only, AI-filtered and grid variants only on identical dates/costs; AI/grid rows remain NOT RUN until their gates pass. Two/three-layer tests require prior baseline/risk approval.
9. Record gap-through-stop, order rejection, close/partial-close failure, invalid volume, missing/stale/future macro, API timeout/malformed response, duplicate signal and restart scenarios. Unimplemented risk controls are open blockers, not passing tests. The current tester-only restriction prevents any demo/live readiness claim.

Do not commit personal identifiers, broker credentials or unredacted terminal journals. Store sanitized evidence alongside commit hashes. A reviewer must assess expectancy, profit factor, drawdowns (balance, equity and floating), worst basket, average win/loss, exposure, trade count and cost/parameter sensitivity; no metric is currently available.

Stage 2 adds a required local tester run-scope/UTC declaration and persistent state files. Follow MQL5/STAGE2.md; independent passes must not share scopes, and optimization is explicitly refused. Preserve evidence files for restart/fault tests; do not delete state to clear a halt. Copy the complete MQL5 project tree for compilation. No actual Windows scope provisioning or test has been performed here.
