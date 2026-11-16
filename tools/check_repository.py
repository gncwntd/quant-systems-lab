#!/usr/bin/env python3
"""Check the Git index publication boundary; never print matched secret values."""

from __future__ import annotations

import posixpath
import re
import subprocess
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 1_000_000
ROOT_FILES = {
    'README.md', 'LICENSE', 'NOTICE', 'CONTRIBUTING.md', 'CODE_OF_CONDUCT.md',
    'SECURITY.md', '.gitignore', '.gitattributes', '.clang-format',
    '.editorconfig', 'CMakeLists.txt', 'CMakePresets.json', 'pyproject.toml',
    'uv.lock', '.env.example',
}
SOURCE_DIRS = {
    '.github', 'docs', 'tools', 'tests', 'core', 'python', 'dashboard',
    'benchmarks', 'examples', 'hdl',
}
PRIVATE_PARTS = {
    '.local', '.aws', '.codex', '.agents', '.ssh', 'node_modules',
    '__pycache__', '.venv', 'build', 'dist', 'logs', 'profiles',
}
SECRET_PATTERNS = (
    ('private key', re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    ('GitHub token', re.compile(r'\bgh[pousr]_[A-Za-z0-9]{36,}\b')),
    ('GitHub fine-grained token', re.compile(r'\bgithub_pat_[A-Za-z0-9_]{30,}\b')),
    ('AWS access key', re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b')),
    ('local home path', re.compile(r'/(?:home|Users)/[A-Za-z0-9_.-]+/')),
)
LINK = re.compile(r'\[[^\]]*\]\(([^\s)]+)\)')


def path_errors(name: str, mode: str = '100644') -> list[str]:
    path = PurePosixPath(name)
    errors = []
    if mode not in {'100644', '100755'}:
        errors.append('only regular source files are permitted')
    if path.is_absolute() or '..' in path.parts:
        errors.append('invalid repository-relative path')
    if any(part in PRIVATE_PARTS for part in path.parts):
        errors.append('private or generated directory')
    if len(path.parts) == 1:
        if name not in ROOT_FILES:
            errors.append('root file is not in the publication allowlist')
    elif path.parts[0] not in SOURCE_DIRS:
        errors.append('directory is not in the publication allowlist')
    if path.name.startswith('.env') and path.name != '.env.example':
        errors.append('real environment configuration is forbidden')
    if path.suffix.lower() in {
        '.pem', '.key', '.p12', '.pfx', '.csv', '.parquet', '.db', '.sqlite',
        '.bin', '.gz', '.zip', '.pt', '.pth', '.pkl', '.joblib', '.log',
    }:
        errors.append('sensitive, generated or external-data extension; review policy first')
    return errors


def content_errors(name: str, data: bytes) -> list[str]:
    if len(data) > MAX_BYTES:
        return ['file exceeds the 1 MB publication limit']
    if b'\x00' in data:
        return ['binary content requires explicit publication review']
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        return ['source text must be UTF-8']
    errors = [label + ' pattern detected' for label, pattern in SECRET_PATTERNS if pattern.search(text)]
    if data and not data.endswith(b'\n'):
        errors.append('missing final newline')
    if any(line.rstrip(' \t') != line for line in text.splitlines()):
        errors.append('trailing whitespace')
    return errors


def link_errors(name: str, text: str, tracked: set[str]) -> list[str]:
    errors = []
    for match in LINK.finditer(text):
        target = match.group(1).strip('<>')
        if target.startswith(('#', 'https://', 'http://', 'mailto:')):
            continue
        target = unquote(target.split('#', 1)[0])
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
        if target.startswith('/') or resolved.startswith('../') or resolved not in tracked:
            errors.append('local Markdown link is missing or outside the public source set')
    return errors


def git(*args: str) -> bytes:
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def main() -> int:
    records = []
    for entry in git('ls-files', '--stage', '-z').split(b'\x00'):
        if not entry:
            continue
        meta, name = entry.decode('utf-8').split('\t', 1)
        mode, oid, stage = meta.split()
        records.append((name, mode, oid, stage))
    if not records:
        print('No tracked files: stage the intended public source set first.')
        return 1
    tracked = {record[0] for record in records}
    failures = []
    for name, mode, oid, stage in records:
        errors = path_errors(name, mode)
        if stage != '0':
            errors.append('unresolved index conflict')
        if int(git('cat-file', '-s', oid)) > MAX_BYTES:
            errors.append('file exceeds the 1 MB publication limit')
        elif mode in {'100644', '100755'}:
            data = git('cat-file', 'blob', oid)
            errors.extend(content_errors(name, data))
            if name.endswith('.md'):
                errors.extend(link_errors(name, data.decode('utf-8', errors='replace'), tracked))
        failures.extend((name, error) for error in errors)
    for name, error in failures:
        print(f'{name}: {error}')
    print(f'Checked {len(records)} indexed files; {len(failures)} publication errors.')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
