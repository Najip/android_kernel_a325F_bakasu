## SUSFS patch delta

- Kernel commit: 36ba798ec5d60554778598b720bec77e52374749
- Jack commit: bbe032eb06c50d24a9207bf2ece5e25cf2460bd0
- Patch: Patches/Patch/susfs_patch_to_4.14.patch
- In-tree SUSFS_VERSION: v2.3.0
- Patch SUSFS_VERSION: v2.4.0

| File | Hunks | Added lines | Already in tree | Missing | Removed lines still in tree | Status |
|---|---|---|---|---|---|---|
| `block/ioprio.c` | 3 | 8 | 2 | 6 | 0 of 0 | PARTIAL |
| `fs/Makefile` | 1 | 6 | 1 | 5 | 0 of 0 | PARTIAL |
| `fs/namei.c` | 26 | 182 | 180 | 2 | 0 of 0 | PARTIAL |
| `fs/namespace.c` | 11 | 181 | 181 | 0 | 0 of 0 | IN TREE |
| `fs/notify/fdinfo.c` | 4 | 56 | 56 | 0 | 0 of 0 | IN TREE |
| `fs/proc/base.c` | 4 | 14 | 14 | 0 | 0 of 0 | IN TREE |
| `fs/proc/cmdline.c` | 1 | 8 | 8 | 0 | 0 of 0 | IN TREE |
| `fs/proc/fd.c` | 2 | 51 | 51 | 0 | 0 of 0 | IN TREE |
| `fs/proc/task_mmu.c` | 8 | 38 | 38 | 0 | 0 of 0 | IN TREE |
| `fs/proc_namespace.c` | 3 | 143 | 143 | 0 | 0 of 0 | IN TREE |
| `fs/readdir.c` | 21 | 80 | 77 | 3 | 0 of 0 | PARTIAL |
| `fs/stat.c` | 2 | 33 | 10 | 23 | 0 of 0 | PARTIAL |
| `fs/statfs.c` | 2 | 56 | 56 | 0 | 0 of 0 | IN TREE |
| `fs/super.c` | 2 | 17 | 8 | 9 | 0 of 0 | PARTIAL |
| `fs/susfs.c` | 1 | 1862 | 1080 | 782 | 0 of 0 | PARTIAL |
| `include/linux/susfs.h` | 1 | 186 | 172 | 14 | 0 of 0 | PARTIAL |
| `include/linux/susfs_def.h` | 1 | 165 | 158 | 7 | 0 of 0 | PARTIAL |
| `kernel/kallsyms.c` | 2 | 24 | 24 | 0 | 0 of 0 | IN TREE |
| `kernel/sys.c` | 4 | 14 | 9 | 5 | 0 of 0 | PARTIAL |
| `mm/memory.c` | 2 | 6 | 6 | 0 | 0 of 0 | IN TREE |
| `security/selinux/avc.c` | 3 | 13 | 13 | 0 | 0 of 0 | IN TREE |

IN TREE: 11, PARTIAL: 10

Total added lines: 3143, missing: 856

### Tree vs Jack (new files)

| New file in Jack patch | Tree-only lines (-) | Jack-only lines (+) |
|---|---|---|
| `fs/susfs.c` | 56 | 1142 |
| `include/linux/susfs.h` | 27 | 37 |
| `include/linux/susfs_def.h` | 10 | 14 |
