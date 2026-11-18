#!/usr/bin/env python3
"""Import pinned Jack core with prior port adaptations; fail on unresolved hooks."""
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

def once(text, old, new):
    require(text.count(old) == 1, 'Missing or ambiguous adaptation anchor: ' + old[:100])
    return text.replace(old, new, 1)

def write(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text('\n'.join(line.rstrip() for line in text.splitlines()) + '\n')

pin = os.environ['JACK_COMMIT']
require(re.fullmatch('[0-9a-f]{40}', pin), 'Expected full Jack commit SHA')
require(git('-C', 'NonGKI_Kernel_Build_2nd', 'rev-parse', 'HEAD').stdout.strip() == pin, 'Jack checkout differs from pin')
patch_path = 'Patches/Patch/susfs_patch_to_4.14.patch'
patch_bytes = (Path('NonGKI_Kernel_Build_2nd') / patch_path).read_bytes()
patch = patch_bytes.decode()
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

def new_file(section):
    require('\nnew file mode' in section.split('\n@@')[0], 'Expected complete new-file payload')
    return '\n'.join(line[1:] for line in section.splitlines() if line.startswith('+') and not line.startswith('+++')) + '\n'

core = ('fs/susfs.c', 'include/linux/susfs.h', 'include/linux/susfs_def.h')
require(all(p in sections for p in core), 'Jack core files missing')
c, h, d = (new_file(sections[p]) for p in core)
require(re.search(r'#define\s+SUSFS_VERSION\s+"v?2\.4\.0"', h), 'Selected patch is not SUSFS 2.4.0')
require('void susfs_set_priority_uid_filter(void __user **' in c, 'Jack priority command API changed')
require('susfs_is_priority_uid_filtered' in c and 'CMD_SUSFS_SET_PRIORITY_UID_FILTER' in d, 'Jack priority implementation missing')
pattern = re.compile(r'/\*\n \* Switches the selinux domain.*?static void susfs_restore_creds\(struct cred \*orig_cred\) \{.*?\n\}\n', re.S)
replacement = '''/* Retain the credential adaptation from the prior KSUN Jack port. */
static const struct cred *susfs_switch_to_ksu_domain(void) {
    struct cred *cred = READ_ONCE(ksu_cred);
    const struct cred *saved;
    if (!cred)
        return NULL;
    saved = override_creds(cred);
    if (!susfs_is_current_ksu_domain()) {
        revert_creds(saved);
        return NULL;
    }
    return saved;
}
static void susfs_restore_creds(const struct cred *saved) {
    if (saved)
        revert_creds(saved);
}
'''
c, count = pattern.subn(lambda m: replacement, c, count=1)
require(count == 1, 'Credential helper changed; manual review required')
c, count = re.subn(r'(?<!const )struct cred \*orig_cred = NULL;', 'const struct cred *orig_cred = NULL;', c)
require(count >= 1, 'Credential declaration changed')
log_pattern = re.compile(r'(#else\s*\n#define SUSFS_LOGI\(fmt, \.\.\.\)[ \t]*\n#define SUSFS_LOGE\(fmt, \.\.\.\)[ \t]*\n)(#endif)')
if '#define SUSFS_LOGI_RL(fmt, ...)\n' not in c:
    c, count = log_pattern.subn(lambda m: m[1] + '#define SUSFS_LOGI_RL(fmt, ...)\n#define SUSFS_LOGE_RL(fmt, ...)\n' + m[2], c, count=1)
    require(count == 1, 'Disabled-log adaptation changed')
if 'susfs_get_data_path' not in c:
    c += '\nint susfs_get_data_path(struct path *path) {\n\treturn kern_path("/data", LOOKUP_FOLLOW, path);\n}\n'
h = once(h, '#include <linux/statfs.h>\n', '#include <linux/statfs.h>\n#ifndef getname_safe\n#define getname_safe(name) (name == NULL ? ERR_PTR(-EINVAL) : getname(name))\n#endif\n#ifndef putname_safe\n#define putname_safe(name) (IS_ERR(name) ? NULL : putname(name))\n#endif\n')
for path, text in zip(core, (c, h, d)):
    write(path, text)
mk = Path('fs/Makefile').read_text()
obj = re.compile(r'^obj-\$\(CONFIG_KSU_SUSFS\)\s*\+=.*$', re.M)
require(len(obj.findall(mk)) == 1, 'Ambiguous SUSFS Kbuild entry')
mk = obj.sub('obj-$(CONFIG_KSU_SUSFS) += susfs.o susfs_ksu_glue.o', mk)
if 'SUSFS_KERNEL_READ_NEW' not in mk:
    anchor = 'obj-$(CONFIG_KSU_SUSFS) += susfs.o susfs_ksu_glue.o\n'
    mk = once(mk, anchor, anchor + 'ifeq ($(shell grep -q "ssize_t kernel_read" $(srctree)/fs/read_write.c $(srctree)/fs/exec.c 2>/dev/null; echo $$?),0)\nCFLAGS_susfs.o += -DSUSFS_KERNEL_READ_NEW\nendif\n')
write('fs/Makefile', mk)
Path('fs/susfs_priority.c').unlink(missing_ok=True)
glue = Path('fs/susfs_ksu_glue.c').read_text()
if 'case CMD_SUSFS_SET_PRIORITY_UID_FILTER:' not in glue:
    glue = once(glue, '    switch (cmd) {\n', '    switch (cmd) {\n#ifdef CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER\n    case CMD_SUSFS_SET_PRIORITY_UID_FILTER: susfs_set_priority_uid_filter(arg); break;\n#endif\n')
if 'case CMD_SUSFS_SET_SUS_PATH_UID_FILTER:' not in glue:
    anchor = '    case CMD_SUSFS_ADD_SUS_PATH_LOOP: susfs_add_sus_path_loop(arg); break;\n'
    glue = once(glue, anchor, anchor + '    case CMD_SUSFS_SET_SUS_PATH_UID_FILTER: susfs_set_sus_path_uid_filter(arg); break;\n')
write('fs/susfs_ksu_glue.c', glue)
reboot = Path('kernel/reboot.c').read_text()
old = '\t\tif ((u32)magic2 == SUSFS_MAGIC &&\n\t\t    cmd == CMD_SUSFS_SET_PRIORITY_UID_FILTER) {\n\t\t\tif (!uid_eq(current_uid(), GLOBAL_ROOT_UID))\n\t\t\t\treturn -EPERM;\n\t\t\treturn susfs_set_priority_uid_filter(arg);\n\t\t}\n'
fixed = '#ifdef CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER\n' + old.replace('return susfs_set_priority_uid_filter(arg);', 'susfs_set_priority_uid_filter(&arg);\n\t\t\treturn 0;') + '#endif\n'
if fixed not in reboot:
    reboot = once(reboot, old, fixed)
write('kernel/reboot.c', reboot)

audit, unresolved = [], []
for path, section in sections.items():
    if path in core or path == 'fs/Makefile':
        audit.append({'path': path, 'status': 'explicit_core_or_kbuild_adaptation'})
        continue
    if '\nnew file mode' in section.split('\n@@')[0]:
        payload = new_file(section)
        destination = Path(path)
        if not destination.exists():
            write(path, payload)
            status = 'new_file_imported'
        elif destination.read_text().splitlines() == payload.splitlines():
            status = 'new_file_already_present'
        else:
            status = 'unresolved_new_file'
            unresolved.append(path)
        audit.append({'path': path, 'status': status})
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
            status = 'unresolved'
            unresolved.append(path + ': hunk ' + str(index))
            (REPORT / (path.replace('/', '__') + '.hunk-' + str(index) + '.patch')).write_text(single)
        audit.append({'path': path, 'hunk': index, 'status': status})
manifest = {'upstream': 'https://github.com/JackA1ltman/NonGKI_Kernel_Build_2nd.git', 'commit': pin, 'patch': patch_path, 'patch_sha256': hashlib.sha256(patch_bytes).hexdigest(), 'audit': audit, 'unresolved': unresolved, 'validation': 'source generation only; compile and device tests not performed'}
write(REPORT / 'jack-source.json', json.dumps(manifest, indent=2))
require(not unresolved, 'Refusing partial port; review .susfs-port/jack-source.json: ' + ', '.join(unresolved))
lock_path = Path('patches/xxksu/source-lock.json')
lock = json.loads(lock_path.read_text())
require(lock.get('parent_patches_materialized') is True, 'Manual xxKSU materialization must run first')
lock['sources']['NonGKI_Kernel_Build_2nd'] = pin
lock['jack_susfs'] = {'commit': pin, 'patch': patch_path, 'sha256': manifest['patch_sha256'], 'audit': '.susfs-port/jack-source.json'}
lock['status'] = 'Jack 2.4.0 core imported with explicit adaptations and no unresolved patch hunks; compile and runtime pending.'
write(lock_path, json.dumps(lock, indent=2))
write(REPORT / 'PORT_NOTES.md', '# Jack SUSFS 2.4.0 with xxKSU manual hooks\n\n- Jack commit: ' + pin + '\n- Core imported from the pinned 4.14 patch; previous credential, disabled-log, kernel_read and command-dispatch adaptations retained.\n- Standalone priority implementation removed. Remaining patch hunks applied or reverse-checked as already present; explicit core/Kbuild adaptations recorded separately.\n- Existing xxKSU manual hooks and branch-aware builder retained.\n- Source hunk checks are not proof of semantic equivalence, a successful compile, boot or runtime behavior.\n')
result = git('diff', '--check')
require(result.returncode == 0, result.stdout + result.stderr)
print(json.dumps(manifest, indent=2))
