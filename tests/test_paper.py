"""Synthetic forward streams verify timing, cash accounting, risk and restart safety."""

from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from qslab.paper import PaperConfig, PaperService, advance, initial_state
from qslab.store import Store

START = 1_800_000_000
CONFIG = PaperConfig(fast=2, slow=3)


def snapshot(second, mid, spread=.0001):
    return dict(status='fresh', source='Synthetic-Demo / MT5 demo', reason='Synthetic test stream.',
                quote=dict(symbol='EURUSD', bid=mid-spread/2, ask=mid+spread/2, digits=5,
                           spread_pips=round(spread/.0001, 4), heartbeat_utc=START+second,
                           tick_time_msc=(START+second)*1000, quote_age_seconds=0,
                           heartbeat_age_seconds=0, tick_clock='Synthetic server clock'))


def minute(state, index, mid, config=CONFIG):
    for offset in range(0, 60, 5):
        data = snapshot(index*60+offset, mid)
        advance(state, data, config, data['quote']['heartbeat_utc'])


def warmed(config=CONFIG):
    state = initial_state(config, START)
    for i in range(config.slow+1):
        minute(state, i, 1.1+i*.001, config)
    return state


class PaperEngineTests(unittest.TestCase):
    def test_only_closed_complete_candles_produce_a_later_quote_fill(self):
        state = warmed()
        self.assertIsNone(state['position'])
        self.assertEqual(state['signal'], 'WARMUP')
        quote = snapshot(240, 1.104)
        _, records = advance(state, quote, CONFIG, START+240)
        self.assertEqual(state['signal'], 'LONG')
        self.assertEqual(len(state['closes']), 3)
        self.assertFalse(state['candles'][0]['complete'])
        self.assertTrue(state['candles'][-1]['complete'])
        self.assertEqual(state['position']['observed_utc'], START+240)
        self.assertAlmostEqual(state['position']['price'], quote['quote']['ask']+.00002)
        self.assertEqual(records[0]['signal_server_minute'], START+180)
        self.assertEqual(records[-1]['kind'], 'entry')

    def test_ask_bid_costs_cash_and_pnl_reconcile(self):
        state = warmed()
        minute(state, 4, 1.104)
        entry = dict(state['position'])
        for i in range(5, 9):
            minute(state, i, 1.08)
        self.assertIsNone(state['position'])
        self.assertEqual(state['closed_count'], 1)
        trade = state['trades'][0]
        self.assertAlmostEqual(trade['exit_price'], 1.08-.00005-.00002)
        expected = CONFIG.units*(trade['exit_price']-entry['price'])-trade['fees']
        self.assertAlmostEqual(trade['net_pnl'], expected)
        self.assertAlmostEqual(state['cash']-CONFIG.capital, expected)
        self.assertAlmostEqual(state['equity']-CONFIG.capital, state['realized_pnl'])
        self.assertAlmostEqual(state['slippage'], .04)

    def test_open_pnl_includes_liquidation_costs_and_no_second_spread_charge(self):
        state = warmed()
        quote = snapshot(240, 1.104)
        advance(state, quote, CONFIG, START+240)
        fees = CONFIG.units*((quote['quote']['ask']+.00002)+(quote['quote']['bid']-.00002))*.35/10000
        expected = -CONFIG.units*(.0001+2*.00002)-fees
        self.assertAlmostEqual(state['equity']-CONFIG.capital, expected)
        self.assertAlmostEqual(state['unrealized_pnl'], expected)
        self.assertEqual(state['realized_pnl'], 0)

    def test_duplicates_backward_ticks_and_unavailable_feeds_never_fill(self):
        state = warmed()
        original = json.dumps(state['candle'])
        last = state['last_tick']
        for data in (snapshot(235, 5), snapshot(230, 5), dict(status='stale', quote=None, reason='Expired.')):
            sample, _ = advance(state, data, CONFIG, START+240)
            self.assertIsNone(sample)
            self.assertIsNone(state['position'])
            self.assertEqual(state['last_tick'], last)
            self.assertEqual(json.dumps(state['candle']), original)

    def test_gap_discards_partial_candle_and_restarts_signal_warmup(self):
        state = warmed()
        minute(state, 4, 1.104)
        position = dict(state['position'])
        advance(state, snapshot(400, 1.104), CONFIG, START+400)
        self.assertEqual(state['gaps'], 1)
        self.assertEqual(state['closes'], [])
        self.assertEqual(state['signal'], 'WARMUP')
        self.assertTrue(state['candle']['partial'])
        self.assertEqual(state['position'], position)

    def test_drawdown_closes_at_next_available_bid_and_blocks_reentry(self):
        config = replace(CONFIG, max_drawdown_pct=.1)
        state = warmed(config)
        minute(state, 4, 1.104, config)
        advance(state, snapshot(300, 1), config, START+300)
        self.assertTrue(state['halted'])
        self.assertIsNone(state['position'])
        self.assertEqual(state['trades'][0]['reason'], 'drawdown_halt')
        advance(state, snapshot(305, 1.2), config, START+305)
        self.assertIsNone(state['position'])

    def test_entry_cost_drawdown_is_checked_on_entry_quote(self):
        config = replace(CONFIG, max_drawdown_pct=.0001)
        state = warmed(config)
        advance(state, snapshot(240, 1.104), config, START+240)
        self.assertTrue(state['halted'])
        self.assertIsNone(state['position'])
        self.assertEqual(state['trades'][0]['reason'], 'entry_cost_halt')

    def test_spread_and_exposure_limits_block_entries(self):
        for spread, config in ((.001, CONFIG), (.0001, replace(CONFIG, units=9000))):
            state = warmed(config)
            advance(state, snapshot(240, 1.104, spread), config, START+240)
            self.assertEqual(state['signal'], 'LONG')
            self.assertIsNone(state['position'])
            self.assertIn('blocked', state['reason'])

    def test_source_change_is_rejected_without_mixing_marks(self):
        state = warmed()
        data = snapshot(240, 1.104)
        data['source'] = 'Other-Demo'
        sample, _ = advance(state, data, CONFIG, START+240)
        self.assertIsNone(sample)
        self.assertEqual(state['feed'], 'source_changed')
        self.assertIsNone(state['position'])

    def test_pause_blocks_entry_but_keeps_marking_and_strategy_exit(self):
        state = warmed()
        state['enabled'] = False
        advance(state, snapshot(240, 1.104), CONFIG, START+240)
        self.assertIsNone(state['position'])
        state['enabled'] = True
        advance(state, snapshot(245, 1.104), CONFIG, START+245)
        self.assertIsNotNone(state['position'])
        state['enabled'] = False
        for second in range(250, 300, 5):
            advance(state, snapshot(second, 1.104), CONFIG, START+second)
        for i in range(5, 9):
            minute(state, i, 1.08)
        self.assertIsNone(state['position'])
        self.assertEqual(state['closed_count'], 1)


