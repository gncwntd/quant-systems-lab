"""Local, ignored experiment records; every run keeps its data hash and configuration."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS datasets (id TEXT PRIMARY KEY, created TEXT, meta TEXT, bars TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, created TEXT, dataset_id TEXT, result TEXT)')
        self.path.chmod(0o600)

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def save_data(self, bars, meta):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO datasets VALUES (?, ?, ?, ?)',
                       (meta['sha256'], datetime.now(timezone.utc).isoformat(), json.dumps(meta), json.dumps(bars)))
        return meta

    def dataset(self, dataset_id=None):
        with self.connect() as db:
            row = (db.execute('SELECT meta,bars FROM datasets WHERE id=?', (dataset_id,)).fetchone()
                   if dataset_id else db.execute('SELECT meta,bars FROM datasets ORDER BY created DESC LIMIT 1').fetchone())
        if not row:
            raise ValueError('Import a dataset before running an experiment.')
        return json.loads(row[0]), json.loads(row[1])

    def save_run(self, dataset_id, result):
        run_id = uuid.uuid4().hex
        created = datetime.now(timezone.utc).isoformat()
        result.update(id=run_id, created=created, dataset_id=dataset_id)
        with self.connect() as db:
            db.execute('INSERT INTO runs VALUES (?, ?, ?, ?)', (run_id, created, dataset_id, json.dumps(result, allow_nan=False)))
        return result

    def runs(self):
        with self.connect() as db:
            rows = db.execute('SELECT id,created,dataset_id,result FROM runs ORDER BY created DESC LIMIT 50').fetchall()
        return [{'id': row[0], 'created': row[1], 'dataset_id': row[2],
                 'metrics': json.loads(row[3])['metrics'], 'config': json.loads(row[3])['config']} for row in rows]

    def run(self, run_id):
        with self.connect() as db:
            row = db.execute('SELECT result FROM runs WHERE id=?', (run_id,)).fetchone()
        if not row:
            raise ValueError('Experiment not found.')
        return json.loads(row[0])
