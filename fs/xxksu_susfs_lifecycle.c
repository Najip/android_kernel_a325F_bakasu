// SPDX-License-Identifier: GPL-2.0
#include <linux/sched.h>
#include <linux/thread_info.h>
#include <linux/workqueue.h>
#include <linux/susfs.h>
#include <linux/susfs_def.h>
#include <linux/xxksu_parent_bridge.h>

extern struct work_struct susfs_extra_works;

void xxksu_parent_reset_task(void)
{
	susfs_clear_current_proc_no_su();
	susfs_clear_current_proc_umounted();
	susfs_clear_current_proc_umounted_for_zygote_next();
}

void xxksu_parent_deny_task(void)
{
	susfs_set_current_proc_no_su();
}

void xxksu_parent_finish_umount(void)
{
	/* Mirrors selection of xxKSU's unmount path, not per-mount success. */
	susfs_set_current_proc_umounted();
	schedule_work(&susfs_extra_works);
}

void xxksu_parent_post_fs_data(void)
{
	/* Called from xxKSU's existing once-only post-fs-data path. */
	susfs_start_sdcard_monitor_fn();
}
