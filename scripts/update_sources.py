#!/usr/bin/env python3
"""Check xxKSU and Jack's SUSFS for new commits and update this tree.

What it does:
  xxKSU  - moves the pin in sources.json to the newest commit, but only if
           every patch in patches/xxksu/ still applies to it.
  SUSFS  - moves the pin to Jack's newest commit. If Jack changed the SUSFS
           core (fs/susfs.c, susfs.h, susfs_def.h), the new core files are
           copied in and patches/susfs/ (our small local additions) is applied
           on top. If Jack changed the kernel hook part of his patch, the
           changes are NOT applied automatically; they are listed for review.

Usage: python3 scripts/update_sources.py [--summary FILE]
Exit code 0 = finished (updated or nothing new), 1 = an update was blocked.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CORE = ['fs/susfs.c', 'include/linux/susfs.h', 'include/linux/susfs_def.h']


def run(*args, cwd=None, data=None, check=True):
    return subprocess.run(list(args), cwd=cwd, input=data, check=check,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def latest_commit(repo, branch):
    out = run('git', 'ls-remote', repo, 'refs/heads/' + branch).stdout.decode().split()
    if not out:
        raise RuntimeError('branch %s not found in %s' % (branch, repo))
    return out[0]


def fetch(repo, commits, directory):
    run('git', 'init', '-q', str(directory))
    run('git', '-C', str(directory), 'fetch', '-q', '--depth=1', repo, *commits)


def web(repo):
    return repo[:-4] if repo.endswith('.git') else repo


def sections(patch):
    """Split a patch into {path: text} per file."""
    result = {}
    for part in re.split(rb'(?m)^(?=diff --git )', patch):
        match = re.match(rb'diff --git a/(\S+) b/(\S+)', part)
        if match:
            path = match.group(2).decode()
            result[path] = result.get(path, b'') + part
    return result


def update_xxksu(pin, notes):
    latest = latest_commit(pin['repo'], pin['branch'])
    if latest == pin['commit']:
        notes.append('- xxKSU: already up to date (`%s`).' % latest[:12])
        return False, True
    with tempfile.TemporaryDirectory() as temporary:
        tree = Path(temporary) / 'KernelSU'
        fetch(pin['repo'], [latest], tree)
        run('git', '-C', str(tree), 'checkout', '-q', '--detach', 'FETCH_HEAD')
        for patch in sorted((ROOT / 'patches/xxksu').glob('*.patch')):
            check = run('git', '-C', str(tree), 'apply', '--check', str(patch), check=False)
            if check.returncode:
                notes.append('- xxKSU: update to `%s` BLOCKED. `patches/xxksu/%s` no longer applies:\n'
                             '  ```\n  %s\n  ```' % (latest[:12], patch.name,
                                                   check.stderr.decode(errors='replace').strip()[:1500]))
                return False, False
            run('git', '-C', str(tree), 'apply', str(patch))
    notes.append('- xxKSU: `%s` -> `%s` ([changes](%s/compare/%s...%s)). All xxKSU patches apply.'
                 % (pin['commit'][:12], latest[:12], web(pin['repo']), pin['commit'], latest))
    pin['commit'] = latest
    return True, True


def update_susfs(pin, notes, review):
    latest = latest_commit(pin['repo'], pin['branch'])
    if latest == pin['commit']:
        notes.append('- SUSFS: already up to date (Jack `%s`).' % latest[:12])
        return False, True
    with tempfile.TemporaryDirectory() as temporary:
        temporary = Path(temporary)
        jack = temporary / 'jack'
        fetch(pin['repo'], [pin['commit'], latest], jack)
        old = run('git', '-C', str(jack), 'show', pin['commit'] + ':' + pin['patch']).stdout
        new = run('git', '-C', str(jack), 'show', latest + ':' + pin['patch']).stdout
        old_parts, new_parts = sections(old), sections(new)
        core_changed = any(old_parts.get(p) != new_parts.get(p) for p in CORE)
        hooks = sorted(p for p in set(old_parts) | set(new_parts)
                       if p not in CORE and old_parts.get(p) != new_parts.get(p))
        if core_changed:
            core = temporary / 'core'
            run('git', 'init', '-q', str(core))
            includes = [arg for p in CORE for arg in ('--include', p)]
            run('git', 'apply', *includes, '-', cwd=core, data=new)
            for p in CORE:
                path = core / p
                if not path.is_file():
                    notes.append('- SUSFS: update to `%s` BLOCKED. Jack\'s patch no longer creates `%s`.'
                                 % (latest[:12], p))
                    return False, False
                text = path.read_text()
                path.write_text('\n'.join(line.rstrip() for line in text.split('\n')))
            for patch in sorted((ROOT / 'patches/susfs').glob('*.patch')):
                check = run('git', 'apply', str(patch), cwd=core, check=False)
                if check.returncode:
                    notes.append('- SUSFS: update to `%s` BLOCKED. `patches/susfs/%s` no longer applies '
                                 'to Jack\'s new core:\n  ```\n  %s\n  ```'
                                 % (latest[:12], patch.name,
                                    check.stderr.decode(errors='replace').strip()[:1500]))
                    return False, False
            for p in CORE:
                shutil.copyfile(core / p, ROOT / p)
        version = re.search(r'#define SUSFS_VERSION "([^"]+)"', (ROOT / 'include/linux/susfs.h').read_text())
        notes.append('- SUSFS: Jack `%s` -> `%s` ([changes](%s/compare/%s...%s)). Core %s. Version now `%s`.'
                     % (pin['commit'][:12], latest[:12], web(pin['repo']), pin['commit'], latest,
                        'updated' if core_changed else 'unchanged', version.group(1) if version else '?'))
        if hooks:
            review.append('Jack changed the kernel hook part of `%s` for: %s. These hooks were NOT '
                          'changed automatically; port them by hand before merging.'
                          % (pin['patch'], ', '.join('`%s`' % p for p in hooks)))
            diff = temporary / 'hooks.diff'
            for p in hooks:
                (temporary / 'old.patch').write_bytes(old_parts.get(p, b''))
                (temporary / 'new.patch').write_bytes(new_parts.get(p, b''))
                result = run('diff', '-u', '--label', 'old/' + p, '--label', 'new/' + p,
                             str(temporary / 'old.patch'), str(temporary / 'new.patch'), check=False)
                with open(diff, 'ab') as stream:
                    stream.write(result.stdout)
            review.append('```diff\n' + diff.read_text(errors='replace')[:20000] + '\n```')
    pin['commit'] = latest
    return True, True


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--summary', type=Path)
    args = parser.parse_args()
    path = ROOT / 'sources.json'
    sources = json.loads(path.read_text())
    notes, review = [], []
    xxksu_changed, xxksu_ok = update_xxksu(sources['xxksu'], notes)
    susfs_changed, susfs_ok = update_susfs(sources['susfs'], notes, review)
    changed = xxksu_changed or susfs_changed
    if changed:
        path.write_text(json.dumps(sources, indent=2) + '\n')
    lines = ['## xxKSU / SUSFS update', ''] + notes
    if review:
        lines += ['', '## Needs review', ''] + review
    if changed:
        lines += ['', 'A test kernel is built from this branch automatically. Flash it from the '
                  '"A325X Kernel" run for this branch, and merge this pull request if it works.']
    text = '\n'.join(lines) + '\n'
    print(text)
    if args.summary:
        args.summary.write_text(text)
    output = os.environ.get('GITHUB_OUTPUT')
    if output:
        with open(output, 'a') as stream:
            stream.write('changed=%s\nneeds_review=%s\n' % (str(changed).lower(), str(bool(review)).lower()))
    return 0 if xxksu_ok and susfs_ok else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print('Update check failed: ' + str(exc), file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError):
            print(exc.stderr.decode(errors='replace'), file=sys.stderr)
        sys.exit(1)
