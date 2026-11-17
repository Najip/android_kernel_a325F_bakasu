/* SPDX-License-Identifier: GPL-2.0 */
#ifndef _LINUX_SUSFS_KSUN_H
#define _LINUX_SUSFS_KSUN_H

#if defined(CONFIG_KSU_SUSFS) && !defined(SUSFS_KSUN_GLUE_BUILD)
#define ksu_handle_faccessat	susfs_ksun_handle_faccessat
#define ksu_handle_stat		susfs_ksun_handle_stat
#define ksu_su_compat_enabled	susfs_ksun_su_compat_key
#define ksu_handle_execveat	susfs_ksun_handle_execveat
#define ksu_handle_sys_reboot	susfs_ksu_sys_reboot
#endif

#endif /* _LINUX_SUSFS_KSUN_H */
