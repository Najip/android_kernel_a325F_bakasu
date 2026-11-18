#!/usr/bin/env python3
"""Validate pinned sources and apply reviewed integration patches.

Not wired into the builder until source-lock.json contains both patch sets.
A check never modifies sources. Apply refuses unrelated tracked changes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'patches/xxksu/source-lock.json'

def git(directory, *args, data=None, check=True):
    return subprocess.run(['git', '-C', str(directory), *args], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)

def fail(message):
    raise SystemExit('xxKSU preparation: ' + message)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='apply after all validation succeeds; default checks only')
    args = parser.parse_args()
    lock = json.loads(LOCK.read_text())
    revisions = {}
    for name, expected in lock['sources'].items():
        directory = ROOT / name
        if not (directory / '.git').exists():
            fail(name + ': submodule not initialized')
        actual = git(directory, 'rev-parse', 'HEAD').stdout.decode().strip()
        recorded = git(ROOT, 'ls-tree', 'HEAD', '--', name).stdout.decode().split()
        if actual != expected or len(recorded) < 3 or recorded[0] != '160000' or recorded[2] != expected:
            fail(name + ': HEAD and committed gitlink must both match ' + expected)
        revisions[name] = actual
    patches = lock.get('patches', [])
    if not patches or {p['target'] for p in patches} != {'.', 'KernelSU'}:
        fail('integration incomplete: reviewed parent-kernel and KernelSU patch sets are both required')
    grouped = {}
    metadata = []
    for entry in patches:
        target = entry['target']
        if target not in ('.', 'KernelSU'):
            fail('unsupported patch target: ' + target)
        path = (ROOT / entry['path']).resolve()
        if not path.is_relative_to(ROOT / 'patches/xxksu'):
            fail('patch must live under patches/xxksu')
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != entry['sha256']:
            fail('patch hash mismatch: ' + entry['path'])
        grouped.setdefault(target, []).append(data)
        metadata.append({'path': entry['path'], 'sha256': digest, 'target': target})
    plans = []
    for target, pieces in grouped.items():
        directory = ROOT if target == '.' else ROOT / target
        data = b'\n'.join(pieces)
        if git(directory, 'apply', '--check', '--reverse', '-', data=data, check=False).returncode == 0:
            plans.append((directory, data, 'already applied'))
            continue
        dirty = git(directory, 'diff', '--name-only', 'HEAD', '--ignore-submodules=all').stdout.strip()
        if dirty:
            fail(target + ': unrelated tracked changes; use a clean checkout')
        result = git(directory, 'apply', '--check', '-', data=data, check=False)
        if result.returncode:
            fail(target + ': patch validation failed: ' + result.stderr.decode(errors='replace'))
        plans.append((directory, data, 'ready'))
    applied = []
    try:
        if args.apply:
            for directory, data, status in plans:
                if status == 'ready':
                    git(directory, 'apply', '-', data=data)
                    applied.append((directory, data))
    except subprocess.CalledProcessError:
        for directory, data in reversed(applied):
            git(directory, 'apply', '--reverse', '-', data=data)
        raise
    print(json.dumps({'mode': 'apply' if args.apply else 'check', 'sources': revisions, 'patches': metadata, 'targets': [{'target': str(d.relative_to(ROOT)) or '.', 'status': 'applied' if args.apply and s == 'ready' else s} for d, _, s in plans]}, indent=2))

if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print('xxKSU preparation failed: ' + str(exc), file=sys.stderr)
        sys.exit(1)
