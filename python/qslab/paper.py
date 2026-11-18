"""Persistent forward simulation on sampled demo quotes. No broker operations."""

from dataclasses import asdict, dataclass
import hashlib
import json
import logging
import math
from pathlib import Path
import threading
import time
import uuid

VERSION = 'sampled-paper-v1'
ENGINE_HASH = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


@dataclass(frozen=True)
class PaperConfig:
    capital: float = 10000
    units: float = 1000
    fast: int = 5
    slow: int = 20
    commission_bps: float = .35
    slippage_pips: float = .2
    max_spread_pips: float = 3
    max_drawdown_pct: float = 2
    max_gap_seconds: int = 10

    def __post_init__(self):
        if not (type(self.fast) is int and type(self.slow) is int and 2 <= self.fast < self.slow <= 60):
            raise ValueError('Paper SMA windows must satisfy 2 <= fast < slow <= 60.')
        numbers = asdict(self)
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in numbers.values()):
            raise ValueError('Paper settings must be finite numbers.')
        if not (self.capital >= 100 and self.units > 0 and self.commission_bps >= 0
                and self.slippage_pips >= 0 and self.max_spread_pips > 0
                and 0 < self.max_drawdown_pct <= 50 and 2 <= self.max_gap_seconds <= 30):
            raise ValueError('Invalid paper cost or risk settings.')


def initial_state(config, now):
    return dict(schema=1, mode='PAPER_SIMULATION', version=VERSION, engine_sha256=ENGINE_HASH, config=asdict(config),
                id=uuid.uuid4().hex, created_utc=now, enabled=True, halted=False, source=None,
                cash=config.capital, equity=config.capital, peak=config.capital,
                drawdown_pct=0, max_drawdown_pct=0, realized_pnl=0, unrealized_pnl=0,
                fees=0, slippage=0, position=None, signal='WARMUP', target_long=False,
                reason='Waiting for fresh demo quotes.', feed='unavailable', last_poll_utc=now,
                last_tick=None, last_observed_utc=None, last_quote=None,
                observations=0, gaps=0, duplicates=0, rejected=0, closed_count=0,
                candle=None, candles=[], closes=[], trades=[], events=[], sma_fast=None, sma_slow=None)


def event(state, records, now, kind, message, **extra):
    record = dict(observed_utc=now, kind=kind, message=message, **extra)
    state['events'] = (state['events'] + [record])[-30:]
    records.append(record)


def mark(state, quote, config):
    position = state['position']
    # Liquidation-side mark includes estimated exit slippage and commission.
    exit_price = quote['bid'] - config.slippage_pips * .0001
    exit_fee = config.units * exit_price * config.commission_bps / 10000 if position else 0
    state['unrealized_pnl'] = (config.units * (exit_price - position['price'])
                               - position['fee'] - exit_fee) if position else 0
    state['equity'] = state['cash'] + (config.units * exit_price - exit_fee if position else 0)
    state['peak'] = max(state['peak'], state['equity'])
    state['drawdown_pct'] = max(0, (state['peak'] - state['equity']) / state['peak'] * 100)
    state['max_drawdown_pct'] = max(state['max_drawdown_pct'], state['drawdown_pct'])


def close_position(state, quote, config, records, reason):
    position = state['position']
    price = quote['bid'] - config.slippage_pips * .0001
    fee = config.units * price * config.commission_bps / 10000
    pnl = config.units * (price - position['price']) - position['fee'] - fee
    state['cash'] += config.units * price - fee
    state['fees'] += fee
    state['slippage'] += config.units * config.slippage_pips * .0001
    state['realized_pnl'] += pnl
    state['closed_count'] += 1
    trade = dict(entry_utc=position['observed_utc'], exit_utc=quote['heartbeat_utc'],
                 units=config.units, entry_price=position['price'], exit_price=price,
                 fees=position['fee'] + fee, net_pnl=pnl, reason=reason)
    state['trades'] = (state['trades'] + [trade])[-50:]
    state['position'] = None
    event(state, records, quote['heartbeat_utc'], 'exit', reason, **trade)
    mark(state, quote, config)


