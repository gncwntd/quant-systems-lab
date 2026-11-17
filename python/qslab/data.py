"""Strict daily-series import and an explicit ECB reference-rate adapter."""

import csv
import hashlib
import io
import math
from datetime import date
from urllib.request import Request, urlopen


def parse_csv(text):
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    headers = reader.fieldnames or []
    if len(headers) != len(set(headers)):
        raise ValueError('Duplicate CSV column names are not allowed.')
    ecb = 'TIME_PERIOD' in headers and 'OBS_VALUE' in headers
    if not ecb and not {'date', 'close'}.issubset(headers):
        raise ValueError('CSV requires date,close columns or ECB TIME_PERIOD,OBS_VALUE columns.')
    bars = []
    for row in reader:
        if ecb:
            if row.get('CURRENCY', 'USD') != 'USD' or row.get('CURRENCY_DENOM', 'EUR') != 'EUR':
                raise ValueError('Only USD per EUR is supported; mixed currency series rejected.')
            day, value = row['TIME_PERIOD'], row['OBS_VALUE']
        else:
            day, value = row['date'], row['close']
        try:
            day = date.fromisoformat(day.strip()).isoformat()
            value = float(value)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError(f'Invalid date or price on CSV row {reader.line_num}.') from exc
        if not math.isfinite(value) or value <= 0:
            raise ValueError('Prices must be finite and positive.')
        if bars and day <= bars[-1]['date']:
            raise ValueError('Dates must be unique and strictly increasing; input is not silently reordered.')
        bars.append({'date': day, 'close': value})
        if len(bars) > 10000:
            raise ValueError('At most 10,000 daily observations are supported.')
    if len(bars) < 30:
        raise ValueError('At least 30 daily observations are required.')
    gaps = [(date.fromisoformat(b['date']) - date.fromisoformat(a['date'])).days
            for a, b in zip(bars, bars[1:])]
    return bars, {
        'sha256': hashlib.sha256(text.encode()).hexdigest(),
        'rows': len(bars), 'start': bars[0]['date'], 'end': bars[-1]['date'],
        'max_calendar_gap_days': max(gaps),
        'kind': 'reference_rate' if ecb else 'user_supplied_daily',
        'quality': 'Validated dates, ordering and positive prices; not a bid/ask or completeness audit.',
    }


def fetch_ecb(start, end):
    start = date.fromisoformat(start).isoformat()
    end = date.fromisoformat(end).isoformat()
    if start >= end:
        raise ValueError('Start date must precede end date.')
    url = ('https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A'
           f'?startPeriod={start}&endPeriod={end}&format=csvdata')
    request = Request(url, headers={'Accept': 'text/csv', 'User-Agent': 'QuantSystemsLab/0.1'})
    with urlopen(request, timeout=30) as response:
        raw = response.read(5_000_001)
    if len(raw) > 5_000_000:
        raise ValueError('ECB response exceeds the import limit.')
    text = raw.decode('utf-8-sig')
    bars, meta = parse_csv(text)
    meta.update(source='ECB daily EUR/USD reference rates', source_url=url, kind='reference_rate')
    return bars, meta
