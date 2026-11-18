#!/usr/bin/env python3
"""Compile the read-only script with an existing Wine MT5 install; optionally install."""

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', type=Path, default=Path.home() / '.mt5')
    parser.add_argument('--terminal', type=Path, help='Existing terminal installation/data folder containing MQL5 and MetaEditor64.exe.')
    parser.add_argument('--install', action='store_true', help='Copy the verified source and compiled script into MQL5/Scripts/QSLab.')
    parser.add_argument('--script', choices=('quotes', 'history'), default='quotes', help='Compile the continuous quote bridge or one-shot closed-D1 exporter.')
    args = parser.parse_args()
    prefix = args.prefix.expanduser().resolve()
    terminal = (args.terminal or prefix / 'drive_c' / 'Program Files' / 'MetaTrader 5').resolve()
    editor = terminal / 'MetaEditor64.exe'
    if not editor.is_file() or not (terminal / 'MQL5' / 'Scripts').is_dir():
        parser.error('Select an existing MT5 installation/data folder; no software will be installed.')
    build = ROOT / '.local' / 'mt5-bridge' / 'build'
    build.mkdir(parents=True, exist_ok=True, mode=0o700)
    source = build / ('QSLQuoteBridge.mq5' if args.script == 'quotes' else 'QSLHistoryExport.mq5')
    binary = source.with_suffix('.ex5')
    log = source.with_suffix('.log')
    shutil.copyfile(ROOT / 'mt5' / source.name, source)
    for generated in (binary, log):
        generated.unlink(missing_ok=True)
    env = dict(os.environ, WINEPREFIX=str(prefix), WINEDEBUG='-all')
    windows_path = subprocess.check_output(['winepath', '-w', str(source)], env=env, text=True).strip()
    with (build / (source.stem+'-compiler-output.txt')).open('wb') as output:
        # MetaEditor may return a nonzero exit code even after successful compilation.
        subprocess.run(['wine', str(editor), '/compile:' + windows_path, '/log'], env=env,
                       stdout=output, stderr=subprocess.STDOUT, timeout=120, check=False)
    result = log.read_text(encoding='utf-16') if log.exists() else ''
    if not binary.is_file() or '0 errors, 0 warnings' not in result:
        raise SystemExit('Compilation not verified. Review the ignored local compiler log.')
    print(source.stem+' compiled: 0 errors, 0 warnings.')
    print('Source SHA256: ' + hashlib.sha256(source.read_bytes()).hexdigest())
    if args.install:
        destination = terminal / 'MQL5' / 'Scripts' / 'QSLab'
        destination.mkdir(exist_ok=True)
        for artifact in (source, binary):
            shutil.copyfile(artifact, destination / artifact.name)
        print('Installed QSLab/'+source.stem+'. Attach it to '+('a separate EURUSD chart; keep the quote bridge running.' if args.script == 'history' else 'an EURUSD chart; no Algo Trading permission is needed.'))


if __name__ == '__main__':
    main()
