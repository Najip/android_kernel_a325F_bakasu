#!/usr/bin/env python3
"""Preflight locked patches sequentially in disposable clones; --apply opts in.
Requires clean trees and exact source pins. Reapplication fails closed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def git(directory, *args):
    return subprocess.run(['git', '-C', str(directory), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode()

def require(condition, message):
    if not condition:
        raise ValueError(message)

def clean(directory):
    require(not git(directory, 'status', '--porcelain', '--untracked-files=all',
                    '--ignore-submodules=all').strip(), str(directory) + ': clean source tree required')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    lock = json.loads((ROOT / 'patches/xxksu/source-lock.json').read_text())
    require(set(lock['sources']) == {'KernelSU', 'NonGKI_Kernel_Build_2nd'}, 'unexpected source lock')
    clean(ROOT)
    for name, expected in lock['sources'].items():
        directory = ROOT / name
        require((directory / '.git').exists(), name + ': uninitialized submodule')
        recorded = git(ROOT, 'ls-tree', 'HEAD', '--', name).split()
        require(len(recorded) >= 3 and recorded[0] == '160000' and recorded[2] == expected,
                name + ': committed gitlink differs from source lock')
        require(git(directory, 'rev-parse', 'HEAD').strip() == expected, name + ': HEAD differs from source lock')
        clean(directory)
    entries = lock.get('patches', [])
    require(len(entries) == 6 and {p['target'] for p in entries} == {'.', 'KernelSU'}, 'expected six-patch series')
    patches = []
    seen = set()
    for entry in entries:
        require(entry['target'] in ('.', 'KernelSU'), 'unsupported target')
        path = (ROOT / entry['path']).resolve()
        require(path.is_relative_to((ROOT / 'patches/xxksu').resolve()), 'patch escapes patch directory')
        require(path not in seen, 'duplicate patch')
        seen.add(path)
        require(hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256'], 'hash mismatch: ' + entry['path'])
        if entry['target'] == 'KernelSU':
            patches.append((entry['target'], path))
    with tempfile.TemporaryDirectory(prefix='xxksu-preflight-') as temporary:
        trees = {}
        for target in ('.', 'KernelSU'):
            source = ROOT if target == '.' else ROOT / target
            destination = Path(temporary) / ('parent' if target == '.' else target)
            git(ROOT, 'clone', '--shared', '--no-checkout', '--', str(source), str(destination))
            git(destination, 'checkout', '--detach', git(source, 'rev-parse', 'HEAD').strip())
            trees[target] = destination
        for target, patch in patches:
            git(trees[target], 'apply', '--check', str(patch))
            git(trees[target], 'apply', str(patch))
        for directory in trees.values():
            git(directory, 'diff', '--check')
        for target, patch in reversed(patches):
            git(trees[target], 'apply', '--reverse', '--check', str(patch))
            git(trees[target], 'apply', '--reverse', str(patch))
        for directory in trees.values():
            clean(directory)
    applied = []
    if args.apply:
        try:
            for target, patch in patches:
                directory = ROOT if target == '.' else ROOT / target
                git(directory, 'apply', '--check', str(patch))
                git(directory, 'apply', str(patch))
                applied.append((directory, patch))
            git(ROOT, 'diff', '--check')
            git(ROOT / 'KernelSU', 'diff', '--check')
        except Exception:
            for directory, patch in reversed(applied):
                git(directory, 'apply', '--reverse', str(patch))
            raise
    print(json.dumps({'mode': 'apply' if args.apply else 'check', 'sources': lock['sources'],
                      'patches': entries, 'sequential_preflight': 'PASS',
                      'reverse_application': 'PASS', 'clean_restoration': 'PASS'}, indent=2))

if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print('xxKSU preparation failed: ' + str(exc), file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError):
            print(exc.stderr.decode(errors='replace'), file=sys.stderr)
        sys.exit(1)
