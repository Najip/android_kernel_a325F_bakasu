// SPDX-License-Identifier: GPL-2.0
/*
 * Compatibility shim for KernelSU-Next (legacy).
 *
 * fs/read_write.c gates its call to ksu_handle_sys_read() with the static key
 * ksu_is_init_rc_hook_enabled, which BakaSU used to define. KernelSU-Next gates
 * inside its own ksu_handle_sys_read() with a plain bool (ksu_init_rc_hook), so
 * the key only has to exist and stay enabled. It is weak so a BakaSU build of
 * this tree still links with BakaSU's own definition.
 */
#include <linux/compiler.h>
#include <linux/jump_label.h>

#ifdef CONFIG_KSU
struct static_key_true ksu_is_init_rc_hook_enabled __weak = STATIC_KEY_TRUE_INIT;
#endif
