import argparse
import json

from .data import fetch_ecb
from .server import ROOT, serve
from .store import Store


def main():
    parser = argparse.ArgumentParser(description='Local EUR/USD research lab; no live trading.')
    commands = parser.add_subparsers(dest='command', required=True)
    web = commands.add_parser('serve')
    web.add_argument('--port', type=int, default=8765)
    fetch = commands.add_parser('fetch-ecb')
    fetch.add_argument('--start', default='2022-01-01')
    fetch.add_argument('--end', default='2026-11-17')
    args = parser.parse_args()
    if args.command == 'serve':
        serve(args.port)
    else:
        bars, meta = fetch_ecb(args.start, args.end)
        Store(ROOT / '.local' / 'runtime' / 'lab.sqlite3').save_data(bars, meta)
        print(json.dumps(meta, indent=2))


if __name__ == '__main__':
    main()
