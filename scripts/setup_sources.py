#!/usr/bin/env python3
"""Download KernelSU at the commit pinned in sources.json and apply patches/kernelsu/.

Run from anywhere:  python3 scripts/setup_sources.py [OUT_DIR]
The source goes to ./KernelSU (ignored by git). Running it again is safe.
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


def download(pin):
    KSU.mkdir(exist_ok=True)
    git(KSU, 'init', '-q')
    git(KSU, 'remote', 'add', 'origin', pin['repo'])
    print('Downloading %s %s' % (pin['name'], pin['commit']))
    if pin.get('full_history'):
        # The version number is computed from the commit count, so fetch the whole
        # history (commits and trees only; file contents are fetched on checkout).
        fetch = ['fetch', '-q', '--filter=blob:none', '--tags', 'origin',
                 '+refs/heads/%s:refs/remotes/origin/%s' % (pin['branch'], pin['branch'])]
    else:
        fetch = ['fetch', '-q', '--depth=1', 'origin', pin['commit']]
    for _ in range(3):
        if git(KSU, *fetch, check=False).returncode == 0:
            break
    else:
        fail('could not download %s from %s' % (pin['name'], pin['repo']))
    target = pin['commit'] if pin.get('full_history') else 'FETCH_HEAD'
    if git(KSU, 'checkout', '-q', '--detach', target, check=False).returncode:
        fail('commit %s is not on branch %s of %s' % (pin['commit'], pin['branch'], pin['repo']))


def main():
    pin = json.loads((ROOT / 'sources.json').read_text())['kernelsu']
    if not (KSU / '.git').exists():
        download(pin)
    head = git(KSU, 'rev-parse', 'HEAD').stdout.strip()
    if head != pin['commit']:
        fail('KernelSU/ is at %s, sources.json wants %s. Delete the KernelSU folder and run again.'
             % (head, pin['commit']))

    patches = sorted((ROOT / 'patches/kernelsu').glob('*.patch'))
    stamp = KSU / '.git' / 'applied-patches'
    wanted = ''.join('%s %s\n' % (hashlib.sha256(p.read_bytes()).hexdigest(), p.name) for p in patches)
    results = []
    if stamp.is_file() and stamp.read_text() == wanted:
        results = [{'patch': p.name, 'result': 'already applied'} for p in patches]
    else:
        if git(KSU, 'status', '--porcelain').stdout.strip():
            fail('KernelSU/ has changes from an older setup. Delete the KernelSU folder and run again.')
        for patch in patches:
            if git(KSU, 'apply', '--check', str(patch), check=False).returncode:
                fail('%s does not apply to %s %s' % (patch.name, pin['name'], pin['commit']))
            git(KSU, 'apply', str(patch))
            results.append({'patch': patch.name, 'result': 'applied'})
        stamp.write_text(wanted)

    describe = git(KSU, 'describe', '--tags', '--always', check=False).stdout.strip()
    summary = {'name': pin['name'], 'repo': pin['repo'], 'commit': head,
               'describe': describe, 'patches': results}
    if pin.get('full_history'):
        summary['commit_count'] = int(git(KSU, 'rev-list', '--count', 'HEAD').stdout)
    text = json.dumps(summary, indent=2) + '\n'
    if len(sys.argv) > 1:
        out = Path(sys.argv[1])
        out.mkdir(parents=True, exist_ok=True)
        (out / 'kernelsu-source.json').write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
