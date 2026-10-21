# Official Windows compiler evidence — candidate workflow

No real MetaEditor compilation was run while authoring these scripts. A passing download/signature preflight is **not** a passing compile. PowerShell execution is **NOT RUN** until Windows Actions evidence exists. No MT5 Strategy Tester run is included.

The candidate scripts are checked in, but `.github/workflows/metaeditor-compile.yml` is **not present**. Only the Python/static `checks.yml` workflow currently exists. No automatic or manual Windows compile workflow is wired up. The steps below describe a proposed follow-up, not executed or available automation. No EULA acceptance, installation or compiler evidence is recorded. A reviewed Windows workflow must be added before any workflow instructions below can be used.

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

1. Record that consent in the development review. In a newly reviewed workflow, set `METAQUOTES_EULA_ACCEPTED` to `'true'`, and fill `REVIEWED_INSTALLER_SHA256` and `REVIEWED_SIGNER_THUMBPRINT` with the exact reviewed preflight values. Push that concrete change to the development branch. Alternatively use the matching manual dispatch inputs if available.
2. The workflow downloads again, requires the exact reviewed installer hash/certificate and a valid signature, then runs documented `/auto /path` on a fresh disposable Windows runner. A changed download rejects and requires a new preflight. No account, broker, MQL5 Community login or paid VM is configured.
3. The installer may auto-launch the terminal. Before installation the script blocks outbound networking for that installation's `terminal64.exe`; it stops any spawned instance and never directly launches the terminal. No broker session or trade is authorized. If firewall setup is unavailable, the script fails before installing.
4. The installed editor must have a valid Authenticode signature and the same subject as the reviewed installer. Compile the actual project together with its sibling include headers, using the installed standard library via `/include:<MQL5-root>`. Do not use `/s`, which is only a syntax check.
5. Compilation has a timeout. A new adjacent raw log, exactly one parseable `Result` summary, zero errors/warnings and a fresh nonempty EX5 are required. Unknown/localized log formats fail for manual review instead of being guessed. Reports include compiler file/product versions, process exit code, source/include manifest and hashes. The signature check or installer may fail on a hosted Windows Server runner; record that failure, not a compile result.
6. JSON and raw logs upload even on a failed job. Installer, installed MetaQuotes binaries and compiled EA binaries are not redistributed as artifacts. A compiled EX5 hash is evidence only; the EA execution lock stays false.

A compile result can establish compilation for the recorded source/compiler/library version only. It cannot establish protective order behavior, durable terminal storage, runtime restart recovery, backtest performance or live readiness.
