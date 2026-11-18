"""Read-only MT5 demo snapshots, isolated from historical research datasets."""

import json
import math
import time
from pathlib import Path


class QuoteReader:
    def __init__(self, path=None, clock=time.time):
        self.path = Path(path) if path else None
        self.clock = clock

    def snapshot(self):
        base = {'status': 'unavailable', 'quote': None,
                'source': 'MT5 demo terminal', 'sampling_seconds': 1,
                'note': 'Demo snapshots only; not a tick archive or backtest dataset.'}
        try:
            paths = ([self.path] if self.path else list((Path.home() / '.mt5' / 'drive_c' / 'users').glob(
                '*/AppData/Roaming/MetaQuotes/Terminal/Common/Files/QSLab/quote.json')))
            if not paths:
                return dict(base, reason='Start QSLQuoteBridge on an EURUSD chart in MT5.')
            if len(paths) != 1:
                return dict(base, reason='Multiple bridges found; select one with --quote-file.')
            with paths[0].open('rb') as file:
                raw = file.read(8193)
            if len(raw) > 8192:
                raise ValueError('Snapshot exceeds the size limit.')
            data = json.loads(raw)
            if not isinstance(data, dict) or type(data.get('schema')) is not int or data['schema'] != 1:
                raise ValueError('Unsupported bridge schema.')
            for key in ('demo', 'connected', 'valid'):
                if type(data.get(key)) is not bool:
                    raise ValueError('Invalid bridge flags.')
            if data.get('symbol') != 'EURUSD':
                raise ValueError('Expected the EURUSD bridge.')
            if not data['demo']:
                return dict(base, status='blocked', reason='Only demo accounts are accepted.')
            server = data.get('server')
            if not isinstance(server, str) or not 1 <= len(server) <= 80 or not all(c.isalnum() or c in '-_. ' for c in server):
                raise ValueError('Invalid server label.')
            base['source'] = server + ' / MT5 demo'
            heartbeat = data.get('heartbeat_utc')
            if type(heartbeat) is not int or heartbeat <= 0:
                raise ValueError('Invalid bridge timestamp.')
            age = self.clock() - heartbeat
            if age < -2:
                return dict(base, status='clock_error', reason='Bridge clock is ahead; check the computer clock.')
            if age > 5:
                return dict(base, status='stale', reason='Bridge heartbeat expired; MT5 or the script may be stopped.')
            if not data['connected']:
                return dict(base, status='disconnected', reason='MT5 is disconnected from the demo server.')
            if not data['valid']:
                return dict(base, reason='MT5 has no valid EURUSD quote yet.')
            bid, ask = data.get('bid'), data.get('ask')
            if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 < v < 100 for v in (bid, ask)) or ask < bid:
                raise ValueError('Invalid bid/ask prices.')
            digits, tick, tick_age = (data.get(key) for key in ('digits', 'tick_time_msc', 'tick_age_ms'))
            if type(digits) is not int or not 2 <= digits <= 8:
                raise ValueError('Invalid symbol precision.')
            if type(tick) is not int or not 0 < tick < 100_000_000_000_000 or type(tick_age) is not int:
                raise ValueError('Invalid tick clock.')
            if tick_age < -2000:
                return dict(base, status='clock_error', reason='Demo server clock estimate is inconsistent.')
            quote_age = max(0, tick_age / 1000) + max(0, age)
            # Construct an allowlist; arbitrary input fields never reach the HTTP API.
            quote = {'symbol': 'EURUSD', 'bid': bid, 'ask': ask, 'digits': digits,
                     'spread_pips': round((ask - bid) / .0001, 4),
                     'heartbeat_utc': heartbeat, 'heartbeat_age_seconds': round(max(0, age), 1),
                     'tick_time_msc': tick, 'quote_age_seconds': round(quote_age, 1),
                     'tick_clock': 'Raw MT5 server timestamp; age is a client-side server-clock estimate.'}
            return dict(base, status='fresh' if quote_age <= 15 else 'stale', quote=quote,
                        reason='Receiving demo quotes.' if quote_age <= 15 else 'Quote timestamp appears old against the MT5 server-clock estimate; check the feed and computer clock.')
        except FileNotFoundError:
            return dict(base, reason='Bridge file not found; start QSLQuoteBridge in MT5.')
        except (OSError, ValueError, TypeError, OverflowError):
            return dict(base, status='invalid', reason='Bridge snapshot unreadable or invalid; waiting for a valid update.')
