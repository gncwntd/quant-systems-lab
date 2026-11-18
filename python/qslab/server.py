"""Loopback-only research API and dashboard; no trading or credential endpoints."""

import csv
import io
import json
import logging
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .data import fetch_ecb, parse_csv
from .engine import Config, run_research
from .store import Store
from .quotes import QuoteReader
from .paper import PaperService
from .paper_journal import read_journal, export_lines

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / 'dashboard'


def handler_for(store, quotes=None, paper=None):
    quotes = quotes or QuoteReader()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            logging.info(fmt, *args)

        def reply(self, status, data, content_type='application/json', attachment=None):
            body = json.dumps(data, allow_nan=False).encode() if content_type == 'application/json' else data
            self.send_response(status)
            self.send_header('Content-Type', content_type + '; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
            if attachment:
                self.send_header('Content-Disposition', f'attachment; filename="{attachment}"')
            self.end_headers()
            self.wfile.write(body)

        def valid_host(self):
            port = self.server.server_port
            return self.headers.get('Host') in (f'127.0.0.1:{port}', f'localhost:{port}')

        def journal_download(self, format):
            if format not in ('jsonl', 'csv'):
                raise ValueError('Journal export format must be jsonl or csv.')
            report = read_journal(store, limit=1)
            self.send_response(200)
            self.send_header('Content-Type', ('application/x-ndjson' if format == 'jsonl' else 'text/csv')+'; charset=utf-8')
            self.send_header('Content-Disposition', f'attachment; filename="qslab-paper-journal.{format}"')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'")
            self.send_header('Connection', 'close')
            self.end_headers()
            self.close_connection = True
            try:
                for chunk in export_lines(store, report, format):
                    self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                logging.info('Journal download disconnected')
            except Exception:
                logging.exception('Journal export interrupted; completion record not emitted')

        def do_GET(self):
            if not self.valid_host():
                self.reply(403, {'error': 'Loopback host required.'})
                return
            path = urlsplit(self.path)
            try:
                if path.path in ('/', '/app.js', '/styles.css'):
                    name, kind = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'),
                                  '/styles.css': ('styles.css', 'text/css')}[path.path]
                    self.reply(200, (STATIC / name).read_bytes(), kind)
                elif path.path == '/api/quotes':
                    self.reply(200, quotes.snapshot())
                elif path.path == '/api/paper' and paper is not None:
                    self.reply(200, paper.snapshot())
                elif path.path == '/api/paper/export' and paper is not None:
                    self.reply(200, paper.snapshot(), attachment='qslab-paper-snapshot.json')
                elif path.path == '/api/paper/journal' and paper is not None:
                    params = parse_qs(path.query)
                    self.reply(200, read_journal(store, before=int(params.get('before', ['0'])[0]),
                                                limit=int(params.get('limit', ['25'])[0]),
                                                kind=params.get('kind', ['all'])[0]))
                elif path.path == '/api/paper/journal/export' and paper is not None:
                    self.journal_download(parse_qs(path.query).get('format', ['jsonl'])[0])
                elif path.path == '/api/state':
                    try:
                        meta, bars = store.dataset()
                    except ValueError:
                        meta, bars = None, []
                    self.reply(200, {'mode': 'RESEARCH', 'dataset': meta, 'bars': bars,
                                     'runs': store.runs(), 'defaults': asdict(Config()),
                                     'checkpoints': [
                                         {'id': 'G00', 'title': 'Open-source foundation', 'status': 'Complete'},
                                         {'id': 'R01', 'title': 'Daily data import and audit', 'status': 'Implemented; source suitability pending'},
                                         {'id': 'R02', 'title': 'Cost-aware reference simulation', 'status': 'Implemented; no trading edge established'},
                                         {'id': 'R03', 'title': 'Dashboard and experiment log', 'status': 'Implemented locally'},
                                         {'id': 'CP05', 'title': 'Validated adaptive model', 'status': 'Planned'},
                                         {'id': 'R04', 'title': 'Read-only demo quotes', 'status': 'Adapter implemented; inspect quote panel for connection'},
                                         {'id': 'R05', 'title': 'Streaming paper simulation', 'status': 'M1 / SMA 5–20; local hypothetical fills only'},
                                         {'id': 'R06', 'title': 'Paper audit and reconciliation', 'status': 'Event journal, full audit exports and independent accounting checks'},
                                         {'id': 'CP07', 'title': 'Broker demo forward test', 'status': 'Planned; no execution adapter'}]})
                elif path.path == '/api/run':
                    run_id = parse_qs(path.query).get('id', [''])[0]
                    self.reply(200, store.run(run_id))
                elif path.path == '/api/export':
                    params = parse_qs(path.query)
                    run = store.run(params.get('id', [''])[0])
                    if params.get('format', ['json'])[0] == 'csv':
                        output = io.StringIO()
                        columns = ['entry_date', 'exit_date', 'side', 'units', 'entry_price', 'exit_price', 'gross_pnl', 'costs', 'net_pnl', 'reason']
                        writer = csv.DictWriter(output, fieldnames=columns, extrasaction='ignore')
                        writer.writeheader()
                        writer.writerows(run['trades'])
                        self.reply(200, output.getvalue().encode(), 'text/csv', 'qslab-trades.csv')
                    else:
                        self.reply(200, run, attachment='qslab-experiment.json')
                else:
                    self.reply(404, {'error': 'Not found.'})
            except ValueError as exc:
                self.reply(400, {'error': str(exc)})
            except Exception:
                logging.exception('GET failed')
                self.reply(500, {'error': 'Local service error; see the server log.'})

        def do_POST(self):
            if (not self.valid_host() or self.headers.get('Origin', f'http://{self.headers.get("Host")}') != f'http://{self.headers.get("Host")}'
                    or self.headers.get_content_type() != 'application/json'):
                self.reply(403, {'error': 'Same-origin JSON requests only.'})
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 6_000_000:
                    raise ValueError('Request must be between 1 byte and 6 MB.')
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError('Expected a JSON object.')
                if self.path == '/api/paper/control' and paper is not None:
                    paper.set_enabled(body.get('enabled'))
                    self.reply(200, paper.snapshot())
                elif self.path == '/api/import':
                    if not isinstance(body.get('csv'), str) or len(body['csv'].encode()) > 5_000_000:
                        raise ValueError('Supply CSV text of at most 5 MB.')
                    bars, meta = parse_csv(body['csv'])
                    meta['source'] = str(body.get('name', 'User CSV'))[:120]
                    store.save_data(bars, meta)
                    self.reply(200, meta)
                elif self.path == '/api/fetch-ecb':
                    bars, meta = fetch_ecb(body.get('start', '2022-01-01'), body.get('end', '2026-11-17'))
                    store.save_data(bars, meta)
                    self.reply(200, meta)
                elif self.path == '/api/backtest':
                    cfg = Config.from_dict(body.get('config', {}))
                    meta, bars = store.dataset(body.get('dataset_id'))
                    result = run_research(bars, cfg)
                    result['dataset'] = meta
                    self.reply(200, store.save_run(meta['sha256'], result))
                else:
                    self.reply(404, {'error': 'Not found.'})
            except (ValueError, TypeError, KeyError) as exc:
                self.reply(400, {'error': str(exc)})
            except Exception:
                logging.exception('POST failed')
                self.reply(500, {'error': 'Request failed; check source access or the local server log.'})

    return Handler


def serve(port=8765, database=None, quote_file=None):
    store = Store(database or ROOT / '.local' / 'runtime' / 'lab.sqlite3')
    reader = QuoteReader(quote_file)
    # Bind before starting a collector so a duplicate launch cannot leave an orphan worker.
    server = ThreadingHTTPServer(('127.0.0.1', port), handler_for(store, reader))
    try:
        paper = PaperService(store, reader)
    except Exception:
        server.server_close()
        raise
    server.RequestHandlerClass = handler_for(store, reader, paper)
    paper.start()
    print(f'Quant Systems Lab: http://127.0.0.1:{server.server_port} (research only)', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        paper.stop()
        server.server_close()
