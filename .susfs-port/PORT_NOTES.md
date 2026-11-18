# Jack SUSFS v2.4.0 core on xxKSU manual hooks

- Jack commit: 26f2313be61f7a8603a50b2dcd12171495a79d27 (`Patches/Patch/susfs_patch_to_4.14.patch`).
- `fs/susfs.c`, `include/linux/susfs.h` and `include/linux/susfs_def.h` are Jack's v2.4.0 files at that
  commit, including the SUS_PATH `i_state` fix. Local additions only:
  - `susfs_get_data_path()` (used by the existing `fs/readdir.c` hooks),
  - empty `SUSFS_LOGI_RL`/`SUSFS_LOGE_RL` stubs for builds with logs disabled,
  - `#ifndef` guards around `getname_safe`/`putname_safe` in `susfs.h`.
- Jack's credential switch (`setup_selinux("u:r:ksu:s0")` + `commit_creds`) is used unchanged; xxKSU
  exports `setup_selinux`, `ksu_cred` and `is_ksu_domain` with matching signatures.
- `fs/susfs_priority.c` (the earlier standalone filter) is removed from source and Kbuild. The priority
  UID filter is Jack's `void susfs_set_priority_uid_filter(void __user **)`.
- `fs/susfs_ksu_glue.c` dispatches `CMD_SUSFS_SET_PRIORITY_UID_FILTER` and
  `CMD_SUSFS_SET_SUS_PATH_UID_FILTER`; `kernel/reboot.c` uses the double-pointer API.
- `block/ioprio.c` and `kernel/sys.c` declare `susfs_is_priority_uid_filtered()` explicitly (Jack's
  header no longer declares it) and are guarded by `CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER`.
- Package changes: xxKSU's throne tracker thread calls `xxksu_parent_packages_changed()` (patch 0006),
  which asks Jack's code to resolve the priority and sus_path package lists again.
- Config: `CONFIG_KSU_SUSFS_ENABLE_LOG=y` and `CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER=y`, so all ten
  feature options are enabled.
- Hook files (`fs/namei.c`, `fs/namespace.c`, `fs/readdir.c`, `fs/proc/*`, `fs/statfs.c`,
  `kernel/kallsyms.c`, `mm/memory.c`, `security/selinux/avc.c`) already matched Jack's patch line for
  line and are unchanged. `fs/stat.c` and `fs/super.c` keep their existing equivalent adaptations.
- Behaviour change that comes with Jack v2.4.0: SUS_PATH entries are hidden from every app UID
  (10000-19999 per user) unless the UID is allowed through the sus_path UID filter; v2.3.0 only hid
  them from processes marked as umounted.
- Verification so far: every touched object and KernelSU `ksu.o` compile with the pinned AOSP Clang
  14.0.6, with no unresolved symbols against the previous build's System.map. Boot, root and SUSFS
  runtime behaviour on the device are not yet tested.
