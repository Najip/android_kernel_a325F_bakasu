// SPDX-License-Identifier: GPL-2.0
#define SUSFS_KSUN_GLUE_BUILD 1

#include <linux/compiler.h>
#include <linux/cred.h>
#include <linux/dcache.h>
#include <linux/err.h>
#include <linux/errno.h>
#include <linux/file.h>
#include <linux/fs.h>
#include <linux/init.h>
#include <linux/jump_label.h>
#include <linux/sched.h>
#include <linux/string.h>
#include <linux/types.h>
#include <linux/uaccess.h>
#include <linux/susfs.h>
#include <linux/susfs_def.h>
#include <linux/susfs_ksu.h>

#ifdef CONFIG_KSU_SUSFS
struct user_arg_ptr;
#include <linux/xxksu_parent_bridge.h>
#if !defined(CONFIG_XXKSU_MANUAL_HOOKS)
extern int ksu_handle_execveat_ksud(int *fd, struct filename **filename_ptr, void *argv, void *envp, int *flags);
extern int ksu_handle_execveat_sucompat(int *fd, struct filename **filename_ptr, void *argv, void *envp, int *flags);
#endif
extern const size_t ksu_rc_len __weak;
extern bool ksu_init_rc_hook __weak;
extern bool is_ksu_domain(void) __weak;

bool __weak susfs_is_current_ksu_domain(void)
{
    return is_ksu_domain ? is_ksu_domain() : false;
}

static int susfs_ksu_handle_cmd(unsigned int cmd, void __user **arg)
{
    switch (cmd) {
#ifdef CONFIG_KSU_SUSFS_SUS_PATH
    case CMD_SUSFS_ADD_SUS_PATH: susfs_add_sus_path(arg); break;
    case CMD_SUSFS_ADD_SUS_PATH_LOOP: susfs_add_sus_path_loop(arg); break;
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
    case CMD_SUSFS_HIDE_SUS_MNTS_FOR_NON_SU_PROCS: susfs_set_hide_sus_mnts_for_non_su_procs(arg); break;
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
    case CMD_SUSFS_ADD_SUS_KSTAT:
    case CMD_SUSFS_ADD_SUS_KSTAT_STATICALLY: susfs_add_sus_kstat(arg); break;
    case CMD_SUSFS_UPDATE_SUS_KSTAT: susfs_update_sus_kstat(arg); break;
#endif
#ifdef CONFIG_KSU_SUSFS_SPOOF_UNAME
    case CMD_SUSFS_SET_UNAME: susfs_set_uname(arg); break;
#endif
#ifdef CONFIG_KSU_SUSFS_ENABLE_LOG
    case CMD_SUSFS_ENABLE_LOG: susfs_enable_log(arg); break;
#endif
#ifdef CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG
    case CMD_SUSFS_SET_CMDLINE_OR_BOOTCONFIG: susfs_set_cmdline_or_bootconfig(arg); break;
#endif
#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT
    case CMD_SUSFS_ADD_OPEN_REDIRECT: susfs_add_open_redirect(arg); break;
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_MAP
    case CMD_SUSFS_ADD_SUS_MAP: susfs_add_sus_map(arg); break;
#endif
    case CMD_SUSFS_ENABLE_AVC_LOG_SPOOFING: susfs_set_avc_log_spoofing(arg); break;
    case CMD_SUSFS_SHOW_ENABLED_FEATURES: susfs_get_enabled_features(arg); break;
    case CMD_SUSFS_SHOW_VARIANT: susfs_show_variant(arg); break;
    case CMD_SUSFS_SHOW_VERSION: susfs_show_version(arg); break;
    default: break;
    }
    return 0;
}

int susfs_ksu_sys_reboot(int magic1, int magic2, unsigned int cmd, void __user **arg)
{
    if ((u32)magic2 == SUSFS_MAGIC) {
        if (!uid_eq(current_uid(), GLOBAL_ROOT_UID))
            return 0;
        return susfs_ksu_handle_cmd(cmd, arg);
    }
    return ksu_handle_sys_reboot(magic1, magic2, cmd, arg);
}

static int __init susfs_ksu_glue_init(void)
{
    susfs_init();
    return 0;
}
late_initcall(susfs_ksu_glue_init);

struct static_key_true susfs_ksun_su_compat_key = STATIC_KEY_TRUE_INIT;

static void susfs_ksun_su_to_sh(struct filename **filename)
{
    static const char su[] = "/system/bin/su";
    struct filename *fn;
    if (!filename || IS_ERR_OR_NULL(*filename) || !xxksu_parent_sucompat_enabled() ||
        !xxksu_parent_uid_allowed(current_uid().val) || likely(strcmp((*filename)->name, su)))
        return;
    fn = getname_kernel("/system/bin/sh");
    if (IS_ERR(fn))
        return;
    putname(*filename);
    *filename = fn;
}

int susfs_ksun_handle_faccessat(int *dfd, struct filename **filename, int *mode, int *flags)
{
    susfs_ksun_su_to_sh(filename);
    return 0;
}

int susfs_ksun_handle_stat(int *dfd, struct filename **filename, int *flags)
{
    susfs_ksun_su_to_sh(filename);
    return 0;
}

#if !defined(CONFIG_XXKSU_MANUAL_HOOKS)
int susfs_ksun_handle_execveat(int *fd, struct filename **filename_ptr, void *argv, void *envp, int *flags)
{
    ksu_handle_execveat_ksud(fd, filename_ptr, argv, envp, flags);
    return ksu_handle_execveat_sucompat(fd, filename_ptr, argv, envp, flags);
}
#endif

static bool susfs_ksun_is_init_rc(struct file *fp)
{
    char path[256];
    char *dpath;
    if (strcmp(current->comm, "init") || !d_is_reg(fp->f_path.dentry))
        return false;
    dpath = d_path(&fp->f_path, path, sizeof(path));
    if (IS_ERR(dpath))
        return false;
    return !strcmp(dpath, "/init.rc") || !strcmp(dpath, "/system/etc/init/hw/init.rc");
}

void ksu_handle_vfs_fstat(int fd, loff_t *kstat_size_ptr)
{
    struct file *file;
    if (!&ksu_rc_len || !&ksu_init_rc_hook || !ksu_init_rc_hook)
        return;
    file = fget(fd);
    if (!file)
        return;
    if (susfs_ksun_is_init_rc(file))
        *kstat_size_ptr += ksu_rc_len;
    fput(file);
}

struct static_key_true ksu_is_input_hook_enabled __weak = STATIC_KEY_TRUE_INIT;

int __weak ksu_handle_post_execveat_sucompat(int *fd, struct filename **filename_ptr, void *argv, void *envp, int *flags, int *retval)
{
    return 0;
}

int __weak ksu_setup_preinit_file(struct filename **filename_ptr, struct user_arg_ptr *argv)
{
    return -ENOSYS;
}

u32 susfs_ksu_sid __weak;
u32 susfs_priv_app_sid __weak;
bool ksu_selinux_hide_running __weak;
struct page *fake_status __weak;
DEFINE_STATIC_KEY_FALSE(fake_status_initialize_key);
void __weak initialize_fake_status(void) { }
ssize_t __weak my_write_context(struct file *file, char *buf, size_t size) { return -EINVAL; }
ssize_t __weak my_write_access(struct file *file, char *buf, size_t size) { return -EINVAL; }
int __weak my_setprocattr(const char *name, void *value, size_t size) { return -EINVAL; }
#endif
