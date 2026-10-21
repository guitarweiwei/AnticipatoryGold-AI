# Actual Windows MetaEditor evidence — compile blocked

The user explicitly accepted the MetaQuotes EULA on 2026-10-21 and authorized official installation on a disposable Windows runner **only for MetaEditor compilation**. The signed compiler was installed and actually invoked. The latest [run 39652983425](https://github.com/guitarweiwei/AnticipatoryGold-AI/actions/runs/39652983425), source commit `e0a36888c28c8b422b6421e0b8a8557c87530bad`, **FAILED**:

```text
AnticipatoryGold_AI_v1.mq5(8,10) : error 106: file 'Include\Trade\Trade.mqh' not found
Result: 1 errors, 0 warnings
```

The compiler process returned 0, but the actual log reports an error; process exit alone is never success. No EX5 hash was produced. This is an installed-dependency failure, not evidence that all EA source errors have been resolved. MT5 backtest and EA execution remain **NOT RUN**. All trade locks, original inputs and risk limits are unchanged.

## Identity and preserved evidence

- Compiler file/product version: `5.0.0.6274`.
- Compiler SHA256: `2506302A69DD673391A3F586CEF91DDADA16B3EEA03D902D5A4E608E8161EBA3`.
- Installer SHA256: `C8C0A73F86C58974DF62FB48F8256A099D6698518CF2DEFC2B3F169773729E22`.
- Installer and editor Authenticode: Valid; subject `CN=MetaQuotes Ltd., O=MetaQuotes Ltd., S=Lemesos, C=CY`.
- Reviewed certificate thumbprint: `5A64A7AED24C33DED342D01D01FA5286F06DA6DC`.
- Latest artifact ZIP SHA256: `c6ee91ec73a57eba763cffff47c3db9feadb2c9959e4148f8f07117c6beb6af9`, independently downloaded and matched to Actions' displayed digest.
- The report objects, source/library manifests, decoded compiler logs and original artifact/log digests from six attempts are retained in [evidence/20261021-compile-attempts.json](evidence/20261021-compile-attempts.json). Values are preserved; JSON whitespace is normalized. Original compiler logs are UTF-16 with BOM; the readable [latest log](evidence/20261021-metaeditor.log) is UTF-8/LF. The aggregate retains the original decoded CRLF text and original byte digest.

Windows checkout converted MQL text from LF to CRLF. Main source canonical LF SHA256 `669f2ab269e6451bbdd32bb0f8bc272bf93b6b5c49ce4edcbd638ef521145e0d` becomes compiled-byte SHA256 `97a1c7e75b7681ed941700595e08b2f6bcfce6ac74733f896fca06b7785a72c5`; lifecycle include canonical `3d11d861a3c6f1402cabf631bf8881bb4c3e3dac5118716bda74e676f29062fd` becomes `33947aa285aebaff1eb0601f2ea48c8c8531820ee6b3e1d6895b3f5d4cc10f57`. Both mappings were byte-hashed, not assumed. Source content is unchanged.

## Workflow and actual limitations

The workflow first runs a no-installation download/signature job. The separate installation/compile job depends on it and activates only on a development push containing `[metaeditor-compile-authorized]`; ordinary pushes and manual dispatch skip installation. Contents permission is read-only, checkout does not persist credentials, Actions are pinned to reviewed upstream release commits, and the artifact whitelist uploads only named JSON and compiler log files for seven days. Vendor binaries, vendor header source and EX5 are not redistributed.

Before installer startup, all three Windows firewall profiles are enabled and checked, the firewall service is checked, and the effective outbound Block rule and exact terminal program path are verified. Failed checks stop installation. An installer-spawned terminal at that exact installation is stopped; the script never directly starts terminal/tester. Editor signature validity and the reviewed installer publisher are required. Only the signed editor was initialized to look for its own portable standard library. Alternate library lookup requires exactly one `origin.txt` matching this installation. No vendor header was fabricated or borrowed from an unrelated installation.

The first four installation/preparation attempts never invoked the compiler and retain `compile=NOT RUN`. A fifth genuine compiler invocation produced the same missing-header error, but the wrapper failed to parse its CRLF Result line; its original numeric fields remain null in the aggregate. The CRLF regex was fixed, then the sixth real invocation above independently recorded `errors=1`, `warnings=0`, `status=FAILED`. Missing-library diagnostics were empty in the checked per-user MetaQuotes roots. Installation exit 1 is retained without assigning undocumented installer semantics; actual signed editor/files and compiler output determine what occurred.

The current diagnostic path can invoke the actual compiler with missing headers to obtain a real failure log. Success still requires exactly one parseable Result line, zero errors and warnings, a fresh nonempty EX5, and real installed Trade.mqh plus a captured vendor-library hash manifest. A raw compiler error or missing vendor library cannot be marked PASSED.

## Proposed next action — NOT authorized or executed

The current user instruction says **only MetaEditor compilation**. An additional direct launch of MT5 is outside that scope. [pending_offline_bootstrap.ps1](pending_offline_bootstrap.ps1) is a reviewable proposal only: no workflow references it, and its default switch stops before any action. Windows syntax and runtime are NOT RUN for this proposal.

If separately authorized, it would initialize only the reviewed signed `terminal64.exe` in this disposable temporary installation, with a verified outbound network block, no supplied account, no Expert/script startup, and config `[Experts] Enabled=0 / AllowLiveTrading=0 / AllowDllImport=0`. It refuses an existing instance at that path and an installation account database, allows up to 30 seconds of initialization, then stops and verifies exit within a bounded cleanup period. It supplies no tester section and never installs the project EA into the terminal. Config values are requested safeguards, not a claim of observed platform settings. The initialization may still fail to generate the library; only actual file evidence followed by a new compiler run could resolve this blocker. No backtest, order unlocking or merge would be authorized.

Official references:

- Download: https://www.metatrader5.com/en/download
- Installer and automatic flags: https://www.metatrader5.com/en/terminal/help/start_advanced/installation
- EULA accepted by user: https://www.metaquotes.net/licenses/terminal/mt5
- Data directories/origin and configuration keys: https://www.metatrader5.com/en/terminal/help/start_advanced/start
- Compiler flags: https://www.metatrader5.com/en/metaeditor/help/beginning/integration_ide

Compilation success, if later obtained, would establish compilation only, not runtime order safety, restart durability, backtest performance or trading readiness.