class Reader:
    def __init__(self):
        self.data = snapshot(0, 1.1)

    def snapshot(self):
        return self.data


class PaperPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.directory.name)/'lab.sqlite3')
        self.reader = Reader()
        self.now = START
        self.service = PaperService(self.store, self.reader, CONFIG, clock=lambda: self.now)

    def tearDown(self):
        self.service.stop()
        self.directory.cleanup()

    def step(self, second, mid):
        self.now = START+second
        self.reader.data = snapshot(second, mid)
        self.service.step()

    def warm(self):
        for i in range(4):
            for offset in range(0, 60, 5):
                self.step(i*60+offset, 1.1+i*.001)

    def test_restart_preserves_position_cash_and_deduplicates_existing_tick(self):
        self.warm()
        self.step(240, 1.104)
        before = self.service.snapshot()
        second = PaperService(self.store, self.reader, CONFIG, clock=lambda: self.now)
        second.step()
        after = second.snapshot()
        for key in ('id', 'position', 'cash', 'equity', 'observations', 'retained_samples'):
            self.assertEqual(before[key], after[key])
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM paper_audit WHERE payload LIKE '%Simulated long%'").fetchone()[0], 1)

    def test_transaction_failure_does_not_leave_a_partial_fill_or_sample(self):
        self.warm()
        before = self.service.snapshot()
        with self.store.connect() as db:
            db.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON paper_audit BEGIN SELECT RAISE(ABORT, 'synthetic storage error'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.step(240, 1.104)
        after = self.service.snapshot()
        for key in ('position', 'cash', 'observations', 'retained_samples'):
            self.assertEqual(before[key], after[key])
        with self.store.connect() as db:
            db.execute('DROP TRIGGER fail_audit')
        self.service.step()
        self.assertIsNotNone(self.service.snapshot()['position'])

    def test_long_restart_gap_requires_new_warmup_and_current_mark(self):
        self.warm()
        self.step(240, 1.104)
        self.now += 20
        self.assertFalse(self.service.snapshot()['valuation_current'])
        self.assertEqual(self.service.snapshot()['worker_status'], 'offline')
        self.step(270, 1.104)
        state = self.service.snapshot()
        self.assertTrue(state['valuation_current'])
        self.assertEqual(state['signal'], 'WARMUP')
        self.assertIsNotNone(state['position'])

    def test_control_persists_and_changed_engine_config_is_rejected(self):
        self.service.set_enabled(False)
        second = PaperService(self.store, self.reader, CONFIG)
        self.assertFalse(second.snapshot()['enabled'])
        with self.assertRaises(ValueError):
            self.service.set_enabled('false')
        with self.assertRaises(ValueError):
            PaperService(self.store, self.reader, replace(CONFIG, units=2000))

    def test_real_background_worker_collects_without_browser_requests(self):
        read = threading.Event()
        def observed_snapshot():
            read.set()
            return self.reader.data
        self.reader.snapshot = observed_snapshot
        self.service.start()
        self.assertIsNotNone(self.service.thread)
        self.assertTrue(read.wait(2), 'Background worker did not read the source.')
        self.service.stop()
        self.assertEqual(self.service.snapshot()['observations'], 1)
        self.assertFalse(self.service.thread.is_alive())

    def test_sample_retention_is_bounded_without_deleting_audit(self):
        with self.store.connect() as db:
            db.executemany('INSERT INTO paper_samples(session_id,payload) VALUES (?,?)', [('synthetic', '{}')]*10000)
        self.step(0, 1.1)
        self.assertEqual(self.service.snapshot()['retained_samples'], 10000)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT MIN(id) FROM paper_samples').fetchone()[0], 2)


if __name__ == '__main__':
    unittest.main()
