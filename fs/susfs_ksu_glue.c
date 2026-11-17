// SPDX-License-Identifier: GPL-2.0
/*
 * Glue between the in-tree SUSFS and KernelSU-Next (legacy).
 *
 * BakaSU carried this itself: ksu_handle_susfs_cmd() in its supercall
 * dispatcher, plus a susfs_init() call from its own init. KernelSU-Next
 * legacy has no SUSFS support, so the parent kernel provides both:
 *
 *  - kernel/reboot.c sends every reboot(2) call with the KernelSU install
 *    magic here. Calls carrying SUSFS_MAGIC from root are handled below (this
 *    is the interface the ksu_susfs tool and modules such as BRENE use); all
 *    other calls continue to ksu_handle_sys_reboot() in KernelSU-Next.
 *  - susfs_init() runs once at late_initcall.
 *
 * The priority UID filter command is handled earlier, in kernel/reboot.c.
 */
#include <linux/compiler.h>
#include <linux/cred.h>
#include <linux/init.h>
#include <linux/types.h>
#include <linux/uaccess.h>
#include <linux/susfs.h>
#include <linux/susfs_def.h>
#include <linux/susfs_ksu.h>

#ifdef CONFIG_KSU_SUSFS

/* Provided by KernelSU(-Next); weak so a missing symbol degrades, not breaks. */
extern bool is_ksu_domain(void) __weak;

/* BakaSU defined this; the in-tree SUSFS calls it. */
bool __weak susfs_is_current_ksu_domain(void)
{
	return is_ksu_domain ? is_ksu_domain() : false;
}

static int susfs_ksu_handle_cmd(unsigned int cmd, void __user **arg)
{
	switch (cmd) {
#ifdef CONFIG_KSU_SUSFS_SUS_PATH
	case CMD_SUSFS_ADD_SUS_PATH:
		susfs_add_sus_path(arg);
		break;
	case CMD_SUSFS_ADD_SUS_PATH_LOOP:
		susfs_add_sus_path_loop(arg);
		break;
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
	case CMD_SUSFS_HIDE_SUS_MNTS_FOR_NON_SU_PROCS:
		susfs_set_hide_sus_mnts_for_non_su_procs(arg);
		break;
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
	case CMD_SUSFS_ADD_SUS_KSTAT:
	case CMD_SUSFS_ADD_SUS_KSTAT_STATICALLY:
		susfs_add_sus_kstat(arg);
		break;
	case CMD_SUSFS_UPDATE_SUS_KSTAT:
		susfs_update_sus_kstat(arg);
		break;
#endif
#ifdef CONFIG_KSU_SUSFS_SPOOF_UNAME
	case CMD_SUSFS_SET_UNAME:
		susfs_set_uname(arg);
		break;
#endif
#ifdef CONFIG_KSU_SUSFS_ENABLE_LOG
	case CMD_SUSFS_ENABLE_LOG:
		susfs_enable_log(arg);
		break;
#endif
#ifdef CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG
	case CMD_SUSFS_SET_CMDLINE_OR_BOOTCONFIG:
		susfs_set_cmdline_or_bootconfig(arg);
		break;
#endif
#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT
	case CMD_SUSFS_ADD_OPEN_REDIRECT:
		susfs_add_open_redirect(arg);
		break;
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_MAP
	case CMD_SUSFS_ADD_SUS_MAP:
		susfs_add_sus_map(arg);
		break;
#endif
	case CMD_SUSFS_ENABLE_AVC_LOG_SPOOFING:
		susfs_set_avc_log_spoofing(arg);
		break;
	case CMD_SUSFS_SHOW_ENABLED_FEATURES:
		susfs_get_enabled_features(arg);
		break;
	case CMD_SUSFS_SHOW_VARIANT:
		susfs_show_variant(arg);
		break;
	case CMD_SUSFS_SHOW_VERSION:
		susfs_show_version(arg);
		break;
	default:
		break;
	}
	return 0;
}

int susfs_ksu_sys_reboot(int magic1, int magic2, unsigned int cmd,
			 void __user **arg)
{
	if ((u32)magic2 == SUSFS_MAGIC) {
		/* Only root may configure SUSFS. */
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

#endif /* CONFIG_KSU_SUSFS */
