#!/usr/bin/env python3
"""Record a pinned Jack 2.4.0 patch without replacing reviewed xxKSU adaptations.

The 26f2313 failure was not a compiler error. The 4.14 hook hunks were unchanged
from the baseline already adapted in this tree, and the only core delta was the
SUS_PATH i_state fix this tree already has. Reapplying those hunks, or replacing
fs/susfs.c, would drop local adaptations and mix priority-filter signatures.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
REPORT = Path('.susfs-port')
REPORT.mkdir(exist_ok=True)

def require(ok, message):
    if not ok:
        raise SystemExit(message)

def git(*args, data=None):
    return subprocess.run(['git', *args], input=data, text=True, capture_output=True)

def write(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text('\n'.join(line.rstrip() for line in text.splitlines()) + '\n')

def split_sections(patch):
    sections = {}
    for section in re.split(r'(?m)^(?=diff --git )', patch):
        if not section.startswith('diff --git '):
            continue
        match = re.match(r'diff --git a/(\S+) b/(\S+)', section)
        require(match is not None and match[1] == match[2], 'Renamed patch path requires review')
        path = match[2]
        parts = PurePosixPath(path).parts
        require(parts and not path.startswith('/') and '..' not in parts, 'Unsafe patch path')
        require(parts[0] in {'arch', 'block', 'drivers', 'fs', 'include', 'init', 'ipc', 'kernel', 'lib', 'mm', 'net', 'security'}, 'Unexpected patch scope: ' + path)
        require(path not in sections and not Path(path).is_symlink(), 'Duplicate or symlink patch target')
        sections[path] = section
    require(sections, 'No patch sections found')
    return sections

def norm_section(section):
    return '\n'.join(line for line in section.splitlines() if not line.startswith('index '))

def added_payload(section):
    return [line[1:] for line in section.splitlines() if line.startswith('+') and not line.startswith('+++')]

def reviewed_core_delta(old_section, new_section):
    old_payload, new_payload = added_payload(old_section), added_payload(new_section)
    if old_payload == new_payload:
        return 'unchanged'
    if len(old_payload) != len(new_payload):
        return 'unexpected'
    changes = 0
    for old, new in zip(old_payload, new_payload):
        if old == new:
            continue
        if 'test_bit(AS_FLAGS_SUS_PATH' not in old or old.replace('i_mapping->flags', 'i_state') != new:
            return 'unexpected'
        changes += 1
    return 'istate' if changes == 2 else 'unexpected'

pin = os.environ['JACK_COMMIT']
require(re.fullmatch('[0-9a-f]{40}', pin), 'Expected full Jack commit SHA')
require(git('-C', 'NonGKI_Kernel_Build_2nd', 'rev-parse', 'HEAD').stdout.strip() == pin, 'Jack checkout differs from pin')
patch_path = 'Patches/Patch/susfs_patch_to_4.14.patch'
patch_bytes = (Path('NonGKI_Kernel_Build_2nd') / patch_path).read_bytes()
patch = patch_bytes.decode()
sections = split_sections(patch)
core = ('fs/susfs.c', 'include/linux/susfs.h', 'include/linux/susfs_def.h')
require(all(path in sections for path in core), 'Jack core files missing')
header = '\n'.join(line[1:] for line in sections['include/linux/susfs.h'].splitlines() if line.startswith('+') and not line.startswith('+++'))
implementation = '\n'.join(added_payload(sections['fs/susfs.c']))
definitions = '\n'.join(added_payload(sections['include/linux/susfs_def.h']))
require(re.search(r'#define\s+SUSFS_VERSION\s+"v?2\.4\.0"', header), 'Selected patch is not SUSFS 2.4.0')
require('void susfs_set_priority_uid_filter(void __user **' in implementation, 'Jack priority command API changed')
require('susfs_is_priority_uid_filtered' in implementation and 'CMD_SUSFS_SET_PRIORITY_UID_FILTER' in definitions, 'Jack priority implementation missing')

lock_path = Path('patches/xxksu/source-lock.json')
lock = json.loads(lock_path.read_text())
require(lock.get('parent_patches_materialized') is True, 'Manual xxKSU materialization must run first')
baseline = lock['sources']['NonGKI_Kernel_Build_2nd']
require(re.fullmatch('[0-9a-f]{40}', baseline), 'Baseline Jack pin is not a full SHA')
baseline_show = git('-C', 'NonGKI_Kernel_Build_2nd', 'show', baseline + ':' + patch_path)
if baseline_show.returncode != 0:
    fetched = git('-C', 'NonGKI_Kernel_Build_2nd', 'fetch', 'origin', baseline)
    require(fetched.returncode == 0, 'Cannot fetch baseline Jack patch: ' + fetched.stderr)
    baseline_show = git('-C', 'NonGKI_Kernel_Build_2nd', 'show', baseline + ':' + patch_path)
require(baseline_show.returncode == 0, 'Cannot read baseline Jack patch: ' + baseline_show.stderr)
baseline_sections = split_sections(baseline_show.stdout)
require(set(baseline_sections) == set(sections), 'Jack patch file list changed; manual review required')
core_delta = reviewed_core_delta(baseline_sections['fs/susfs.c'], sections['fs/susfs.c'])
other_changes = sorted(path for path in sections if path != 'fs/susfs.c' and norm_section(sections[path]) != norm_section(baseline_sections[path]))
require(not other_changes, 'Jack hook patch changed and was not auto-applied: ' + ', '.join(other_changes))
require(core_delta in {'unchanged', 'istate'}, 'New Jack core delta is not the reviewed i_state fix; refusing to replace fs/susfs.c')
if core_delta == 'istate':
    current_core = Path('fs/susfs.c').read_text()
    require('test_bit(AS_FLAGS_SUS_PATH, &fi->inode.i_state)' in current_core, 'Tree is missing the reviewed fi->inode.i_state fix')
    require('test_bit(AS_FLAGS_SUS_PATH, &inode->i_state)' in current_core, 'Tree is missing the reviewed inode->i_state fix')

sentinels = (
    ('fs/susfs.c', 'is_i_uid_not_allowed'),
    ('fs/susfs_priority.c', 'int susfs_set_priority_uid_filter(void __user *arg)'),
    ('include/linux/susfs.h', 'int susfs_set_priority_uid_filter(void __user *arg);'),
    ('block/ioprio.c', 'susfs_is_priority_uid_filtered'),
    ('kernel/sys.c', 'susfs_is_priority_uid_filtered'),
    ('kernel/reboot.c', 'return susfs_set_priority_uid_filter(arg);'),
    ('fs/namei.c', 'susfs_is_inode_sus_path'),
    ('fs/readdir.c', 'susfs_is_inode_sus_path'),
    ('fs/stat.c', 'susfs_mask'),
    ('fs/super.c', 'DEFAULT_KSU_MNT_MINOR_DEV'),
    ('fs/Makefile', 'susfs_priority.o'),
)
missing = [path + ': ' + needle for path, needle in sentinels if needle not in Path(path).read_text()]
require(not missing, 'Refusing to treat existing adaptations as reviewed; missing: ' + ', '.join(missing))

audit, unresolved = [], []
for path, section in sections.items():
    if path in core or path == 'fs/Makefile':
        if path == 'fs/susfs.c' and core_delta == 'istate':
            status = 'reviewed_istate_delta_already_present'
        elif path == 'fs/Makefile':
            status = 'retained_existing_kbuild'
        else:
            status = 'unchanged_core_retained'
        audit.append({'path': path, 'status': status})
        continue
    if '\nnew file mode' in section.split('\n@@')[0]:
        unresolved.append(path + ': unexpected new file in an otherwise unchanged hook patch')
        audit.append({'path': path, 'status': 'unresolved_new_file'})
        continue
    hunks = list(re.finditer(r'(?m)^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[^\n]*\n', section))
    if not hunks:
        unresolved.append(path + ': unsupported metadata-only section')
    for index, match in enumerate(hunks, 1):
        old_count = int(match[2] or 1)
        new_count = int(match[4] or 1)
        body = []
        for line in section[match.end():].splitlines(keepends=True):
            if old_count == 0 and new_count == 0:
                break
            require(line and line[0] in ' +-\\', 'Malformed patch hunk')
            body.append(line)
            if line[0] in ' -':
                old_count -= 1
            if line[0] in ' +':
                new_count -= 1
            require(old_count >= 0 and new_count >= 0, 'Invalid hunk counts')
        require(old_count == 0 and new_count == 0, 'Incomplete hunk')
        single = 'diff --git a/{0} b/{0}\n--- a/{0}\n+++ b/{0}\n'.format(path) + match[0] + ''.join(body)
        if git('apply', '--reverse', '--check', '-', data=single).returncode == 0:
            status = 'already_present'
        elif git('apply', '--check', '-', data=single).returncode == 0:
            result = git('apply', '-', data=single)
            require(result.returncode == 0, result.stderr)
            status = 'applied'
        else:
            status = 'reviewed_existing_adaptation'
        audit.append({'path': path, 'hunk': index, 'status': status})

manifest = {
    'upstream': 'https://github.com/JackA1ltman/NonGKI_Kernel_Build_2nd.git',
    'commit': pin,
    'baseline': baseline,
    'patch': patch_path,
    'patch_sha256': hashlib.sha256(patch_bytes).hexdigest(),
    'core_decision': 'retain existing core; ' + core_delta + ' delta not reapplied',
    'priority_filter': 'existing susfs_priority.c retained; Jack void(void __user **) signature not mixed in',
    'audit': audit,
    'unresolved': unresolved,
    'validation': 'source generation only; compile and device tests not performed',
}
write(REPORT / 'jack-source.json', json.dumps(manifest, indent=2))
require(not unresolved, 'Refusing partial port; review .susfs-port/jack-source.json: ' + ', '.join(unresolved))
lock['sources']['NonGKI_Kernel_Build_2nd'] = pin
lock['jack_susfs'] = {
    'commit': pin,
    'baseline': baseline,
    'patch': patch_path,
    'sha256': manifest['patch_sha256'],
    'decision': manifest['core_decision'],
    'audit': '.susfs-port/jack-source.json',
}
lock['status'] = 'Jack 2.4.0 pin reviewed against existing xxKSU adaptations. Core, priority filter and hook files were not replaced. Compile and runtime pending.'
write(lock_path, json.dumps(lock, indent=2))
write(REPORT / 'COMMIT_SUBJECT', 'SUSFS: record reviewed Jack 2.4.0 pin without replacing existing adaptations\n')
write(REPORT / 'PORT_NOTES.md', '\n'.join([
    '# Jack SUSFS 2.4.0 reviewed against existing xxKSU adaptations',
    '',
    '- Jack commit: ' + pin,
    '- Baseline patch: ' + baseline,
    '- Core decision: existing fs/susfs.c retained. The only patch delta is the SUS_PATH i_state fix, and this tree already has it.',
    '- Priority filter: existing fs/susfs_priority.c and int(void __user *) declaration retained. Jack\'s void(void __user **) implementation was not mixed in.',
    '- Hook hunks unchanged from the baseline were not reapplied. Exact matches are already_present; context differences against existing adaptations are reviewed_existing_adaptation.',
    '- This is not proof of a successful compile, boot, root or runtime behavior.',
    '',
]))
result = git('diff', '--check')
require(result.returncode == 0, result.stdout + result.stderr)
print(json.dumps({key: manifest[key] for key in ('commit', 'baseline', 'core_decision', 'priority_filter', 'unresolved')}, indent=2))
print('audit_counts ' + json.dumps({status: sum(item['status'] == status for item in audit) for status in sorted({item['status'] for item in audit})}))
