"""Audit pagination, independent cash reconstruction and cutoff export contracts."""

import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

from test_paper import CONFIG, START, Reader, snapshot
from qslab.paper import PaperService
from qslab.paper_journal import read_journal, export_lines
from qslab.store import Store


class PaperJournalTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.directory.name)/'lab.sqlite3')
        self.reader = Reader()
        self.now = START
        self.paper = PaperService(self.store, self.reader, CONFIG, clock=lambda: self.now)

    def tearDown(self):
        self.directory.cleanup()

    def step(self, second, mid):
        self.now = START+second
        self.reader.data = snapshot(second, mid)
        self.paper.step()

    def open_position(self):
        for i in range(4):
            for offset in range(0, 60, 5):
                self.step(i*60+offset, 1.1+i*.001)
        self.step(240, 1.104)

    def close_position(self):
        for second in range(245, 300, 5):
            self.step(second, 1.104)
        for minute in range(5, 9):
            for offset in range(0, 60, 5):
                self.step(minute*60+offset, 1.08)

    def test_initial_balance_is_not_reported_as_a_verified_fill(self):
        report = read_journal(self.store)
        self.assertEqual(report['reconciliation']['status'], 'initial_balance')
        self.assertEqual(report['reconciliation']['entries_checked'], 0)
        self.assertEqual(report['records'], [])
        self.assertIsNone(report['next_before'])

    def test_independent_open_and_closed_position_accounting(self):
        self.open_position()
        report = read_journal(self.store)
        self.assertEqual(report['reconciliation']['status'], 'passed')
        self.assertAlmostEqual(report['reconciliation']['expected']['equity'], self.paper.snapshot()['equity'])
        self.assertLess(report['reconciliation']['expected']['unrealized_pnl'], 0)
        self.close_position()
        report = read_journal(self.store)
        self.assertEqual(report['reconciliation']['status'], 'passed')
        self.assertEqual(report['reconciliation']['entries_checked'], 1)
        self.assertEqual(report['reconciliation']['exits_checked'], 1)
        self.assertEqual(report['reconciliation']['expected']['unrealized_pnl'], 0)
        self.assertAlmostEqual(report['reconciliation']['expected']['realized_pnl'], self.paper.snapshot()['realized_pnl'])

    def test_modified_account_and_fill_fees_are_detected(self):
        self.open_position()
        with self.store.connect() as db:
            state = json.loads(db.execute('SELECT state FROM paper_state').fetchone()[0])
            state['cash'] += 1
            db.execute('UPDATE paper_state SET state=?', (json.dumps(state),))
        report = read_journal(self.store)
        self.assertEqual(report['reconciliation']['status'], 'mismatch')
        self.assertIn('cash does not reconcile.', report['reconciliation']['errors'])
        with self.store.connect() as db:
            for event_id, raw in db.execute('SELECT id,payload FROM paper_audit').fetchall():
                record = json.loads(raw)
                if record['kind'] == 'entry':
                    record['fee'] += 2
                    db.execute('UPDATE paper_audit SET payload=? WHERE id=?', (json.dumps(record), event_id))
        errors = read_journal(self.store)['reconciliation']['errors']
        self.assertIn('Entry commission does not reconcile.', errors)

    def test_broken_audit_is_visible_and_never_gets_a_pass_badge(self):
        for payload in ('{', json.dumps(dict(kind='exit', observed_utc=START))):
            with self.store.connect() as db:
                db.execute('DELETE FROM paper_audit')
                db.execute('INSERT INTO paper_audit(session_id,payload) VALUES (?,?)', (self.paper.snapshot()['id'], payload))
            report = read_journal(self.store)
            self.assertEqual(report['reconciliation']['status'], 'invalid_audit')
            self.assertEqual(report['total_records'], 1)
            self.assertEqual(len(report['records']), 1)

    def test_pagination_is_stable_when_new_events_arrive(self):
        for i in range(65):
            self.paper.set_enabled(bool(i%2))
        first = read_journal(self.store, limit=25)
        self.assertEqual(first['total_records'], 65)
        self.assertEqual(len(first['records']), 25)
        self.paper.set_enabled(True)
        second = read_journal(self.store, before=first['next_before'], limit=25)
        third = read_journal(self.store, before=second['next_before'], limit=25)
        ids = [row['id'] for page in (first, second, third) for row in page['records']]
        self.assertEqual(len(ids), 65)
        self.assertEqual(len(set(ids)), 65)
        self.assertIsNone(third['next_before'])
        self.assertEqual(read_journal(self.store, kind='entry')['records'], [])
        self.assertEqual(read_journal(self.store, kind='control')['filtered_records'], 66)

    def test_full_exports_include_all_events_and_exclude_newer_records(self):
        for i in range(65):
            self.paper.set_enabled(bool(i%2))
        report = read_journal(self.store, limit=1)
        self.paper.set_enabled(True)
        lines = [json.loads(line) for line in export_lines(self.store, report, 'jsonl')]
        self.assertEqual(lines[0]['type'], 'session')
        self.assertEqual(lines[-1]['type'], 'end')
        self.assertEqual(lines[-1]['event_count'], 65)
        events = [line for line in lines if line['type'] == 'audit']
        self.assertEqual(len(events), 65)
        self.assertEqual(events[-1]['id'], report['audit_through_id'])
        rows = list(csv.DictReader(io.StringIO(b''.join(export_lines(self.store, report, 'csv')).decode())))
        self.assertEqual(rows[0]['record_type'], 'session')
        self.assertEqual(rows[-1]['record_type'], 'end')
        self.assertEqual(int(rows[-1]['event_count']), 65)
        self.assertEqual(len([row for row in rows if row['record_type'] == 'audit']), 65)
        self.assertIn('engine_sha256', rows[0]['session_json'])

    def test_csv_escapes_formula_text_but_preserves_negative_numbers(self):
        self.open_position()
        self.close_position()
        with self.store.connect() as db:
            db.execute('INSERT INTO paper_audit(session_id,payload) VALUES (?,?)',
                       (self.paper.snapshot()['id'], json.dumps(dict(kind='control', message='=1+1', observed_utc=START))))
        rows = list(csv.DictReader(io.StringIO(b''.join(export_lines(self.store, read_journal(self.store), 'csv')).decode())))
        self.assertTrue(any(row['message'] == "'=1+1" for row in rows))
        self.assertTrue(any(row['net_pnl'].startswith('-') for row in rows))

    def test_query_bounds_are_validated(self):
        for params in (dict(limit=0), dict(limit=101), dict(before=-1), dict(before=2**64), dict(kind='unknown')):
            with self.subTest(params=params), self.assertRaises(ValueError):
                read_journal(self.store, **params)


if __name__ == '__main__':
    unittest.main()
