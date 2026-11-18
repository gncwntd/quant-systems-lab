"""Read-only audit inspection and independent paper-account reconciliation."""

from collections import Counter, deque
import csv
from datetime import datetime, timezone
import io
import json
import math

KINDS = {'all', 'control', 'signal', 'entry', 'exit', 'gap', 'feed', 'halt', 'source'}


def decode_event(raw):
    try:
        value = json.loads(raw)
        observed = value.get('observed_utc') if isinstance(value, dict) else None
        if (isinstance(value, dict) and value.get('kind') in KINDS - {'all'}
                and type(observed) in (int, float) and math.isfinite(observed) and observed > 0):
            return value
    except (ValueError, TypeError):
        pass
    return dict(kind='invalid', observed_utc=None, message='Unreadable audit event; inspect the private database backup.')


def reconcile(state, rows):
    """Rebuild cash/exposure from audit fills, without calling the simulation engine."""
    config = state['config']
    cash, realized, fees = config['capital'], 0.0, 0.0
    position = None
    entries = exits = 0
    errors = []
    counts = Counter()

    def check(name, actual, expected):
        if (type(actual) not in (int, float) or not math.isfinite(actual)
                or not math.isclose(actual, expected, abs_tol=1e-6, rel_tol=1e-10)):
            if len(errors) < 30:
                errors.append(name + ' does not reconcile.')

    for _, raw in rows:
        record = decode_event(raw)
        kind = record['kind']
        if kind == 'invalid':
            raise ValueError('Invalid audit event.')
        counts[kind] += 1
        if kind == 'entry':
            entries += 1
            if position is not None:
                raise ValueError('Audit contains overlapping long entries.')
            units = config['units']
            price = record['price']
            fee = units * price * config['commission_bps'] / 10000
            check('Entry commission', record['fee'], fee)
            position = dict(units=units, price=price, fee=fee, observed_utc=record['observed_utc'])
            cash -= units * price + fee
            fees += fee
        elif kind == 'exit':
            exits += 1
            if position is None:
                raise ValueError('Audit contains an exit without an entry.')
            units, price = record['units'], record['exit_price']
            check('Exit quantity', units, position['units'])
            check('Exit entry price', record['entry_price'], position['price'])
            check('Exit entry time', record['entry_utc'], position['observed_utc'])
            fee = units * price * config['commission_bps'] / 10000
            pnl = units * (price - position['price']) - position['fee'] - fee
            check('Round-trip fees', record['fees'], position['fee'] + fee)
            check('Trade net P&L', record['net_pnl'], pnl)
            realized += pnl
            fees += fee
            cash += units * price - fee
            position = None
    unrealized = 0
    equity = cash
    if position:
        quote = state.get('last_quote')
        if not quote:
            raise ValueError('Open exposure has no stored valuation quote.')
        exit_price = quote['bid'] - config['slippage_pips'] * .0001
        exit_fee = position['units'] * exit_price * config['commission_bps'] / 10000
        equity += position['units'] * exit_price - exit_fee
        unrealized = position['units'] * (exit_price-position['price']) - position['fee'] - exit_fee
    for name, expected in dict(cash=cash, equity=equity, realized_pnl=realized,
                               unrealized_pnl=unrealized, fees=fees, closed_count=exits).items():
        check(name, state[name], expected)
    if (state['position'] is None) != (position is None):
        errors.append('Open position presence does not reconcile.')
    elif position:
        for key in ('units', 'price', 'fee', 'observed_utc'):
            check('Open position ' + key, state['position'][key], position[key])
    status = 'mismatch' if errors else 'passed' if entries else 'initial_balance'
    return dict(status=status, entries_checked=entries, exits_checked=exits,
                expected=dict(cash=cash, equity=equity, realized_pnl=realized,
                              unrealized_pnl=unrealized, fees=fees, net_pnl=equity-config['capital']),
                errors=errors, counts=dict(counts),
                note='Accounting consistency only; stored prices may be stale. This does not verify signal quality or broker execution.')


