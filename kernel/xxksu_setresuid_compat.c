// SPDX-License-Identifier: GPL-2.0
#include <linux/types.h>

/*
 * kernel/sys.c still calls the legacy setresuid hook. The pinned xxKSU source
 * performs this work from its task_fix_setuid LSM hook, so this compatibility
 * stub intentionally does nothing.
 */
int ksu_handle_setresuid(uid_t ruid, uid_t euid, uid_t suid)
{
	return 0;
}
