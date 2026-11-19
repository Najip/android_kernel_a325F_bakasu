#!/usr/bin/env python3
"""Apply the device patches in patches/kernel/ to the kernel tree.

  0001 network fix ............ always (WiFi "connected, no internet" / VPN
                                 reconnect hang; UDP-only GSO)
  other patches/kernel files .. always (branch-specific fixes)
  0002 performance tuning ..... only when PERF_TUNING=true
                                 (GPU 1100 MHz @ 1.035 V, CPU/CCI undervolt,
                                 GPU meter, fast charge with screen on,
                                 zram zstd, USB autosuspend off)

The tuning config (arch/arm64/configs/a325n-tuning.config) is merged by the
build script when PERF_TUNING=true.
Usage: PERF_TUNING=false python3 scripts/apply_kernel_patches.py OUT_DIR
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
NETWORK = '0001-network-udp-gso-qdisc.patch'
TUNING = '0002-optional-tuning.patch'


def git(*args, data=None):
    return subprocess.run(['git', '-C', str(ROOT), *args], input=data, check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def main():
    out = Path(sys.argv[1]).resolve()
    flag = os.environ.get('PERF_TUNING', 'false').lower()
    if flag not in ('true', 'false'):
        raise ValueError('PERF_TUNING must be true or false')
    tuning = flag == 'true'
    extras = [path.name for path in sorted((ROOT / 'patches/kernel').glob('*.patch'))
              if path.name not in (NETWORK, TUNING)]
    plan = [(NETWORK, 'network')] + [(name, 'required') for name in extras]
    if tuning:
        plan.append((TUNING, 'tuning'))
    selected, records = [], []
    for name, kind in plan:
        data = (ROOT / 'patches/kernel' / name).read_bytes()
        selected.append((name, data))
        records.append({'name': name, 'kind': kind, 'sha256': hashlib.sha256(data).hexdigest()})
    applied = []
    try:
        for name, data in selected:
            git('apply', '--check', '-', data=data)
            git('apply', '-', data=data)
            applied.append(data)
        git('diff', '--check')
    except subprocess.CalledProcessError:
        for data in reversed(applied):
            git('apply', '--reverse', '-', data=data)
        raise ValueError('a kernel patch does not apply. If you are rebuilding locally, '
                         'reset the tree first with: git checkout -- .')
    out.mkdir(parents=True, exist_ok=True)
    result = {'perf_tuning': tuning, 'patches': records}
    text = json.dumps(result, indent=2) + '\n'
    (out / 'kernel-patches.json').write_text(text)
    (out / 'applied-patches.txt').write_text(''.join(name + '\n' for name, _ in selected))
    print(text, end='')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print('Kernel patches failed: ' + str(exc), file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError):
            print(exc.stderr.decode(errors='replace'), file=sys.stderr)
        sys.exit(1)
