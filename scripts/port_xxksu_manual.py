#!/usr/bin/env python3
"""Generate an isolated, uncompiled manual-hook review port for the locked xxKSU pin."""
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)

def require(ok, message):
    if not ok:
        raise SystemExit(message)

def replace_once(text, old, new):
    require(text.count(old) == 1, 'Anchor missing or ambiguous: ' + old[:100])
    return text.replace(old, new, 1)

def write(path, text):
    Path(path).write_text(text)

def add_hook(text, function, arguments, call):
    pattern = re.compile(r'(?m)^int\s+' + re.escape(function) + r'\s*\(([^{};]*)\)\s*\{')
    matches = list(pattern.finditer(text))
    require(len(matches) == 1, 'Expected one definition: ' + function)
    match = matches[0]
    require(all(re.search(r'\b' + arg + r'\b', match[1]) for arg in arguments), 'Unexpected signature: ' + function)
    return text[:match.end()] + '\n#ifdef CONFIG_XXKSU_MANUAL_HOOKS\n\t' + call + '\n#endif\n' + text[match.end():]

target = os.environ['TARGET_BRANCH']
require(re.fullmatch(r'xxksu-manual-susfs-port(?:-[A-Za-z0-9._-]+)?', target), 'Invalid isolated target')
base = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
require(not subprocess.check_output(['git', 'status', '--porcelain']).strip(), 'Clean source checkout required')
subprocess.run(['python3', 'scripts/prepare_xxksu.py', '--apply'], check=True)
# Parent patches become committed source on the generated branch. KernelSU patches
# remain locked runtime patches; do not publish modified submodule commits.
lock_path = Path('patches/xxksu/source-lock.json')
lock = json.loads(lock_path.read_text())
require(lock['sources']['KernelSU'] == '1b8ce9e15a9402aa2192aed5d381366cf2150f0f', 'Unexpected xxKSU pin')
prep_path = Path('scripts/prepare_xxksu.py')
prep = replace_once(prep_path.read_text(), '        patches.append((entry[\'target\'], path))',
                    '        if entry[\'target\'] == \'KernelSU\':\n            patches.append((entry[\'target\'], path))')
write(prep_path, prep)
lock['parent_patches_materialized'] = True
lock['materialized_from'] = base
lock['status'] = 'Manual-hook review port: parent integration materialized; KernelSU patches remain runtime-applied. Compile and device validation pending.'
write(lock_path, json.dumps(lock, indent=2) + '\n')

# Keep legacy BakaSU-shaped execution/read/input paths disabled, even though
# runtime branch-link hooking is now disabled. Native source hooks replace them.
for filename in ('fs/exec.c', 'fs/read_write.c', 'drivers/input/input.c', 'fs/susfs_ksu_glue.c'):
    text = Path(filename).read_text()
    require('!defined(CONFIG_KSU_HACK_ARM64_BRANCH_LINK)' in text, 'Missing native-transition guard: ' + filename)
    text = text.replace('!defined(CONFIG_KSU_HACK_ARM64_BRANCH_LINK)', '!defined(CONFIG_XXKSU_MANUAL_HOOKS)')
    write(filename, text)

header = '''/* SPDX-License-Identifier: GPL-2.0 */
#ifndef _LINUX_XXKSU_MANUAL_HOOKS_H
#define _LINUX_XXKSU_MANUAL_HOOKS_H
#include <linux/compiler.h>
#include <linux/types.h>
struct cred;
struct inode;
struct dentry;
struct file;
struct linux_binprm;
#ifdef CONFIG_XXKSU_MANUAL_HOOKS
int ksu_handle_sys_execve(const char __user **filename, void *argv, void *envp);
int ksu_handle_sys_execveat(int *fd, const char __user **filename, void *argv, void *envp, int *flags);
int ksu_task_fix_setuid(struct cred *new, const struct cred *old, int flags);
int ksu_inode_rename(struct inode *old_dir, struct dentry *old_dentry, struct inode *new_dir, struct dentry *new_dentry);
int ksu_bprm_check(struct linux_binprm *bprm);
int ksu_file_permission(struct file *file, int mask);
int ksu_hide_setprocattr(const char *name, void *value, size_t size);
int ksu_hide_inode_setxattr(struct dentry *dentry, const char *name, void *value, size_t *size, int *flags);
#endif
#endif
'''
write('include/linux/xxksu_manual_hooks.h', header)

security = Path('security/security.c').read_text()
security = '#include <linux/xxksu_manual_hooks.h>\n' + security
hooks = [
    ('security_task_fix_setuid', ('new', 'old', 'flags'), '(void)ksu_task_fix_setuid(new, old, flags);'),
    ('security_inode_rename', ('old_dir', 'old_dentry', 'new_dir', 'new_dentry'), '(void)ksu_inode_rename(old_dir, old_dentry, new_dir, new_dentry);'),
    ('security_bprm_check', ('bprm',), '(void)ksu_bprm_check(bprm);'),
    ('security_file_permission', ('file', 'mask'), '(void)ksu_file_permission(file, mask);'),
    ('security_setprocattr', ('name', 'value', 'size'), '(void)ksu_hide_setprocattr(name, value, size);'),
    ('security_inode_setxattr', ('dentry', 'name', 'value', 'size', 'flags'), '(void)ksu_hide_inode_setxattr(dentry, name, (void *)value, &size, &flags);'),
]
for function, arguments, call in hooks:
    security = add_hook(security, function, arguments, call)
