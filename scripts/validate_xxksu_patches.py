#!/usr/bin/env python3
"""Check patch application only, never compile or enable the integration."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SERIES = [
    ('.', '0001-parent-bridge-api.patch'),
    ('KernelSU', '0002-xxksu-native-wrappers.patch'),
    ('.', '0003-parent-access-stat-adapter.patch'),
    ('.', '0004-parent-native-hook-transition.patch'),
    ('.', '0005-parent-susfs-lifecycle.patch'),
    ('KernelSU', '0006-xxksu-susfs-lifecycle-calls.patch'),
]

def main():
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    run_id = os.environ.get('GITHUB_RUN_ID', 'local')
    attempt = os.environ.get('GITHUB_RUN_ATTEMPT', '1')
    destination = 'audit-reports/xxksu-validation/' + run_id + '-' + attempt
    report = {
        'status': 'FAIL',
        'scope': 'Complete-series forward/reverse application only; no compile, boot, root, SUSFS-runtime, or LKM validation.',
        'source_commit': os.environ.get('GITHUB_SHA', ''),
        'run_id': run_id, 'attempt': attempt,
        'run_url': os.environ.get('GITHUB_SERVER_URL', 'https://github.com') + '/' + os.environ.get('GITHUB_REPOSITORY', '') + '/actions/runs/' + run_id,
        'report_directory': destination, 'sources': {}, 'patches': [],
        'steps': [], 'log_parts': [],
    }
    log = []

    def git(cwd, *args):
        command = ['git', '-C', str(cwd), *args]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors='replace')
        report['steps'].append({'command': command, 'exit_code': result.returncode})
        log.append('$ ' + ' '.join(command) + '\n' + result.stdout + result.stderr + '\n')
        if result.returncode:
            raise RuntimeError('Command failed: ' + ' '.join(command))
        return result.stdout.strip()

    try:
        source_commit = git(ROOT, 'rev-parse', 'HEAD')
        if report['source_commit'] and source_commit != report['source_commit']:
            raise RuntimeError('Checkout does not match the triggering source commit')
        report['source_commit'] = source_commit
        lock = json.loads((ROOT / 'patches/xxksu/source-lock.json').read_text())
        for name, expected in lock['sources'].items():
            actual = git(ROOT / name, 'rev-parse', 'HEAD')
            recorded = git(ROOT, 'ls-tree', 'HEAD', '--', name).split()
            if len(recorded) < 3 or recorded[0] != '160000' or recorded[2] != expected or actual != expected:
                raise RuntimeError(name + ': source HEAD/gitlink differs from the source lock')
            report['sources'][name] = actual
        patch_dir = ROOT / 'patches/xxksu'
        if {p.name for p in patch_dir.glob('*.patch')} != {name for _, name in SERIES}:
            raise RuntimeError('Unexpected/missing patch: update the explicit validation series')
        for target, name in SERIES:
            path = patch_dir / name
            report['patches'].append({'name': name, 'target': target, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        with tempfile.TemporaryDirectory(prefix='xxksu-validate-') as temporary:
            temporary = Path(temporary)
            trees = {'.': temporary / 'parent', 'KernelSU': temporary / 'KernelSU'}
            for target, tree in trees.items():
                source = ROOT if target == '.' else ROOT / target
                revision = source_commit if target == '.' else report['sources'][target]
                git(ROOT, 'clone', '--shared', '--no-checkout', '--', str(source), str(tree))
                git(tree, 'checkout', '--detach', revision)
                if git(tree, 'status', '--porcelain', '--untracked-files=all', '--ignore-submodules=all'):
                    raise RuntimeError(target + ': disposable checkout is not clean')
            for target, name in SERIES:
                path = str(patch_dir / name)
                git(trees[target], 'apply', '--check', path)
                git(trees[target], 'apply', path)
            report['forward_application'] = 'PASS'
            for target, tree in trees.items():
                git(tree, 'diff', '--check')
                git(tree, 'diff', '--stat')
            for target, name in reversed(SERIES):
                path = str(patch_dir / name)
                git(trees[target], 'apply', '--reverse', '--check', path)
                git(trees[target], 'apply', '--reverse', path)
            report['reverse_application'] = 'PASS'
            for target, tree in trees.items():
                if git(tree, 'status', '--porcelain', '--untracked-files=all', '--ignore-submodules=all'):
                    raise RuntimeError(target + ': tree differs after reversing all patches')
            report['clean_restoration'] = 'PASS'
        report['status'] = 'PASS'
    except Exception as error:
        report['error'] = str(error)
        log.append('VALIDATION FAILED: ' + str(error) + '\n')
    finally:
        text = ''.join(log)
        for index, offset in enumerate(range(0, max(len(text), 1), 10000), 1):
            name = 'commands.part-%04d.txt' % index
            (out / name).write_text(text[offset:offset + 10000])
            report['log_parts'].append(destination + '/' + name)
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        summary = os.environ.get('GITHUB_STEP_SUMMARY')
        if summary:
            with open(summary, 'a') as stream:
                stream.write('### xxKSU complete-series application check: ' + report['status'] + '\n\n' + report['scope'] + '\n')
        print(json.dumps({'status': report['status'], 'error': report.get('error'), 'report_directory': destination}))
    return 0 if report['status'] == 'PASS' else 1

if __name__ == '__main__':
    sys.exit(main())
