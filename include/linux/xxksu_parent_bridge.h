/* SPDX-License-Identifier: GPL-2.0 */
#ifndef _LINUX_XXKSU_PARENT_BRIDGE_H
#define _LINUX_XXKSU_PARENT_BRIDGE_H

#include <linux/types.h>

bool xxksu_parent_sucompat_enabled(void);
bool xxksu_parent_uid_allowed(uid_t uid);
void xxksu_parent_read_fd(unsigned int fd);

void xxksu_parent_reset_task(void);
void xxksu_parent_deny_task(void);
void xxksu_parent_finish_umount(void);
void xxksu_parent_post_fs_data(void);

#endif