def read_journal(store, before=0, limit=25, kind='all'):
    if type(before) is not int or not 0 <= before <= 2**63-1:
        raise ValueError('before must be a nonnegative SQLite event ID.')
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('limit must be between 1 and 100.')
    if kind not in KINDS:
        raise ValueError('Unknown audit event kind.')
    with store.connect() as db:
        db.execute('BEGIN')
        row = db.execute('SELECT state FROM paper_state WHERE id=1').fetchone()
        if not row:
            raise ValueError('No paper session exists.')
        state = json.loads(row[0])
        upper = db.execute('SELECT COALESCE(MAX(id),0) FROM paper_audit WHERE session_id=?', (state['id'],)).fetchone()[0]
        page = deque(maxlen=limit+1)
        matching = 0
        def rows():
            nonlocal matching
            for event_id, raw in db.execute('SELECT id,payload FROM paper_audit WHERE session_id=? AND id<=? ORDER BY id', (state['id'], upper)):
                payload = decode_event(raw)
                if kind == 'all' or payload['kind'] == kind:
                    matching += 1
                    if not before or event_id < before:
                        page.append(dict(id=event_id, event=payload))
                yield event_id, raw
        try:
            result = reconcile(state, rows())
        except (ValueError, TypeError, KeyError, OverflowError):
            # Never render a positive reconciliation badge for an incomplete/broken audit.
            # Re-read the bounded page so a malformed fill cannot hide later records.
            page.clear()
            matching = 0
            counts = Counter()
            for _, raw in rows():
                counts[decode_event(raw)['kind']] += 1
            result = dict(status='invalid_audit', entries_checked=0, exits_checked=0,
                          errors=['Audit structure could not be reconciled.'], counts=dict(counts), expected=None,
                          note='No accounting consistency conclusion is available.')
    selected = list(reversed(page))[:limit]
    account_keys = ('cash', 'equity', 'realized_pnl', 'unrealized_pnl', 'fees', 'position',
                    'closed_count', 'last_observed_utc', 'last_poll_utc', 'feed', 'enabled', 'halted')
    return dict(session={key: state[key] for key in ('id', 'mode', 'version', 'engine_sha256', 'config', 'created_utc', 'source')},
                account={key: state[key] for key in account_keys},
                captured_utc=datetime.now(timezone.utc).isoformat(), audit_through_id=upper,
                reconciliation=result, total_records=sum(result['counts'].values()),
                filtered_records=matching, kind=kind, records=selected,
                next_before=selected[-1]['id'] if len(page) > limit else None)


def audit_batches(store, session_id, through):
    """Immutable audit IDs establish a cutoff; release database locks before yielding."""
    after = 0
    while True:
        with store.connect() as db:
            rows = db.execute('SELECT id,payload FROM paper_audit WHERE session_id=? AND id>? AND id<=? ORDER BY id LIMIT 250',
                              (session_id, after, through)).fetchall()
        if not rows:
            return
        for event_id, raw in rows:
            after = event_id
            yield dict(id=event_id, event=json.loads(raw))


def export_lines(store, report, format):
    """Stream the full cutoff audit; the end row distinguishes a completed export."""
    if format not in ('jsonl', 'csv'):
        raise ValueError('Journal export format must be jsonl or csv.')
    header = {key: value for key, value in report.items() if key not in ('records', 'next_before', 'kind', 'filtered_records')}
    records = audit_batches(store, report['session']['id'], report['audit_through_id'])
    if format == 'jsonl':
        yield (json.dumps(dict(type='session', **header), allow_nan=False)+'\n').encode()
        count = 0
        for record in records:
            count += 1
            yield (json.dumps(dict(type='audit', **record), allow_nan=False)+'\n').encode()
        yield (json.dumps(dict(type='end', event_count=count, audit_through_id=report['audit_through_id']))+'\n').encode()
        return
    output = io.StringIO()
    fields = ['record_type', 'session_id', 'engine_sha256', 'source', 'audit_through_id', 'event_count',
              'event_id', 'observed_utc', 'observed_iso_utc', 'kind', 'message', 'signal', 'price', 'fee',
              'units', 'entry_utc', 'exit_utc', 'entry_price', 'exit_price', 'fees', 'net_pnl', 'reason',
              'event_json', 'session_json']
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
    def line(row=None):
        if row is None:
            writer.writeheader()
        else:
            # Spreadsheet applications must not evaluate source/message text as formulas.
            writer.writerow({key: "'"+value if isinstance(value, str) and value.startswith(('=', '+', '-', '@', '\t', '\r'))
                             else value for key, value in row.items()})
        result = output.getvalue().encode()
        output.seek(0)
        output.truncate(0)
        return result
    yield line()
    session = report['session']
    common = dict(session_id=session['id'], engine_sha256=session['engine_sha256'],
                  source=session['source'], audit_through_id=report['audit_through_id'])
    yield line(dict(common, record_type='session', event_count=report['total_records'], session_json=json.dumps(header, allow_nan=False)))
    count = 0
    for record in records:
        count += 1
        event = record['event']
        observed = event['observed_utc']
        yield line(dict(event, **common, record_type='audit', event_id=record['id'],
                        observed_iso_utc=datetime.fromtimestamp(observed, timezone.utc).isoformat(),
                        event_json=json.dumps(event, allow_nan=False)))
    yield line(dict(common, record_type='end', event_count=count))