def advance(state, snapshot, config, now):
    """Mutate only a transaction-local state; return the sampled quote and audit events."""
    records = []
    state['last_poll_utc'] = now
    previous_feed = state['feed']
    state['feed'] = snapshot['status']
    if snapshot['status'] != 'fresh' or not snapshot.get('quote'):
        state['reason'] = 'Simulation waiting: ' + snapshot['reason']
        if previous_feed != state['feed']:
            event(state, records, now, 'feed', state['reason'])
        return None, records
    quote = snapshot['quote']
    if state['source'] and state['source'] != snapshot['source']:
        state['feed'] = 'source_changed'
        state['reason'] = 'Source changed; this session will not mix providers.'
        if previous_feed != state['feed']:
            event(state, records, now, 'source', state['reason'])
        return None, records
    state['source'] = snapshot['source']
    tick = quote['tick_time_msc']
    if state['last_tick'] is not None and tick <= state['last_tick']:
        if tick < state['last_tick']:
            state['rejected'] += 1
            state['feed'] = 'out_of_order'
            state['reason'] = 'Backward source timestamp rejected; no simulation fill.'
        else:
            state['duplicates'] += 1
            state['reason'] = 'Waiting for a new source tick.'
        return None, records
    observed = quote['heartbeat_utc']
    gap = state['last_tick'] is not None and (
        tick - state['last_tick'] > config.max_gap_seconds * 1000
        or observed - state['last_observed_utc'] > config.max_gap_seconds
        or observed < state['last_observed_utc'])
    if gap:
        state['gaps'] += 1
        state['candle'] = None
        state['closes'] = []
        state['sma_fast'] = state['sma_slow'] = None
        state['signal'] = 'WARMUP'
        state['target_long'] = False
        event(state, records, observed, 'gap', 'Continuity lost; partial candle discarded and SMA warm-up restarted. Open exposure retained.')
    state['observations'] += 1
    state['last_tick'] = tick
    state['last_observed_utc'] = observed
    state['last_quote'] = quote
    bucket = tick // 60000 * 60  # Raw server clock, intentionally not labeled UTC.
    mid = (quote['bid'] + quote['ask']) / 2
    candle = state['candle']
    new_bucket = candle is not None and bucket != candle['server_minute']
    if new_bucket:
        complete = not candle['partial'] and candle['samples'] >= 2
        candle['complete'] = complete
        state['candles'] = (state['candles'] + [candle])[-60:]
        if complete:
            state['closes'] = (state['closes'] + [candle['close']])[-config.slow:]
        if len(state['closes']) >= config.slow:
            state['sma_fast'] = sum(state['closes'][-config.fast:]) / config.fast
            state['sma_slow'] = sum(state['closes']) / config.slow
            state['target_long'] = state['sma_fast'] > state['sma_slow']
            state['signal'] = 'LONG' if state['target_long'] else 'CASH'
            event(state, records, observed, 'signal', 'Closed-candle SMA decision.',
                  signal=state['signal'], signal_server_minute=candle['server_minute'])
    if candle is None or new_bucket:
        state['candle'] = dict(server_minute=bucket, open=mid, high=mid, low=mid, close=mid,
                               samples=1, partial=candle is None, complete=False)
    else:
        candle['high'] = max(candle['high'], mid)
        candle['low'] = min(candle['low'], mid)
        candle['close'] = mid
        candle['samples'] += 1
    mark(state, quote, config)
    if state['drawdown_pct'] >= config.max_drawdown_pct and not state['halted']:
        state['halted'] = True
        event(state, records, observed, 'halt', 'Drawdown limit reached; entries halted for this session.')
    if state['position'] and (state['halted'] or (state['signal'] == 'CASH' and new_bucket)):
        close_position(state, quote, config, records, 'drawdown_halt' if state['halted'] else 'sma_cash')
    state['reason'] = f"Collecting complete M1 candles: {len(state['closes'])}/{config.slow}."
    if state['signal'] != 'WARMUP':
        state['reason'] = 'Closed-candle signal: ' + state['signal'] + '.'
    if state['halted']:
        state['reason'] = 'Session halted by drawdown control.'
    elif not state['enabled']:
        state['reason'] = 'Entries paused; observation, marks and strategy/risk exits continue.'
    elif state['target_long'] and not state['position']:
        price = quote['ask'] + config.slippage_pips * .0001
        fee = config.units * price * config.commission_bps / 10000
        if quote['spread_pips'] > config.max_spread_pips:
            state['reason'] = 'Entry blocked: spread exceeds the configured limit.'
        elif config.units * price + fee > min(state['cash'], state['equity'] * .5):
            state['reason'] = 'Entry blocked: cash or 50% equity exposure limit.'
        else:
            state['position'] = dict(price=price, fee=fee, units=config.units, observed_utc=observed)
            state['cash'] -= config.units * price + fee
            state['fees'] += fee
            state['slippage'] += config.units * config.slippage_pips * .0001
            event(state, records, observed, 'entry', 'Simulated long filled at ask plus slippage.', price=price, fee=fee)
            mark(state, quote, config)
            if state['drawdown_pct'] >= config.max_drawdown_pct:
                state['halted'] = True
                event(state, records, observed, 'halt', 'Entry costs reached drawdown limit.')
                close_position(state, quote, config, records, 'entry_cost_halt')
    return dict(source=state['source'], **quote), records


