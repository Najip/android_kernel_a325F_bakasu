#!/usr/bin/env python3
"""Apply the device patches in patches/kernel/ to the kernel tree.

  0001 network fix ............ always
  0002 optional tuning ........ only when PERF_TUNING=true
  0003 original GPU voltages .. always, applied last

The tuning patch was written against modified GPU voltages, so its removed
voltage lines are rewritten to match this tree before it is applied.
Usage: PERF_TUNING=false python3 scripts/apply_kernel_patches.py OUT_DIR
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PATCHES = [
    ('0001-network-udp-gso-qdisc.patch', 'network'),
    ('0002-optional-tuning.patch', 'tuning'),
    ('0003-restore-original-gpu-voltages.patch', 'restore'),
]
GPU = 'drivers/misc/mediatek/base/power/mt6768/mtk_gpufreq_core.h'


def git(*args, data=None):
    return subprocess.run(['git', '-C', str(ROOT), *args], input=data, check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def adapt_tuning(raw):
    voltages = {}
    for line in git('show', 'HEAD:' + GPU).decode().splitlines():
        match = re.match(r'#define SEG_GPU_DVFS_VOLT(\d+)\s+', line)
        if match:
            voltages.setdefault(match.group(1), line)
    if len(voltages) != 32:
        raise ValueError('expected 32 GPU voltage definitions in ' + GPU)
    count = [0]

    def preimage(match):
        count[0] += 1
        return '-' + voltages[match.group(1)]

    text = re.sub(r'^-#define SEG_GPU_DVFS_VOLT(\d+)[^\n]*', preimage, raw.decode(), flags=re.MULTILINE)
    if count[0] != 32:
        raise ValueError('expected 32 GPU voltage lines in the tuning patch')
    return text.encode()


def main():
    out = Path(sys.argv[1]).resolve()
    flag = os.environ.get('PERF_TUNING', 'false').lower()
    if flag not in ('true', 'false'):
        raise ValueError('PERF_TUNING must be true or false')
    tuning = flag == 'true'
    selected, records = [], []
    for name, kind in PATCHES:
        if kind == 'tuning' and not tuning:
            continue
        data = (ROOT / 'patches/kernel' / name).read_bytes()
        if kind == 'tuning':
            data = adapt_tuning(data)
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
