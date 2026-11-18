"""Bounded MT5 closed-D1 assessment; raw server calendar is never relabeled UTC."""

from datetime import datetime, timezone, date
import hashlib
import json
import math
from pathlib import Path
import time

MAX_BYTES = 2_000_000


def parse_history(raw, now=None):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError('History export must be at most 2 MB of UTF-8 JSON.')
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError('Invalid history JSON.') from exc
    if not isinstance(data, dict) or type(data.get('schema')) is not int or data['schema'] != 1:
        raise ValueError('Unsupported history schema.')
    if data.get('demo') is not True or data.get('symbol') != 'EURUSD' or data.get('timeframe') != 'D1':
        raise ValueError('Only EURUSD D1 demo exports are accepted.')
    server = data.get('server')
    if not isinstance(server, str) or not 1 <= len(server) <= 80 or not all(c.isalnum() or c in '-_. ' for c in server):
        raise ValueError('Invalid source label.')
    def integer(value, minimum=0, maximum=10**14):
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError('Invalid history timestamp, count or volume.')
        return value
    captured = integer(data.get('captured_utc'), 1)
    if captured > (time.time() if now is None else now)+120:
        raise ValueError('History capture is in the future; check the computer clock.')
    current = integer(data.get('current_bar_server_time'), 1, 253402214400)
    digits = integer(data.get('digits'), 2, 8)
    point = data.get('point')
    if type(point) not in (int, float) or not math.isfinite(point) or not math.isclose(point, 10**-digits, rel_tol=1e-8):
        raise ValueError('Symbol point does not match digit precision.')
    source_bars = data.get('bars')
    count = integer(data.get('count'), 30, 1500)
    requested = integer(data.get('requested_bars'), count, 1500)
    if not isinstance(source_bars, list) or len(source_bars) != count:
        raise ValueError('History bar count does not match its manifest.')
    bars, spreads = [], []
    previous = 0
    for row in source_bars:
        if not isinstance(row, dict):
            raise ValueError('Each history row must be an object.')
        timestamp = integer(row.get('server_time'), 1, current-1)
        if timestamp <= previous:
            raise ValueError('History timestamps must increase; duplicates are rejected.')
        previous = timestamp
        # Interpret numeric fields as a raw server-calendar label, not a UTC observation.
        day = datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()
        if bars and day <= bars[-1]['date']:
            raise ValueError('D1 export has duplicate or backward server-calendar dates.')
        prices = [row.get(key) for key in ('open', 'high', 'low', 'close')]
        if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 < v < 100 for v in prices):
            raise ValueError('OHLC prices must be finite, positive EURUSD values.')
        opening, high, low, close = prices
        if not low <= min(opening, close) <= max(opening, close) <= high:
            raise ValueError('OHLC bounds are inconsistent.')
        integer(row.get('tick_volume'))
        integer(row.get('real_volume'))
        spreads.append(integer(row.get('spread_points'), 0, 100000)*point/.0001)
        bars.append(dict(date=day, close=close))
    gaps = [(date.fromisoformat(b['date'])-date.fromisoformat(a['date'])).days for a,b in zip(bars,bars[1:])]
    meta = dict(sha256=hashlib.sha256(raw).hexdigest(), rows=count, start=bars[0]['date'], end=bars[-1]['date'],
                max_calendar_gap_days=max(gaps), kind='mt5_demo_daily', source=server+' / MT5 EURUSD D1',
                captured_utc=captured, requested_bars=requested, forming_bar_excluded=True,
                current_bar_server_time=current, date_basis='Raw MT5 server calendar; timezone unverified.',
                price_basis='MT5 OHLC close; bid/last basis and executability require source assessment.',
                source_spread_pips_min=min(spreads), source_spread_pips_max=max(spreads),
                quality='Validated closed D1 ordering, OHLC and manifest. Coverage, price basis, costs and source rights remain unverified. Reported bar spread is not a full historical bid/ask series.')
    return bars, meta


def load_history(path=None):
    if path:
        selected = Path(path)
    else:
        paths = list((Path.home()/'.mt5/drive_c/users').glob('*/AppData/Roaming/MetaQuotes/Terminal/Common/Files/QSLab/history.json'))
        if len(paths) != 1:
            raise ValueError('Run QSLHistoryExport on a separate MT5 chart, or select one export with --file.')
        selected = paths[0]
    try:
        with selected.open('rb') as file:
            raw = file.read(MAX_BYTES+1)
    except OSError as exc:
        raise ValueError('History export cannot be read; run QSLHistoryExport first.') from exc
    bars, meta = parse_history(raw)
    return bars, meta, raw
