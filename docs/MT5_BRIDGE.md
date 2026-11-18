# Read-only MT5 demo quote bridge

MT5 script → common local JSON snapshot → loopback `/api/quotes` → dashboard monitor.

This adapter is deliberately separate from the daily CSV/ECB research engine. It reads EURUSD demo quotes once per second; it does not place orders, collect credentials, archive every tick, or supply a historical bid/ask backtest. It exports server name and demo/connection flags, never account identifiers, balances or passwords. It stops exporting valid prices when the account switches away from demo mode.

## Existing Linux/Wine installation

Requires an installed, user-configured MT5 demo terminal and Wine on PATH. No Python MT5 package, paid API, DLL access or Algo Trading permission is needed. The helper neither installs Wine/MT5 nor creates or logs into an account.

```sh
python3 tools/prepare_mt5_bridge.py --install
```

The default prefix is `~/.mt5`. Use `--prefix` and `--terminal` for a different existing prefix and installation/data folder. The selected terminal folder must contain both `MetaEditor64.exe` and `MQL5/Scripts`. With separate MT5 data folders, compile manually in MetaEditor and copy the source/binary into the actual data folder shown by MT5's **File → Open Data Folder**.

The helper compiles a staged source copy in ignored `.local/mt5-bridge/build/`, requires a new EX5 artifact and a compiler log reporting zero errors/warnings, then optionally copies the verified source and binary into `MQL5/Scripts/QSLab`. Source SHA-256 is printed. Generated binaries and compiler logs stay outside Git. Without `--install`, only local compilation occurs.

In MT5, refresh **Navigator → Scripts**, then attach **QSLab/QSLQuoteBridge** to an EURUSD chart. Keep MT5 and the script running. A closed browser does not stop the script. Removing the script or closing MT5 stops updates; the API expires its heartbeat. Reattach after a normal terminal restart.

Alternatively, after closing the existing terminal normally, start it with the reviewed [startup configuration](../mt5/bridge-startup.ini):

```sh
QSL_STARTUP_CONFIG="$(WINEPREFIX="$HOME/.mt5" winepath -w "$PWD/mt5/bridge-startup.ini")"
WINEPREFIX="$HOME/.mt5" wine "$HOME/.mt5/drive_c/Program Files/MetaTrader 5/terminal64.exe" "/config:$QSL_STARTUP_CONFIG"
```

This uses the terminal's existing session and opens an EURUSD M1 chart with the script. It contains no account credentials or trading-permission changes. Do not force-close a terminal that is performing other work.

## Dashboard and freshness

```sh
python3 tools/run_lab.py serve
```

The reader discovers a single `QSLab/quote.json` under the Wine prefix's MetaQuotes common files. If discovery is ambiguous or another prefix is used, select the exact export with `serve --quote-file /path/to/quote.json`. This local path is not returned by the API. Native Windows users can compile/attach the MQL5 source in their own installation and select its common export explicitly; the compilation helper is Wine-specific.

The script closes a UTF-8 temporary file before publishing it with `FileMove`. The reader caps input at 8 KiB, validates schema/types, positive finite prices, ask ≥ bid, EURUSD and demo mode, and returns only allowlisted fields. The HTTP endpoint is GET-only, with the existing loopback/Host boundary. Missing, corrupt, disconnected and non-demo sources expose no prices.

- **Fresh:** bridge heartbeat is at most five seconds old and estimated quote age is at most fifteen seconds.
- **Stale:** expired heartbeat hides cached prices. With a current heartbeat but an old quote timestamp, values remain visibly inactive and labeled stale.
- **Clock error:** a future heartbeat or inconsistent negative server-age estimate is rejected. Synchronize the computer clock before diagnosing the feed.
- **Offline:** the browser clears values if the local API fails or exceeds the three-second request timeout.

Heartbeat is UTC observation time. `tick_time_msc` is the raw MT5 server timestamp, not relabeled as UTC. Approximate quote age uses `TimeTradeServer() - tick.time_msc` plus elapsed time since the export. `TimeTradeServer()` depends on the computer clock. These checks are operational heuristics, not a latency measurement or independent proof of exchange time. EUR/USD spread in pips is `(ask - bid) / 0.0001`; it does not include commission, slippage or swaps.

The monitor polls once per completed request plus one second. It does not change existing datasets, experiment records or backtest spread assumptions. The separate [streaming paper worker](STREAMING_PAPER.md) now consumes snapshots and retains a rolling local buffer independently of browser polling; the bridge itself still only publishes its latest file. A vendor demonstration server must not be treated as a verified executable broker feed or a licensed-broker relationship.

## Verification

For closed daily source assessment, the separate [MT5 history exporter](MT5_HISTORY.md) can run on another chart. Do not replace the continuous bridge script with that one-shot exporter.

Python unit/integration tests exercise invalid data, stale/disconnected/real-account rejection, clock errors, spread calculation, API isolation and publication rules. CI runs these tests and JavaScript syntax checks. MQL5 compilation needs an installed MetaEditor and is verified locally; hosted CI does not compile MQL5. The source guard against trading APIs is a regression check, not a substitute for source review.

## Official interfaces

- [SymbolInfoTick](https://www.mql5.com/en/docs/marketinformation/symbolinfotick)
- [MqlTick structure](https://www.mql5.com/en/docs/constants/structures/mqltick)
- [FileOpen and common files](https://www.mql5.com/en/docs/files/fileopen)
- [FileMove publication](https://www.mql5.com/en/docs/files/filemove)
- [TimeTradeServer clock behavior](https://www.mql5.com/en/docs/dateandtime/timetradeserver)
- [MetaEditor command-line compiler](https://www.metatrader5.com/en/metaeditor/help/beginning/integration_ide)
- [Terminal startup configuration](https://www.metatrader5.com/en/terminal/help/start_advanced/start)
