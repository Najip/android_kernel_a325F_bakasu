/* SPDX-License-Identifier: GPL-2.0 */
#ifndef _LINUX_XXKSU_MANUAL_HOOKS_H
#define _LINUX_XXKSU_MANUAL_HOOKS_H
#include <linux/compiler.h>
#include <linux/types.h>
struct cred;
struct inode;
struct dentry;
struct file;
struct linux_binprm;
struct stat;
struct stat64;
#ifdef CONFIG_XXKSU_MANUAL_HOOKS
int ksu_handle_sys_execve(const char __user **filename, void *argv, void *envp);
int ksu_handle_sys_execveat(int *fd, const char __user **filename, void *argv, void *envp, int *flags);
int ksu_task_fix_setuid(struct cred *new, const struct cred *old, int flags);
int ksu_inode_rename(struct inode *old_dir, struct dentry *old_dentry, struct inode *new_dir, struct dentry *new_dentry);
int ksu_bprm_check(struct linux_binprm *bprm);
int ksu_file_permission(struct file *file, int mask);
int ksu_hide_setprocattr(const char *name, void *value, size_t size);
int ksu_hide_inode_setxattr(struct dentry *dentry, const char *name, void *value, size_t *size, int *flags);
void ksu_handle_newfstat_ret(unsigned int *fd, struct stat __user **statbuf_ptr);
void ksu_handle_fstat64_ret(unsigned long *fd, struct stat64 __user **statbuf_ptr);
#endif
#endif
