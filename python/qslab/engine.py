"""Deterministic daily reference-price simulation with explicit delayed decisions."""

import hashlib
import math
import random
import statistics
from dataclasses import asdict, dataclass, fields
from datetime import date
from pathlib import Path

ENGINE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


@dataclass(frozen=True)
class Config:
    fast: int = 20
    slow: int = 60
    capital: float = 10000.0
    exposure: float = 0.5
    spread_pips: float = 1.0
    slippage_pips: float = 0.2
    commission_bps: float = 0.35
    carrying_bps_daily: float = 0.0
    max_drawdown_pct: float = 10.0
    evaluation_fraction: float = 0.3
    directions: str = 'long_only'

    @classmethod
    def from_dict(cls, raw):
        if not isinstance(raw, dict) or set(raw) - {f.name for f in fields(cls)}:
            raise ValueError('Unknown configuration fields.')
        values = asdict(cls())
        for key, value in raw.items():
            if key == 'directions':
                values[key] = value
                continue
            if isinstance(value, bool):
                raise ValueError('Numeric settings cannot be booleans.')
            try:
                number = float(value)
            except (ValueError, TypeError) as exc:
                raise ValueError(f'Invalid number for {key}.') from exc
            if not math.isfinite(number):
                raise ValueError('Configuration must contain finite numbers.')
            if key in ('fast', 'slow') and number != int(number):
                raise ValueError('Moving-average windows must be integers.')
            values[key] = int(number) if key in ('fast', 'slow') else number
        cfg = cls(**values)
        if not 2 <= cfg.fast < cfg.slow <= 250:
            raise ValueError('Require 2 ≤ fast < slow ≤ 250.')
        bounds = {'capital': (100, 1e7), 'exposure': (0.01, 1), 'spread_pips': (0, 50),
                  'slippage_pips': (0, 50), 'commission_bps': (0, 100),
                  'carrying_bps_daily': (0, 100), 'max_drawdown_pct': (0.1, 50),
                  'evaluation_fraction': (0.1, 1)}
        for key, (low, high) in bounds.items():
            if not low <= getattr(cfg, key) <= high:
                raise ValueError(f'{key} must be between {low} and {high}.')
        if cfg.directions not in ('long_only', 'long_short'):
            raise ValueError('Unsupported direction mode.')
        return cfg


def signals(bars, cfg):
    prices = [b['close'] for b in bars]
    result = []
    for i in range(len(prices)):
        if i + 1 < cfg.slow:
            result.append(0)
            continue
        fast = statistics.fmean(prices[i + 1 - cfg.fast:i + 1])
        slow = statistics.fmean(prices[i + 1 - cfg.slow:i + 1])
        result.append(1 if fast > slow else (-1 if fast < slow and cfg.directions == 'long_short' else 0))
    return result


def regime(bars, cfg):
    prices = [b['close'] for b in bars]
    if len(prices) < cfg.slow:
        return {'label': 'Insufficient history', 'volatility_pct': None, 'gap_pct': None}
    gap = statistics.fmean(prices[-cfg.fast:]) / statistics.fmean(prices[-cfg.slow:]) - 1
    window = prices[-21:]
    returns = [b / a - 1 for a, b in zip(window, window[1:])]
    vol = statistics.stdev(returns) * math.sqrt(252) if len(returns) > 1 else 0
    return {'label': 'Trend up' if gap > .002 else ('Trend down' if gap < -.002 else 'Range'),
            'volatility_pct': vol * 100, 'gap_pct': gap * 100,
            'volatility_label': 'Elevated' if vol >= .15 else 'Normal',
            'method': 'Descriptive SMA gap ±0.2%; trailing 20-return volatility, not a predictive model.'}


