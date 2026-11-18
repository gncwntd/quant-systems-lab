# Closed daily MT5 demo history

The history adapter exports up to 1,500 closed EURUSD daily bars from an existing user-configured MT5 demo terminal. It is a separate, one-shot read-only script; it neither places orders nor changes the continuous quote bridge or paper strategy.

This checkpoint assesses a historical source and feeds the existing **daily** reference engine. It does not validate the **minute** paper strategy: M1 history and better bid/ask/cost data are still required for that comparison. A daily bar's reported spread is not a complete historical bid/ask series.

## Compile and run

On an existing Linux/Wine installation:

```sh
python3 tools/prepare_mt5_bridge.py --script history --install
```

Use `--prefix` / `--terminal` for another configured installation, as in the [quote bridge guide](MT5_BRIDGE.md). Generated EX5 and compiler output stay under ignored local storage. The helper verifies a new artifact and a compiler log with zero errors/warnings.

In MT5:

1. Leave the chart running `QSLQuoteBridge` open.
2. Open a **separate EURUSD chart** using Market Watch → EURUSD → Chart Window.
3. Open View → Navigator, expand Scripts → QSLab. Refresh Scripts if needed.
4. Drag **QSLHistoryExport** onto the new chart. No Algo Trading/DLL permission is required.
5. Check Experts for `QSLab history: exported ... closed EURUSD D1 bars`.

Do not accept replacing the running quote script: cancel and select a separate chart. The history script has its own execution thread, but it may wait while MT5 downloads history. If fewer than thirty closed bars are ready, it publishes nothing and asks for a retry after synchronization. It exports whatever valid count MT5 returns, not a guaranteed 1,500 bars.

The export is one UTF-8 `QSLab/history.json` bundle under MT5 common files. A temporary file is closed before publication with FileMove. The script checks demo connectivity and unchanged server before publishing. It excludes the forming bar using `CopyRates(..., PERIOD_D1, 1, ...)` and records the current bar's server timestamp as an exclusion boundary. No account identifier, password or real account balance is exported.

## Assess, then explicitly import

```sh
python3 tools/run_lab.py inspect-mt5-history
```

This discovers one Wine common-file export and prints validated source metadata. `--file /path/to/history.json` selects another local file. Inspection does not write a research dataset or mutate paper state.

After source assessment, import explicitly:

```sh
python3 tools/run_lab.py inspect-mt5-history --import-data
```

This archives the exact raw bundle under an ignored `mt5-history/<sha256>.json` directory beside the database and saves normalized `date,close` observations with provenance as the latest daily research dataset. Existing datasets/runs are retained. It does not run a backtest, alter paper cash/exposure, reset a session or change strategy settings.

Select an isolated workspace with `--import-data --database .local/runtime/history-assessment.sqlite3`. Inspect metadata and label the source before comparing results. Keep raw market data and derived personal results outside public Git.

## Validation and interpretation

The reader caps input at 2 MB, accepts only the versioned EURUSD D1 demo schema and checks 30–1,500 bars against declared counts. It rejects duplicate/backward times or server-calendar dates, forming-bar timestamps, invalid OHLC bounds, non-finite prices, negative/non-integer volumes/spreads, malformed symbol precision and capture times more than two minutes in the future. Unexpected identity fields are not copied to output metadata.

The output records source server, capture UTC, requested/actual count, SHA-256, range, maximum calendar gap and reported spread range. Daily dates are decoded as **raw MT5 server-calendar labels**; the source timezone/day-boundary has not been independently verified. OHLC close price basis may be bid or last depending on the instrument/source, and is not relabeled as executable mid/ask.

Coverage, revisions, session boundaries, source rights and real execution costs remain assessment tasks. A partial-history export is not silently promoted to complete coverage. The bundle's recorded point/digits convert reported spread points to pips for descriptive inspection; the existing backtest cost assumptions are not automatically calibrated from that field.

## Restarting the existing workspace

The browser can close while the local server and MT5 script keep running. A computer/terminal shutdown stops acquisition. A normal MT5 restart does not restore scripts automatically: reattach the quote bridge or launch the terminal with [the credential-free startup configuration](../mt5/bridge-startup.ini). Start the Python server if it is not already listening; do not create a duplicate on the same port.

The paper database retains its account. On the first fresh quote after a long interruption, the existing engine records a gap and restarts SMA warm-up. It does not fabricate missing prices or fills. Check source freshness and the journal before interpreting retained equity as current.

## Official interfaces and checks

- [CopyRates and closed/forming positions](https://www.mql5.com/en/docs/series/copyrates)
- [MqlRates OHLC, volume and spread fields](https://www.mql5.com/en/docs/constants/structures/mqlrates)
- [MQL5 program execution and script threads](https://www.mql5.com/en/docs/runtime/running)
- [FileMove publication](https://www.mql5.com/en/docs/files/filemove)

Synthetic tests verify provenance, malformed/source/forming-bar rejection, OHLC ordering, limits, CLI inspection/import separation, raw bundle preservation and unchanged paper state. MQL compilation is checked locally with installed MetaEditor, not in hosted CI. Actual source export/import is a separate integration gate and must be verified before claiming historical broker-data access.
