import argparse
import json

from .data import fetch_ecb
from .server import ROOT, serve
from .store import Store
from .mt5_history import load_history


def main():
    parser = argparse.ArgumentParser(description='Local EUR/USD research lab; no live trading.')
    commands = parser.add_subparsers(dest='command', required=True)
    web = commands.add_parser('serve')
    web.add_argument('--port', type=int, default=8765)
    web.add_argument('--database', help='Separate local SQLite file for an independent research/paper workspace.')
    web.add_argument('--quote-file', help='Explicit local QSLQuoteBridge JSON path; otherwise discover Wine MT5 common files.')
    fetch = commands.add_parser('fetch-ecb')
    fetch.add_argument('--start', default='2022-01-01')
    fetch.add_argument('--end', default='2026-11-17')
    history = commands.add_parser('inspect-mt5-history', help='Validate a one-shot closed-D1 export; optional local research import.')
    history.add_argument('--file', help='Explicit local history.json export; otherwise discover MT5 common files.')
    history.add_argument('--import-data', action='store_true', help='Archive the validated bundle and set it as the latest daily research dataset. Paper state is unaffected.')
    history.add_argument('--database', help='Destination research database when importing.')
    args = parser.parse_args()
    if args.command == 'serve':
        serve(args.port, database=args.database, quote_file=args.quote_file)
    elif args.command == 'inspect-mt5-history':
        try:
            bars, meta, raw = load_history(args.file)
            if args.import_data:
                database = args.database or ROOT / '.local/runtime/lab.sqlite3'
                store = Store(database)
                archive = store.path.parent / 'mt5-history'
                archive.mkdir(exist_ok=True, mode=0o700)
                artifact = archive / (meta['sha256']+'.json')
                artifact.write_bytes(raw)
                artifact.chmod(0o600)
                store.save_data(bars, meta)
            print(json.dumps(dict(meta, imported=args.import_data), indent=2))
        except ValueError as exc:
            parser.error(str(exc))
    else:
        bars, meta = fetch_ecb(args.start, args.end)
        Store(ROOT / '.local' / 'runtime' / 'lab.sqlite3').save_data(bars, meta)
        print(json.dumps(meta, indent=2))


if __name__ == '__main__':
    main()
