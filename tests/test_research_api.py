"""Exercise the real local HTTP boundary without third-party services."""

import http.client
import json
import math
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from qslab.server import handler_for
from qslab.store import Store
from qslab.quotes import QuoteReader
from qslab.paper import PaperService
from test_research import csv_text


class LocalAPITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.directory.name) / 'lab.sqlite3')
        self.quote_path = Path(self.directory.name) / 'quote.json'
        reader = QuoteReader(self.quote_path)
        self.paper = PaperService(self.store, reader)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(self.store, reader, self.paper))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.directory.cleanup()

    def request(self, path, body=None, extra=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        headers = {'Content-Type': 'application/json', **(extra or {})}
        connection.request('GET' if body is None else 'POST', path,
                           body=None if body is None else json.dumps(body), headers=headers)
        response = connection.getresponse()
        status, content_type, data = response.status, response.getheader('Content-Type'), response.read()
        connection.close()
        return status, json.loads(data) if content_type.startswith('application/json') else data

    def test_import_run_history_and_exports(self):
        self.assertIsNone(self.request('/api/state')[1]['dataset'])
        status, meta = self.request('/api/import', {'name': 'Synthetic test', 'csv': csv_text([1 + .02 * math.sin(i / 4) for i in range(100)])})
        self.assertEqual(status, 200)
        status, result = self.request('/api/backtest', {'dataset_id': meta['sha256'], 'config': {'fast': 3, 'slow': 8}})
        self.assertEqual(status, 200)
        self.assertEqual(result['dataset']['source'], 'Synthetic test')
        self.assertEqual(len(self.request('/api/state')[1]['runs']), 1)
        self.assertEqual(self.request('/api/export?id=' + result['id'])[1], result)
        self.assertIn(b'entry_date,exit_date', self.request('/api/export?id=' + result['id'] + '&format=csv')[1])

    def test_cross_origin_and_rebound_host_are_rejected(self):
        self.assertEqual(self.request('/api/backtest', {}, {'Origin': 'https://example.com'})[0], 403)
        self.assertEqual(self.request('/api/state', extra={'Host': 'example.com'})[0], 403)
        self.assertEqual(self.request('/api/backtest', {}, {'Content-Type': 'text/plain'})[0], 403)

    def test_quote_endpoint_is_read_only_and_independent_of_datasets(self):
        status, snapshot = self.request('/api/quotes')
        self.assertEqual(status, 200)
        self.assertEqual(snapshot['status'], 'unavailable')
        self.assertIsNone(self.request('/api/state')[1]['dataset'])
        self.assertEqual(self.request('/api/quotes', {'bid': 1})[0], 404)
        self.assertEqual(self.request('/api/quotes', extra={'Host': 'example.com'})[0], 403)
        self.assertNotIn(str(self.quote_path), json.dumps(snapshot))
        now = int(time.time())
        self.quote_path.write_text(json.dumps(dict(schema=1, symbol='EURUSD', server='Synthetic-Demo',
            demo=True, connected=True, valid=True, heartbeat_utc=now, tick_time_msc=now * 1000,
            tick_age_ms=0, digits=5, bid=1.1, ask=1.1001)))
        snapshot = self.request('/api/quotes')[1]
        self.assertEqual(snapshot['status'], 'fresh')
        self.assertEqual(snapshot['quote']['spread_pips'], 1)
        self.assertEqual(self.request('/api/state')[1]['runs'], [])
        self.assertIsNone(self.request('/api/state')[1]['dataset'])

    def test_errors_and_static_paths_do_not_expose_local_files(self):
        self.assertEqual(self.request('/')[0], 200)
        self.assertEqual(self.request('/../../.local/SESSION_STATE.md')[0], 404)
        self.assertEqual(self.request('/api/backtest', {'config': {'capital': 'invalid'}})[0], 400)
        self.assertEqual(self.request('/api/import', {'csv': 'invalid'})[0], 400)
        self.assertEqual(self.request('/api/backtest', [])[0], 400)
        self.assertEqual(self.request('/api/run?id=missing')[0], 400)


    def test_paper_controls_are_local_simulation_only_and_records_survive(self):
        status, state = self.request('/api/paper')
        self.assertEqual(status, 200)
        self.assertEqual(state['mode'], 'PAPER_SIMULATION')
        self.assertTrue(state['enabled'])
        self.assertEqual(self.request('/api/paper/control', {'enabled': False})[0], 200)
        self.assertFalse(self.request('/api/paper')[1]['enabled'])
        self.assertEqual(self.request('/api/paper/control', {'enabled': 'true'})[0], 400)
        self.assertEqual(self.request('/api/paper/control', {'enabled': True}, {'Origin': 'https://example.com'})[0], 403)
        self.assertEqual(self.request('/api/paper', {})[0], 404)
        self.assertEqual(self.request('/api/paper/export')[1]['id'], state['id'])
        self.assertEqual(self.request('/api/state')[1]['runs'], [])
        self.assertEqual(self.request('/api/paper/control', {'enabled': True})[0], 200)

    def test_audit_journal_exports_filters_and_http_boundary(self):
        self.paper.set_enabled(False)
        self.paper.set_enabled(True)
        status, report = self.request('/api/paper/journal?limit=1')
        self.assertEqual(status, 200)
        self.assertEqual(report['total_records'], 2)
        self.assertEqual(len(report['records']), 1)
        self.assertEqual(report['reconciliation']['status'], 'initial_balance')
        self.assertEqual(self.request('/api/paper/journal?kind=entry')[1]['records'], [])
        raw = self.request('/api/paper/journal/export?format=jsonl')[1]
        lines = [json.loads(line) for line in raw.splitlines()]
        self.assertEqual(lines[-1]['event_count'], 2)
        self.assertEqual(lines[0]['session']['id'], report['session']['id'])
        status, raw = self.request('/api/paper/journal/export?format=csv')
        self.assertEqual(status, 200)
        self.assertIn(b'record_type,session_id', raw)
        for query in ('limit=101', 'limit=oops', 'before=-1', 'kind=unknown'):
            self.assertEqual(self.request('/api/paper/journal?'+query)[0], 400)
        self.assertEqual(self.request('/api/paper/journal/export?format=xml')[0], 400)
        self.assertEqual(self.request('/api/paper/journal', extra={'Host':'example.com'})[0], 403)
        self.assertEqual(self.request('/api/paper/journal', {})[0], 404)
        self.assertEqual(self.request('/api/state')[1]['runs'], [])


if __name__ == '__main__':
    unittest.main()
