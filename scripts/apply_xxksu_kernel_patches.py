#!/usr/bin/env python3
"""Import only the locked nomount network/tuning/GPU-restoration patches."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = '53fe38b470a927e590b89eace39b7a71e4b90ea1'
PATCHES = [
    ('0003-net-udp-gso-qdisc-juan.patch', '7caa413200b57fdd865ef663e1095caa1241b494', 'network'),
    ('0006-tuning-wifi-fix-perf-1100mhz-1035mv_uv75_zstd_usbnoauto-juan.patch', '688e1e783c971c2aa9434ae551a52cc7aac9af9e', 'tuning'),
    ('0006-restore-original-gpu-voltages.patch', '486a70ed37093833a0d533cc46bf69a672964015', 'restore'),
]
GPU = 'drivers/misc/mediatek/base/power/mt6768/mtk_gpufreq_core.h'

def git(tree, *args, data=None):
    return subprocess.run(['git', '-C', str(tree), *args], input=data,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout

def main():
    out = Path(sys.argv[1]).resolve()
    flag = os.environ.get('PERF_TUNING', 'false').lower()
    if flag not in ('true', 'false'):
        raise ValueError('PERF_TUNING must be true or false')
    tuning = flag == 'true'
    try:
        git(ROOT, 'cat-file', '-e', SOURCE + '^{commit}')
    except subprocess.CalledProcessError:
        git(ROOT, 'fetch', '--no-tags', '--depth=1', 'origin', SOURCE)
    baseline = git(ROOT, 'show', 'HEAD:' + GPU).decode()
    voltages = {}
    for line in baseline.splitlines():
        match = re.match(r'#define SEG_GPU_DVFS_VOLT(\d+)\s+', line)
        if match:
            voltages.setdefault(match.group(1), line)
    if len(voltages) != 32:
        raise ValueError('Expected 32 original GPU voltage definitions')
    selected, records = [], []
    for name, expected_blob, kind in PATCHES:
        raw = git(ROOT, 'show', SOURCE + ':patches/kernel/' + name)
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if blob != expected_blob:
            raise ValueError('Imported patch blob mismatch: ' + name)
        if kind == 'tuning' and not tuning:
            continue
        adapted = raw
        if kind == 'tuning':
            count = [0]
            def preimage(match):
                count[0] += 1
                return '-' + voltages[match.group(1)]
            text = re.sub(r'^-#define SEG_GPU_DVFS_VOLT(\d+)[^\n]*', preimage,
                          raw.decode(), flags=re.MULTILINE)
            if count[0] != 32:
                raise ValueError('Expected precisely 32 tuning voltage preimage lines')
            adapted = text.encode()
        selected.append((name, adapted))
        records.append({'name': name, 'kind': kind, 'source_git_blob': blob,
                        'source_sha256': hashlib.sha256(raw).hexdigest(),
                        'applied_sha256': hashlib.sha256(adapted).hexdigest(),
                        'gpu_preimage_adapted': adapted != raw})
    before = git(ROOT, 'diff', '--binary', '--ignore-submodules=all', 'HEAD')
    with tempfile.TemporaryDirectory(prefix='xxksu-kernel-patches-') as temporary:
        tree = Path(temporary) / 'parent'
        git(ROOT, 'clone', '--shared', '--no-checkout', '--', str(ROOT), str(tree))
        git(tree, 'checkout', '--detach', git(ROOT, 'rev-parse', 'HEAD').decode().strip())
        if before:
            git(tree, 'apply', '-', data=before)
        for name, patch in selected:
            git(tree, 'apply', '--check', '-', data=patch)
            git(tree, 'apply', '-', data=patch)
        git(tree, 'diff', '--check')
        for name, patch in reversed(selected):
            git(tree, 'apply', '--reverse', '--check', '-', data=patch)
            git(tree, 'apply', '--reverse', '-', data=patch)
        if git(tree, 'diff', '--binary', '--ignore-submodules=all', 'HEAD') != before:
            raise ValueError('Disposable tree did not restore to prepared baseline')
    applied = []
    try:
        for name, patch in selected:
            git(ROOT, 'apply', '--check', '-', data=patch)
            git(ROOT, 'apply', '-', data=patch)
            applied.append((name, patch))
        git(ROOT, 'diff', '--check')
    except Exception:
        for name, patch in reversed(applied):
            git(ROOT, 'apply', '--reverse', '-', data=patch)
        raise
    out.mkdir(parents=True, exist_ok=True)
    patch_dir = out / 'selected-kernel-patches'
    patch_dir.mkdir(exist_ok=True)
    for name, patch in selected:
        (patch_dir / name).write_bytes(patch)
    result = {'source_branch': 'nomount-lkm-sync-up-patch', 'source_commit': SOURCE,
              'network_fixes': True, 'perf_tuning': tuning,
              'original_gpu_voltages_restored_last': True,
              'sequential_preflight': 'PASS', 'reverse_restoration': 'PASS', 'patches': records}
    text = json.dumps(result, indent=2) + '\n'
    (out / 'xxksu-kernel-patches.json').write_text(text)
    (out / 'applied-patches.txt').write_text(''.join(name + '\n' for name, patch in selected))
    print(text)

if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print('xxKSU kernel patch integration failed: ' + str(exc), file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError):
            print(exc.stderr.decode(errors='replace'), file=sys.stderr)
        sys.exit(1)
