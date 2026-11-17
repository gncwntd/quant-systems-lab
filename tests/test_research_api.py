"""Exercise the real local HTTP boundary without third-party services."""

import http.client
import json
import math
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from qslab.server import handler_for
from qslab.store import Store
from test_research import csv_text


class LocalAPITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.directory.name) / 'lab.sqlite3')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(self.store))
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

    def test_errors_and_static_paths_do_not_expose_local_files(self):
        self.assertEqual(self.request('/')[0], 200)
        self.assertEqual(self.request('/../../.local/SESSION_STATE.md')[0], 404)
        self.assertEqual(self.request('/api/backtest', {'config': {'capital': 'invalid'}})[0], 400)
        self.assertEqual(self.request('/api/import', {'csv': 'invalid'})[0], 400)
        self.assertEqual(self.request('/api/backtest', [])[0], 400)
        self.assertEqual(self.request('/api/run?id=missing')[0], 400)


if __name__ == '__main__':
    unittest.main()