write('security/security.c', security)

execution = Path('fs/exec.c').read_text()
execution = '#include <linux/xxksu_manual_hooks.h>\n' + execution
pattern = re.compile(r'(?m)^(?:COMPAT_)?SYSCALL_DEFINE[35]\((execve(?:at)?),([^{};]*)\)\s*\{')
counts = {'execve': 0, 'execveat': 0}
def exec_hook(match):
    name, signature = match[1], match[2]
    names = ('filename', 'argv', 'envp') + (('fd', 'flags') if name == 'execveat' else ())
    require(all(re.search(r'\b' + arg + r'\b', signature) for arg in names), 'Unexpected exec syscall signature')
    counts[name] += 1
    call = '(void)ksu_handle_sys_execve(&filename, &argv, &envp);'
    if name == 'execveat':
        call = '(void)ksu_handle_sys_execveat(&fd, &filename, &argv, &envp, &flags);'
    return match[0] + '\n#ifdef CONFIG_XXKSU_MANUAL_HOOKS\n\t' + call + '\n#endif\n'
execution = pattern.sub(exec_hook, execution)
require(counts['execve'] >= 1 and counts['execveat'] >= 1, 'Native exec syscall definitions not found: ' + json.dumps(counts))
write('fs/exec.c', execution)

# Existing source-level access/stat adapters and SUSFS reboot dispatch remain.
require('xxksu_parent_uid_allowed' in Path('fs/susfs_ksu_glue.c').read_text(), 'Access/stat bridge missing')
require('ksu_handle_sys_reboot' in Path('kernel/reboot.c').read_text() or 'susfs_ksu_sys_reboot' in Path('kernel/reboot.c').read_text(), 'Reboot dispatch missing')
kconfig = Path('Kconfig').read_text()
require('config XXKSU_MANUAL_HOOKS' not in kconfig, 'Manual mode already exists')
kconfig += '\nconfig XXKSU_MANUAL_HOOKS\n\tbool "xxKSU direct parent-kernel hooks"\n\tdepends on KSU=y\n\tdefault y\n'
write('Kconfig', kconfig)
config_path = Path('arch/arm64/configs/ksu-a325n-common.config')
config = config_path.read_text()
for option in ('CONFIG_KSU_LSM_SECURITY_HOOKS', 'CONFIG_KSU_HACK_ARM64_BRANCH_LINK'):
    config = replace_once(config, option + '=y', '# ' + option + ' is not set')
config += '\nCONFIG_XXKSU_MANUAL_HOOKS=y\n'
write(config_path, config)

for filename in ('build_xxksu.sh', 'package_xxksu.sh'):
    text = Path(filename).read_text()
    text = replace_once(text, 'CONFIG_KSU CONFIG_KSU_SUSFS CONFIG_KSU_LSM_SECURITY_HOOKS CONFIG_KSU_HACK_ARM64_BRANCH_LINK',
                        'CONFIG_KSU CONFIG_KSU_SUSFS CONFIG_XXKSU_MANUAL_HOOKS')
    anchor = 'for option in CONFIG_KSU CONFIG_KSU_SUSFS CONFIG_XXKSU_MANUAL_HOOKS; do'
    check = '''for disabled in CONFIG_KSU_LSM_SECURITY_HOOKS CONFIG_KSU_HACK_ARM64_BRANCH_LINK CONFIG_KSU_TAMPER_SYSCALL_TABLE; do
  if grep -q "^$disabled=" "$OUT_DIR/.config"; then
    echo "Automated hook mode unexpectedly enabled: $disabled" >&2; exit 1
  fi
done
'''
    if filename == 'build_xxksu.sh':
        check = check.replace('$OUT_DIR', '$OUT')
    text = replace_once(text, anchor, check + anchor)
    write(filename, text)
workflow_path = Path('.github/workflows/kernel.yml')
workflow = workflow_path.read_text().replace('xxksu-sufs-jack', target)
write(workflow_path, workflow)
subprocess.run(['git', '-C', 'KernelSU', 'reset', '--hard', lock['sources']['KernelSU']], check=True)
subprocess.run(['sh', '-n', 'build_xxksu.sh'], check=True)
subprocess.run(['sh', '-n', 'package_xxksu.sh'], check=True)
subprocess.run(['git', 'diff', '--check'], check=True)
Path('.susfs-port').mkdir(exist_ok=True)
write('.susfs-port/PORT_NOTES.md', '# xxKSU manual-hook review port\n\n'
      + '- Base: ' + base + '\n'
      + '- Native direct exec and security entry points; automated LSM and branch-link modes disabled.\n'
      + '- Existing access/stat bridge, SUSFS reboot dispatch and native input handler retained.\n'
      + '- Existing parent integration materialized; locked KernelSU patches applied during builds.\n'
      + '- Builder/package configuration checks and workflow routing updated for this isolated branch.\n'
      + '- Existing SUSFS core retained: this is NOT a complete Jack core upgrade.\n'
      + '- Source generation and shell syntax checks only. Compile/link, boot, root and performance remain untested.\n')
print(json.dumps({'base': base, 'target': target, 'exec_hooks': counts, 'security_hooks': [h[0] for h in hooks], 'validation': 'source-generation only'}, indent=2))