def simulate(bars, cfg, strategy='sma'):
    if len(bars) < cfg.slow + 10:
        raise ValueError(f'Need at least {cfg.slow + 10} observations for these windows.')
    start = max(cfg.slow, int(len(bars) * (1 - cfg.evaluation_fraction)))
    if len(bars) - start < 10:
        raise ValueError('Evaluation window needs at least ten observations.')
    decisions = signals(bars, cfg) if strategy == 'sma' else [1] * len(bars)
    equity = cfg.capital
    peak = equity
    units = 0.0
    entry = None
    costs = 0.0
    halted = False
    trades, points, events = [], [], []

    def side_cost(quantity, price):
        return abs(quantity) * ((cfg.spread_pips / 2 + cfg.slippage_pips) * .0001
                                + price * cfg.commission_bps / 10000)

    def close_position(day, price, reason):
        nonlocal units, entry, equity, costs
        fee = side_cost(units, price)
        equity -= fee
        costs += fee
        gross = units * (price - entry['entry_price'])
        trades.append({**entry, 'exit_date': day, 'exit_price': price, 'reason': reason,
                       'gross_pnl': gross,
                       'costs': entry['entry_cost'] + entry['carrying_cost'] + fee,
                       'net_pnl': gross - entry['entry_cost'] - entry['carrying_cost'] - fee})
        units, entry = 0.0, None

    for i in range(start, len(bars)):
        day, price = bars[i]['date'], bars[i]['close']
        if units:
            previous = bars[i - 1]
            days = (date.fromisoformat(day) - date.fromisoformat(previous['date'])).days
            carry = abs(units) * previous['close'] * cfg.carrying_bps_daily / 10000 * days
            equity += units * (price - previous['close']) - carry
            costs += carry
            entry['carrying_cost'] += carry
        drawdown = (peak - equity) / peak * 100
        if not halted and drawdown >= cfg.max_drawdown_pct:
            halted = True
            events.append({'date': day, 'type': 'drawdown_stop', 'message': 'Drawdown limit reached; position closed and new entries halted.'})
        target = decisions[i - 1]  # Decision from the previous observation only.
        current = 1 if units > 0 else (-1 if units < 0 else 0)
        final = i == len(bars) - 1
        if units and (target != current or halted or final):
            close_position(day, price, 'risk_stop' if halted else ('end_of_test' if final else 'signal_change'))
        if not halted and (peak - equity) / peak * 100 >= cfg.max_drawdown_pct:
            halted = True
            events.append({'date': day, 'type': 'drawdown_stop', 'message': 'Exit costs reached drawdown limit; new entries halted.'})
        if target and not units and not halted and not final and equity > 0:
            units = target * equity * cfg.exposure / price
            fee = side_cost(units, price)
            equity -= fee
            costs += fee
            entry = {'entry_date': day, 'entry_price': price, 'units': units,
                     'side': 'LONG' if units > 0 else 'SHORT', 'entry_cost': fee, 'carrying_cost': 0.0}
            if (peak - equity) / peak * 100 >= cfg.max_drawdown_pct:
                halted = True
                events.append({'date': day, 'type': 'drawdown_stop', 'message': 'Entry costs reached drawdown limit; trading halted.'})
                close_position(day, price, 'risk_stop')
        peak = max(peak, equity)
        points.append({'date': day, 'price': price, 'equity': equity,
                       'drawdown_pct': (peak - equity) / peak * 100,
                       'position': 1 if units > 0 else (-1 if units < 0 else 0),
                       'decision': decisions[i]})
    daily, previous_equity = [], cfg.capital
    for point in points:
        daily.append(point['equity'] / previous_equity - 1 if previous_equity > 0 else 0)
        previous_equity = point['equity']
    deviation = statistics.stdev(daily) if len(daily) > 1 else 0
    losses = -sum(t['net_pnl'] for t in trades if t['net_pnl'] < 0)
    wins = sum(t['net_pnl'] for t in trades if t['net_pnl'] > 0)
    metrics = {'initial_equity': cfg.capital, 'final_equity': equity,
               'net_pnl': equity - cfg.capital, 'return_pct': (equity / cfg.capital - 1) * 100,
               'max_drawdown_pct': max(p['drawdown_pct'] for p in points),
               'costs': costs, 'trades': len(trades),
               'win_rate_pct': 100 * sum(t['net_pnl'] > 0 for t in trades) / len(trades) if trades else None,
               'profit_factor': wins / losses if losses else None,
               'sharpe': statistics.fmean(daily) / deviation * math.sqrt(252) if deviation and equity > 0 else None,
               'halted': halted}
    return {'metrics': metrics, 'points': points, 'trades': trades, 'events': events,
            'evaluation_start': bars[start]['date'], 'evaluation_end': bars[-1]['date']}


def monte_carlo(points, capital, threshold, seed=42):
    returns, previous = [], capital
    for point in points:
        if point['equity'] <= 0 or previous <= 0:
            return {'available': False, 'reason': 'Non-positive equity prevents return resampling.'}
        returns.append(point['equity'] / previous - 1)
        previous = point['equity']
    if len(returns) < 20:
        return {'available': False, 'reason': 'Need at least twenty evaluation observations.'}
    rng, finals, drawdowns = random.Random(seed), [], []
    horizon = min(252, len(returns))
    for _ in range(200):
        sampled = []
        while len(sampled) < horizon:
            offset = rng.randrange(len(returns))
            sampled.extend(returns[(offset + k) % len(returns)] for k in range(5))
        equity, peak, dd = capital, capital, 0
        for value in sampled[:horizon]:
            equity *= 1 + value
            peak = max(peak, equity)
            dd = max(dd, (peak - equity) / peak * 100)
        finals.append(equity)
        drawdowns.append(dd)
    finals.sort()
    return {'available': True, 'paths': 200, 'block_size': 5, 'seed': seed,
            'horizon_observations': horizon, 'final_p05': finals[9], 'final_median': statistics.median(finals),
            'final_p95': finals[189], 'loss_probability_pct': 100 * sum(x < capital for x in finals) / 200,
            'drawdown_breach_pct': 100 * sum(x >= threshold for x in drawdowns) / 200,
            'method': 'Circular five-return block bootstrap of net historical returns; no forecast or new strategy response.'}


def run_research(bars, cfg):
    result = simulate(bars, cfg)
    baseline = simulate(bars, cfg, 'buy_hold')
    result.update(config=asdict(cfg), strategy='SMA crossover', engine_version='daily-reference-v1',
                  engine_sha256=ENGINE_SHA256,
                  regime=regime(bars, cfg), benchmark={'name': 'Long EUR reference, same costs/risk',
                                                    'metrics': baseline['metrics'], 'points': baseline['points']},
                  monte_carlo=monte_carlo(result['points'], cfg.capital, cfg.max_drawdown_pct),
                  assumptions=[
                      'USD account; EUR/USD daily single-price observations, not executable bid/ask quotes.',
                      'Signal after observation t; hypothetical execution at observation t+1 with estimated side costs.',
                      'No intraday fills; no depth, gaps, margin or broker execution model. Drawdown stop checks observations only.',
                      'Final position liquidated with estimated exit costs; no new position opened on the final observation.',
                      'SMA parameters selected manually; repeated runs on the same evaluation window can overfit.',
                      'Carrying costs are an explicit estimate; zero is not evidence that financing is free.',
                      'Regime is descriptive; Monte Carlo is conditional resampling, not prediction.'
                  ])
    return result
