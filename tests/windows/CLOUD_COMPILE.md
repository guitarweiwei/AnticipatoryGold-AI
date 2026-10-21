# Official Windows compiler evidence — preflight workflow

No real MetaEditor compilation was run while authoring these scripts. A passing download/signature preflight is **not** a passing compile. Windows PowerShell syntax parsing and download/signature preflight have now run successfully; installation and compiler execution have not. No MT5 Strategy Tester run is included.

`.github/workflows/metaeditor-compile.yml` now wires the candidate scripts to a disposable `windows-2022` runner. It runs on relevant development-branch pushes (or manual dispatch when available) and **only downloads and checks signatures**. The invocation explicitly passes `-AcceptMetaQuotesEula:$false`; there is no installation input, secret or enabled compile job. It parses both PowerShell scripts on Windows, requires a valid signature and a report recording EULA false / compile NOT RUN / backtest NOT RUN, and uploads only `preflight-result.json` for seven days. Checkout and upload actions are pinned to reviewed upstream release commits; repository permissions are read-only and checkout does not persist credentials. A green workflow means the preflight contract passed, never that the EA compiled.

Observed Windows run: [39602184477](https://github.com/guitarweiwei/AnticipatoryGold-AI/actions/runs/39602184477), source commit `26f0acb1da753b6e4822c17ea5c5363b72b36f48`, succeeded. Both PowerShell files parsed on Windows; the download/signature contract passed. The report values are retained unchanged (CRLF normalized to LF for repository text) in `evidence/20261021-preflight/preflight-result.json`.

- Installer SHA256: `C8C0A73F86C58974DF62FB48F8256A099D6698518CF2DEFC2B3F169773729E22`
- Authenticode: `Valid`
- Subject: `CN=MetaQuotes Ltd., O=MetaQuotes Ltd., S=Lemesos, C=CY`
- Certificate thumbprint: `5A64A7AED24C33DED342D01D01FA5286F06DA6DC`
- Downloaded artifact ZIP SHA256: `c6b4747ac859f8789e7821c898439d3692ff7d1996c407c30e9570d230be00a8` (matches Actions' displayed artifact digest).
- EULA accepted: `false`; installation, actual MetaEditor compilation and MT5 backtest: **NOT RUN**.

The certificate subject identifies MetaQuotes Ltd.; a later installer download must still match the exact reviewed hash/certificate. Installation remains blocked pending explicit user acceptance of the linked EULA. No MQL5 source, original risk parameter or trading gate changed in this preflight work.

## Safe first run

The default run downloads the Windows installer linked from MetaQuotes' official download page, records SHA256 and Windows Authenticode validity, certificate subject and thumbprint, then stops. It installs nothing and reports **COMPILE NOT RUN**. Review the signature and verify the subject belongs to MetaQuotes before authorizing installation. The report does not assume an unobserved publisher name or certificate fingerprint.

- Official download page: https://www.metatrader5.com/en/download
- Windows link observed there: https://download.terminal.free/cdn/web/metaquotes.ltd/mt5/mt5setup.exe
- Official current EULA: https://www.metaquotes.net/licenses/terminal/mt5
- Installer documentation: https://www.metatrader5.com/en/terminal/help/start_advanced/installation
- Compiler flags: https://www.metatrader5.com/en/metaeditor/help/beginning/integration_ide
- Portable editor mode: https://www.metatrader5.com/en/metaeditor/help/beginning/open

The installer documentation describes `/auto /path:"..."` and requires agreement to the EULA. No unofficial `/silent`, `/verysilent`, `/extract`, or license-bypass options are used. No primary-source-supported standalone compiler/archive was found in this research; the workflow uses the official installer, not third-party repackaging.

## Approved follow-up

Only after explicit user acceptance of the official EULA for the temporary installation:

1. Record explicit consent in the development review. Add and review a separate install/compile job which invokes `cloud_compile.ps1 -AcceptMetaQuotesEula` with `ApprovedInstallerSha256` and `ApprovedSignerThumbprint` set to the exact reviewed preflight values. Push that concrete change to the development branch. The current workflow has no installation switch or dispatch inputs; it cannot perform this follow-up.
2. The workflow downloads again, requires the exact reviewed installer hash/certificate and a valid signature, then runs documented `/auto /path` on a fresh disposable Windows runner. A changed download rejects and requires a new preflight. No account, broker, MQL5 Community login or paid VM is configured.
3. The installer may auto-launch the terminal. Before installation the script blocks outbound networking for that installation's `terminal64.exe`; it stops any spawned instance and never directly launches the terminal. No broker session or trade is authorized. If firewall setup is unavailable, the script fails before installing.
4. The installed editor must have a valid Authenticode signature and the same subject as the reviewed installer. Compile the actual project together with its sibling include headers, using the installed standard library via `/include:<MQL5-root>`. Do not use `/s`, which is only a syntax check.
5. Compilation has a timeout. A new adjacent raw log, exactly one parseable `Result` summary, zero errors/warnings and a fresh nonempty EX5 are required. Unknown/localized log formats fail for manual review instead of being guessed. Reports include compiler file/product versions, process exit code, source/include manifest and hashes. The signature check or installer may fail on a hosted Windows Server runner; record that failure, not a compile result.
6. JSON and raw logs upload even on a failed job. Installer, installed MetaQuotes binaries and compiled EA binaries are not redistributed as artifacts. A compiled EX5 hash is evidence only; the EA execution lock stays false.

A compile result can establish compilation for the recorded source/compiler/library version only. It cannot establish protective order behavior, durable terminal storage, runtime restart recovery, backtest performance or live readiness.
