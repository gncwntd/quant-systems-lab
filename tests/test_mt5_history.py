"""Synthetic closed-D1 bundles test history validation, provenance and isolated import."""

import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'python'))
from qslab.mt5_history import parse_history, load_history, MAX_BYTES
from qslab.store import Store


def bundle():
    start = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp())
    bars = [dict(server_time=start+i*86400, open=1.1, high=1.12, low=1.09, close=1.11,
                 tick_volume=1000, spread_points=12, real_volume=0) for i in range(40)]
    return dict(schema=1, symbol='EURUSD', timeframe='D1', demo=True, server='Synthetic-Demo',
                captured_utc=start+41*86400, current_bar_server_time=start+40*86400,
                count=40, requested_bars=1500, digits=5, point=.00001, bars=bars)


class MT5HistoryTests(unittest.TestCase):
    def setUp(self):
        self.data = bundle()

    def parse(self, data=None):
        return parse_history(json.dumps(self.data if data is None else data).encode(), now=self.data['captured_utc'])

    def test_closed_daily_data_and_allowlisted_provenance(self):
        data = dict(self.data, account_id='private-marker', password='private-marker')
        raw = json.dumps(data).encode()
        bars, meta = parse_history(raw, now=data['captured_utc'])
        self.assertEqual(bars[0], dict(date='2024-01-01', close=1.11))
        self.assertEqual(meta['rows'], 40)
        self.assertEqual(meta['kind'], 'mt5_demo_daily')
        self.assertEqual(meta['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertAlmostEqual(meta['source_spread_pips_min'], 1.2)
        self.assertTrue(meta['forming_bar_excluded'])
        self.assertNotIn('private-marker', json.dumps(meta))
        self.assertIn('timezone unverified', meta['date_basis'])

    def test_real_accounts_other_instruments_and_manifest_errors_rejected(self):
        for changes in (dict(demo=False), dict(demo=1), dict(schema=True), dict(symbol='GBPUSD'),
                        dict(timeframe='M1'), dict(count=41), dict(count=True), dict(requested_bars=10),
                        dict(digits=True), dict(point=float('nan')), dict(point=.01),
                        dict(server='<bad>'), dict(captured_utc=self.data['captured_utc']+121)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.parse(dict(self.data, **changes))

    def test_forming_duplicate_out_of_order_and_invalid_ohlc_rejected(self):
        mutations = [dict(server_time=self.data['current_bar_server_time']),
                     dict(server_time=self.data['bars'][0]['server_time']),
                     dict(open=float('nan')), dict(close=0), dict(high=1.05), dict(low=2),
                     dict(spread_points=-1), dict(tick_volume=True), dict(real_volume=-1)]
        for mutation in mutations:
            data = copy.deepcopy(self.data)
            data['bars'][1].update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.parse(data)
        data = copy.deepcopy(self.data)
        data['bars'][1]['server_time'] = data['bars'][0]['server_time']+60
        with self.assertRaises(ValueError):
            self.parse(data)

    def test_limits_and_unreadable_files_are_explicit(self):
        for raw in (b'{', b'[]', b'\xff', b'x'*(MAX_BYTES+1)):
            with self.subTest(length=len(raw)), self.assertRaises(ValueError):
                parse_history(raw)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'missing.json'
            with self.assertRaises(ValueError):
                load_history(path)
            path.write_bytes(json.dumps(self.data).encode())
            self.assertEqual(load_history(path)[1]['rows'], 40)

    def test_cli_inspection_does_not_import_and_opt_in_import_keeps_paper_state(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            export = folder/'history.json'
            raw = json.dumps(self.data).encode()
            export.write_bytes(raw)
            database = folder/'research.sqlite3'
            store = Store(database)
            with store.connect() as db:
                db.execute('INSERT INTO paper_state VALUES (1,?)', ('{"sentinel":"untouched"}',))
            command = [sys.executable, str(ROOT/'tools/run_lab.py'), 'inspect-mt5-history', '--file', str(export)]
            inspected = subprocess.run(command, capture_output=True, text=True, check=True)
            self.assertFalse(json.loads(inspected.stdout)['imported'])
            with store.connect() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM datasets').fetchone()[0], 0)
            imported = subprocess.run(command+['--import-data', '--database', str(database)], capture_output=True, text=True, check=True)
            self.assertTrue(json.loads(imported.stdout)['imported'])
            self.assertEqual(store.dataset()[0]['rows'], 40)
            self.assertEqual((folder/'mt5-history'/ (hashlib.sha256(raw).hexdigest()+'.json')).read_bytes(), raw)
            with sqlite3.connect(database) as db:
                self.assertEqual(json.loads(db.execute('SELECT state FROM paper_state').fetchone()[0]), dict(sentinel='untouched'))

    def test_history_script_has_no_trading_credentials_or_external_calls(self):
        source = (ROOT/'mt5/QSLHistoryExport.mq5').read_text()
        for forbidden in ('OrderSend', 'CTrade', '#import', '#include', 'WebRequest', 'ACCOUNT_LOGIN', 'ACCOUNT_BALANCE'):
            self.assertNotIn(forbidden, source)
        self.assertIn('CopyRates(symbol,PERIOD_D1,1,1500,rates)', source)


if __name__ == '__main__':
    unittest.main()
