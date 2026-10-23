# Historical quote download — 2026-10-23

## Download completed; performance calculation blocked by source timestamps

Downloaded all 15 HistData Generic ASCII XAUUSD tick archives: 2023-10 through 2024-12. These include the fixed 2024 evaluation year, warmup and the extra local-month boundary needed by the published fixed-EST convention. Original ZIPs total **449,032,566 bytes** and contain **64,303,811 CSV rows** before UTC-window selection. Every ZIP was read fully for CRC validation and SHA256 recorded. Raw data remain private and unchanged.

Source: https://www.histdata.com/download-free-forex-data/ . Format: https://www.histdata.com/f-a-q/data-files-detailed-specification/ . The published format includes millisecond timestamps, bid and ask, and specifies fixed EST without daylight-saving adjustment. No login, account creation or payment was used.

## Reproducible source defects

| Monthly CSV | Row before reversal | Following row | Source timestamps |
| --- | ---: | ---: | --- |
| 202310 | 2,582,522 | 2,582,523 | 20231029 195959701 → 20231029 190000076 |
| 202410 | 4,494,119 | 4,494,120 | 20241027 195958047 → 20241027 190000061 |

The second reversal lies inside the fixed evaluation year. The converter correctly rejected the source. No valid normalized tick CSV, native indicator run, reference performance calculation or profit chart was produced. The dates alone do not establish a valid DST correction; sorting, adding an hour or deleting rows would change the time/sequence model without source evidence.

Dukascopy returned a real HTTP429 response pointing to its official requester-pays documentation; downloading stopped without changing route or enabling paid AWS access. Exness’s public XAUUSDm annual archive link returned HTTP200 to HEAD, but actual GET/Range reads timed out and the browser download did not complete. A HEAD response is not a completed dataset.

## Validation and limits

The local data checks passed **28/28** and reference execution tests **18/18**. Synthetic tests are not market returns. The source-aware reference code keeps coverage uncertainty separate from ZIP integrity and rejects failed quality reports. These local source changes have not yet been validated by a new Windows performance run.

Capital remains USD5,000, leverage 1:30 and all strategy/risk/cost assumptions remain frozen. Production trading locks remain closed. No merge or live trading occurred. Further performance work requires verified chronological/timebase evidence or another usable source; no data upload is required from the user at this checkpoint.
