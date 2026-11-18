# Paper event journal and accounting checks

The journal adds read-only inspection to the [streaming paper simulator](STREAMING_PAPER.md). It does not change the strategy, frozen engine hash, risk settings or simulated fills. Open `http://127.0.0.1:8765/#paper-journal` while the local server runs.

## Inspect events

Filter controls, signals, entries, exits, gaps, feed transitions, source changes and risk halts. Inspect shows the complete stored payload, including observed UTC time and available decision/fill fields. A signal event records its direction and originating closed server-minute timestamp; it does not contain a complete historical feature vector. The price buffer and stored candle window are bounded, so full historical strategy replay is not established by this journal.

Pages contain at most 25 events in the UI and 100 through the API. “Older events” uses an exclusive immutable event-ID cursor, so newly appended events do not shift the older page. The latest page refreshes every ten seconds; older pages stay fixed until explicitly refreshed. Filtering applies to the displayed events; the accounting check still uses the entire session audit.

The service reads state and audit cutoff together in a SQLite read transaction. It scans events in order with bounded working memory. Reconciliation currently scans the full session audit for each journal request; the first version is intended for a local research session, not a large multi-user archive.

## Reconstruct the account

The independent journal code reconstructs cash, one long position, paid commissions and realized P&L from entry/exit audit events. It uses the stored quantities/fill prices and frozen commission assumption, checking reported commissions, entry references and trade P&L. Open exposure is valued using the stored last bid minus configured exit slippage and estimated exit commission. The reconstructed account is compared with stored cash, equity, realized/open P&L, fees, position and closed-trade count, with small floating-point tolerance.

| Result | Meaning |
| --- | --- |
| Initial balance only | No entry exists; initial cash/account state matches. No fill was verified. |
| Fills reconciled | Recorded entry/exit accounting agrees with the stored account. |
| Accounting mismatch | A numeric or position comparison failed; details identify the failed checks. |
| Invalid audit | Event structure or entry/exit ordering prevented a conclusion. |

Checks use stored data, which may be stale. They do not verify feed truth, signal correctness, fair execution, or profitable trading. An accounting badge is independent of the streaming monitor's price/worker freshness. Mismatch/invalid results are diagnostic; this reader does not silently edit records, fix balances or alter the running strategy.

## Full audit exports

The dashboard's **Full audit JSONL** and **Full audit CSV** include all session audit events through a captured event ID, rather than just the bounded recent events/trades in the existing snapshot export. Event filters and visible pages do not limit these downloads. The rolling 10,000-price-snapshot buffer is separate and is not included.

Each export contains:

1. A session header with frozen config/version/engine hash, source, captured account, reconciliation result and event cutoff/count.
2. Every audit record through that cutoff in increasing ID order.
3. An `end` record with the exported event count and cutoff.

Verify the end record and its count against the header before treating a download as complete. A network/storage failure can interrupt an HTTP download after its headers have been sent. JSONL has `type=session/audit/end`; CSV has `record_type=session/audit/end`. CSV retains full event payloads in `event_json` and header metadata in `session_json`; text cells that might be interpreted as spreadsheet formulas are escaped, while numeric negative P&L stays numeric.

Exports read immutable audit IDs in batches of 250, releasing live database read locks before writing to the client. This avoids holding a long read transaction during a slow download. Consistency relies on the application's append-only audit contract; out-of-band database edits are unsupported. Files, market observations and account records remain local and outside Git.

## API and verification

- `GET /api/paper/journal?before=0&limit=25&kind=all` — bounded page, session/account summary, totals and reconciliation.
- `GET /api/paper/journal/export?format=jsonl` or `format=csv` — full cutoff audit download.
- The earlier `GET /api/paper/export` remains a bounded current-state snapshot.

The existing loopback Host restriction applies. Cursor/limit/kind/format inputs are validated. The new routes perform no mutations and accept no trading or credential input.

Tests verify initial/open/closed account checks, altered balances/commissions, malformed audit rejection, cursor stability during appends, filtering, complete exports beyond the UI page limit, exclusion of later events, CSV formula protection, query bounds and HTTP behavior. Synthetic audit/fill fixtures remain isolated from the real local workspace.
