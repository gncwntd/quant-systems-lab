"""Freshness, validation and privacy boundaries for the read-only demo adapter."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from qslab.quotes import QuoteReader


class QuoteTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'quote.json'
        self.reader = QuoteReader(self.path, clock=lambda: 1_800_000_001)
        self.data = dict(schema=1, symbol='EURUSD', server='Synthetic-Demo', demo=True,
                         connected=True, valid=True, heartbeat_utc=1_800_000_000,
                         tick_time_msc=1_800_000_000_000, tick_age_ms=250,
                         digits=5, bid=1.10000, ask=1.10012)

    def tearDown(self):
        self.directory.cleanup()

    def snapshot(self, **changes):
        self.path.write_text(json.dumps(dict(self.data, **changes)), encoding='utf-8')
        return self.reader.snapshot()

    def test_fresh_quote_spread_and_allowlisted_output(self):
        result = self.snapshot(account_id='must never escape', password='must never escape')
        self.assertEqual(result['status'], 'fresh')
        self.assertEqual(result['source'], 'Synthetic-Demo / MT5 demo')
        self.assertEqual(result['quote']['spread_pips'], 1.2)
        self.assertEqual(result['quote']['quote_age_seconds'], 1.2)
        self.assertNotIn('must never escape', json.dumps(result))
        self.assertNotIn(str(self.path), json.dumps(result))

    def test_missing_and_corrupt_files_have_no_prices(self):
        self.assertEqual(self.reader.snapshot()['status'], 'unavailable')
        for raw in ('{', '[]', 'x' * 8193):
            self.path.write_text(raw)
            result = self.reader.snapshot()
            self.assertEqual(result['status'], 'invalid')
            self.assertIsNone(result['quote'])

    def test_expired_heartbeat_hides_cached_price(self):
        result = self.snapshot(heartbeat_utc=1_799_999_990)
        self.assertEqual(result['status'], 'stale')
        self.assertIsNone(result['quote'])

    def test_old_tick_and_future_clocks_are_not_fresh(self):
        result = self.snapshot(tick_age_ms=16000)
        self.assertEqual(result['status'], 'stale')
        self.assertEqual(result['quote']['quote_age_seconds'], 17)
        for changes in ({'heartbeat_utc': 1_800_000_010}, {'tick_age_ms': -3000}):
            self.assertEqual(self.snapshot(**changes)['status'], 'clock_error')

    def test_real_account_disconnection_and_missing_tick_fail_closed(self):
        for changes, status in (({'demo': False}, 'blocked'), ({'connected': False}, 'disconnected'),
                                ({'valid': False}, 'unavailable')):
            with self.subTest(changes=changes):
                result = self.snapshot(**changes)
                self.assertEqual(result['status'], status)
                self.assertIsNone(result['quote'])

    def test_malformed_prices_types_and_metadata_rejected(self):
        for changes in ({'bid': 0}, {'bid': float('nan')}, {'ask': float('inf')}, {'ask': 1},
                        {'bid': True}, {'digits': 100}, {'tick_time_msc': True}, {'tick_age_ms': '0'},
                        {'heartbeat_utc': True}, {'demo': 1}, {'schema': True}, {'symbol': 'GBPUSD'},
                        {'server': '<script>'}):
            with self.subTest(changes=changes):
                result = self.snapshot(**changes)
                self.assertEqual(result['status'], 'invalid')
                self.assertIsNone(result['quote'])

    def test_bridge_source_does_not_import_or_call_trading_functions(self):
        source = (Path(__file__).resolve().parents[1] / 'mt5' / 'QSLQuoteBridge.mq5').read_text()
        for forbidden in ('OrderSend', 'CTrade', '#include', '#import', 'WebRequest', 'ACCOUNT_LOGIN', 'ACCOUNT_BALANCE'):
            self.assertNotIn(forbidden, source)


if __name__ == '__main__':
    unittest.main()
