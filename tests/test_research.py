"""Research accounting, data boundaries and persistence; synthetic fixtures only."""

import csv
import io
import json
import math
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from qslab.data import parse_csv
from qslab.engine import Config, monte_carlo, run_research, simulate
from qslab.store import Store


def bars(values):
    return [{'date': (date(2024, 1, 1) + timedelta(days=i)).isoformat(), 'close': value}
            for i, value in enumerate(values)]


def csv_text(values, ecb=False):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['TIME_PERIOD', 'OBS_VALUE', 'CURRENCY', 'CURRENCY_DENOM'] if ecb else ['date', 'close'])
    for bar in bars(values):
        writer.writerow([bar['date'], bar['close'], 'USD', 'EUR'] if ecb else [bar['date'], bar['close']])
    return output.getvalue()


def config(**overrides):
    return Config.from_dict({'fast': 2, 'slow': 3, 'evaluation_fraction': 1, 'spread_pips': 0,
                             'slippage_pips': 0, 'commission_bps': 0, 'max_drawdown_pct': 50, **overrides})


class ResearchTests(unittest.TestCase):
    def test_delayed_entry_and_exact_reconciliation(self):
        data = bars([1 + i * .001 for i in range(40)])
        result = simulate(data, config())
        trade = result['trades'][0]
        self.assertEqual(trade['entry_date'], data[3]['date'])
        self.assertEqual(trade['entry_price'], data[3]['close'])
        expected = 5000 / data[3]['close'] * (data[-1]['close'] - data[3]['close'])
        self.assertAlmostEqual(result['metrics']['net_pnl'], expected)
        self.assertAlmostEqual(sum(t['net_pnl'] for t in result['trades']), result['metrics']['net_pnl'])
        self.assertEqual(trade['reason'], 'end_of_test')
        self.assertEqual(result['points'][-1]['position'], 0)

    def test_spread_slippage_and_commission_not_double_counted(self):
        result = simulate(bars([1.] * 40), config(spread_pips=1, slippage_pips=.2, commission_bps=.35), 'buy_hold')
        expected_cost = 2 * 5000 * ((.5 + .2) * .0001 + .35 / 10000)
        self.assertAlmostEqual(result['metrics']['costs'], expected_cost)
        self.assertAlmostEqual(result['metrics']['net_pnl'], -expected_cost)
        self.assertAlmostEqual(result['trades'][0]['net_pnl'], -expected_cost)

    def test_future_prices_do_not_change_past_equity(self):
        data = bars([1 + .002 * math.sin(i) for i in range(60)])
        changed = [dict(b) for b in data]
        changed[30]['close'] = 3
        first, second = simulate(data, config()), simulate(changed, config())
        self.assertEqual(first['points'][:27], second['points'][:27])

    def test_drawdown_halts_future_entries(self):
        data = bars([1., 1.01, 1.02, 1.03, .70] + [1.1 + .01 * i for i in range(35)])
        result = simulate(data, config(exposure=1, max_drawdown_pct=5))
        self.assertTrue(result['metrics']['halted'])
        self.assertEqual(len(result['events']), 1)
        self.assertEqual(result['trades'][0]['reason'], 'risk_stop')
        self.assertTrue(all(p['position'] == 0 for p in result['points'][1:]))

    def test_short_pnl_and_carrying_reconcile(self):
        data = bars([1.2 - i * .001 for i in range(50)])
        result = simulate(data, config(directions='long_short', carrying_bps_daily=1))
        self.assertEqual(result['trades'][0]['side'], 'SHORT')
        self.assertGreater(result['metrics']['net_pnl'], 0)
        self.assertGreater(result['metrics']['costs'], 0)
        self.assertAlmostEqual(sum(t['net_pnl'] for t in result['trades']), result['metrics']['net_pnl'])

    def test_exit_cost_breach_halts_on_the_same_observation(self):
        data = bars([1., 1.01, 1.02, 1.03, 1.029, 1.028] + [1.028] * 34)
        result = simulate(data, config(exposure=1, commission_bps=100, max_drawdown_pct=2))
        self.assertTrue(result['metrics']['halted'])
        self.assertEqual(result['events'][0]['date'], data[6]['date'])
        self.assertEqual(len(result['trades']), 1)

    def test_no_signal_means_cash_and_zero_trades(self):
        result = simulate(bars([1.] * 50), config())
        self.assertEqual(result['metrics']['trades'], 0)
        self.assertEqual(result['metrics']['final_equity'], 10000)
        self.assertIsNone(result['metrics']['sharpe'])

    def test_results_are_finite_json_and_bootstrap_is_reproducible(self):
        data = bars([1 + .02 * math.sin(i / 4) for i in range(100)])
        first, second = run_research(data, config()), run_research(data, config())
        self.assertEqual(first, second)
        json.dumps(first, allow_nan=False)
        self.assertTrue(first['monte_carlo']['available'])
        self.assertEqual(first['monte_carlo']['paths'], 200)
        self.assertFalse(monte_carlo([{'equity': 0}], 10000, 10)['available'])

    def test_configuration_rejects_bad_inputs(self):
        for raw in ({'fast': 3.5}, {'fast': 60, 'slow': 20}, {'capital': float('nan')},
                    {'exposure': 3}, {'directions': 'unknown'}, {'unknown': 1}, {'slow': True}):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                Config.from_dict(raw)


class ImportTests(unittest.TestCase):
    def test_canonical_and_ecb_import_have_provenance(self):
        values = [1 + i * .001 for i in range(100)]
        regular, meta = parse_csv(csv_text(values))
        reference, source = parse_csv(csv_text(values, ecb=True))
        self.assertEqual(regular, reference)
        self.assertEqual(meta['rows'], 100)
        self.assertEqual(len(meta['sha256']), 64)
        self.assertEqual(source['kind'], 'reference_rate')

    def test_invalid_data_is_not_silently_fixed(self):
        good = csv_text([1.] * 40)
        bad = [good.replace('2024-01-02', '2024-01-01'), good.replace('1.0', 'NaN', 1),
               good.replace('1.0', '-1', 1), 'date,close\n2024-01-01,1\n',
               csv_text([1.] * 40, ecb=True).replace('USD', 'GBP', 1)]
        for text in bad:
            with self.subTest(text=text[:40]), self.assertRaises(ValueError):
                parse_csv(text)

    def test_local_storage_preserves_each_completed_experiment(self):
        data, meta = parse_csv(csv_text([1 + i * .001 for i in range(80)]))
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'lab.sqlite3')
            store.save_data(data, meta)
            result = run_research(data, config())
            result['dataset'] = meta
            saved = store.save_run(meta['sha256'], result)
            self.assertEqual(store.run(saved['id']), saved)
            self.assertEqual(store.dataset()[1], data)
            self.assertEqual(store.runs()[0]['dataset_id'], meta['sha256'])


if __name__ == '__main__':
    unittest.main()
