#!/usr/bin/env python3
"""Download xxKSU at the commit pinned in sources.json and apply patches/xxksu/.

Run from anywhere:  python3 scripts/setup_sources.py [OUT_DIR]
The xxKSU source goes to ./KernelSU (ignored by git). Running it again is safe.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
KSU = ROOT / 'KernelSU'


def git(directory, *args, check=True):
    return subprocess.run(['git', '-C', str(directory), *args], check=check,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def fail(message):
    print('Source setup failed: ' + message, file=sys.stderr)
    sys.exit(1)


def main():
    pin = json.loads((ROOT / 'sources.json').read_text())['xxksu']
    if not (KSU / '.git').exists():
        KSU.mkdir(exist_ok=True)
        git(KSU, 'init', '-q')
        git(KSU, 'remote', 'add', 'origin', pin['repo'])
        print('Downloading xxKSU ' + pin['commit'])
        for attempt in range(3):
            if git(KSU, 'fetch', '-q', '--depth=1', 'origin', pin['commit'], check=False).returncode == 0:
                break
        else:
            fail('could not download xxKSU commit ' + pin['commit'])
        git(KSU, 'checkout', '-q', '--detach', 'FETCH_HEAD')
    head = git(KSU, 'rev-parse', 'HEAD').stdout.strip()
    if head != pin['commit']:
        fail('KernelSU/ is at %s, sources.json wants %s. Delete the KernelSU folder and run again.'
             % (head, pin['commit']))

    patches = sorted((ROOT / 'patches/xxksu').glob('*.patch'))
    stamp = KSU / '.git' / 'xxksu-applied-patches'
    wanted = ''.join('%s %s\n' % (hashlib.sha256(p.read_bytes()).hexdigest(), p.name) for p in patches)
    results = []
    if stamp.is_file() and stamp.read_text() == wanted:
        results = [{'patch': p.name, 'result': 'already applied'} for p in patches]
    else:
        if git(KSU, 'status', '--porcelain').stdout.strip():
            fail('KernelSU/ has changes from an older setup. Delete the KernelSU folder and run again.')
        for patch in patches:
            if git(KSU, 'apply', '--check', str(patch), check=False).returncode:
                fail(patch.name + ' does not apply to xxKSU ' + pin['commit'])
            git(KSU, 'apply', str(patch))
            results.append({'patch': patch.name, 'result': 'applied'})
        stamp.write_text(wanted)
    git(KSU, 'diff', '--check')

    summary = {'xxksu_repo': pin['repo'], 'xxksu_commit': head, 'xxksu_patches': results}
    text = json.dumps(summary, indent=2) + '\n'
    if len(sys.argv) > 1:
        out = Path(sys.argv[1])
        out.mkdir(parents=True, exist_ok=True)
        (out / 'xxksu-source.json').write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