class PaperService:
    def __init__(self, store, reader, config=None, clock=time.time):
        self.store, self.reader, self.clock = store, reader, clock
        self.config = config or PaperConfig()
        self.stop_event = threading.Event()
        self.thread = None
        self.worker_error = False
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT state FROM paper_state WHERE id=1').fetchone()
            if row:
                state = json.loads(row[0])
                if state['version'] != VERSION or state['config'] != asdict(self.config) or state['engine_sha256'] != ENGINE_HASH:
                    raise ValueError('Paper session version/settings changed. Preserve its database and select a new database before starting a different engine.')
            else:
                db.execute('INSERT INTO paper_state VALUES (1, ?)',
                           (json.dumps(initial_state(self.config, self.clock()), allow_nan=False),))

    def step(self):
        snapshot = self.reader.snapshot()
        with self.store.connect() as db:
            # Read/decide/write in one transaction: concurrent readers cannot see half a fill.
            # Duplicate workers also serialize and cannot fill the same source tick twice.
            db.execute('BEGIN IMMEDIATE')
            state = json.loads(db.execute('SELECT state FROM paper_state WHERE id=1').fetchone()[0])
            sample, records = advance(state, snapshot, self.config, self.clock())
            if sample:
                db.execute('INSERT INTO paper_samples(session_id,payload) VALUES (?,?)',
                           (state['id'], json.dumps(sample, allow_nan=False)))
                db.execute('DELETE FROM paper_samples WHERE id <= (SELECT MAX(id)-10000 FROM paper_samples)')
            for record in records:
                db.execute('INSERT INTO paper_audit(session_id,payload) VALUES (?,?)',
                           (state['id'], json.dumps(record, allow_nan=False)))
            db.execute('UPDATE paper_state SET state=? WHERE id=1', (json.dumps(state, allow_nan=False),))
        self.worker_error = False

    def snapshot(self):
        with self.store.connect() as db:
            state = json.loads(db.execute('SELECT state FROM paper_state WHERE id=1').fetchone()[0])
            state['retained_samples'] = db.execute('SELECT COUNT(*) FROM paper_samples').fetchone()[0]
        state['worker_status'] = ('error' if self.worker_error else
                                  'offline' if self.clock() - state['last_poll_utc'] > 5 else 'running')
        state['valuation_current'] = (state['worker_status'] == 'running' and state['feed'] == 'fresh'
                                      and state['last_observed_utc'] is not None
                                      and 0 <= self.clock() - state['last_observed_utc'] <= 5)
        state['net_pnl'] = state['equity'] - self.config.capital
        return state

    def set_enabled(self, enabled):
        if type(enabled) is not bool:
            raise ValueError('enabled must be a boolean.')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            state = json.loads(db.execute('SELECT state FROM paper_state WHERE id=1').fetchone()[0])
            records = []
            state['enabled'] = enabled
            event(state, records, self.clock(), 'control', 'Entries resumed.' if enabled else 'Entries paused; exits remain active.')
            db.execute('UPDATE paper_state SET state=? WHERE id=1', (json.dumps(state, allow_nan=False),))
            db.execute('INSERT INTO paper_audit(session_id,payload) VALUES (?,?)', (state['id'], json.dumps(records[0])))

    def start(self):
        if self.thread is not None:
            raise RuntimeError('Paper worker already started.')
        def work():
            while not self.stop_event.is_set():
                try:
                    self.step()
                except Exception:
                    self.worker_error = True
                    logging.exception('Paper simulation update failed; no uncommitted fill retained')
                self.stop_event.wait(1)
        self.thread = threading.Thread(target=work, name='qslab-paper', daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=15)
