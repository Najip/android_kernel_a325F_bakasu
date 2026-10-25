# BakaSU Linux 4.14 compatibility patch

The submodule pins an unmodified upstream commit. The parent repository owns
`0001-a325x-linux414-integration.patch`, initially based on BakaSU main
`d5e9e025b8b49155f8014684d64c91742b465f65` (UAPI v6).

The patch adapts module-hook discovery to `kernel/module.c`, gives BakaSU's
blacklist pointer a distinct name so kallsyms can find the native variable
unambiguously, checks that the
SUSFS preinit setup and cleanup hooks are present, and keeps the generated
syscall header dependency for the preinit object. SUSFS builds require the
runner's target UAPI headers instead of silently omitting the runner.

Preinit stages a shmem runner and reports support only after staging succeeds.
Its SUSFS setup validates PID 1 and allocates a new filename. The distinct
`ksu_setup_preinit_file_owned` symbol makes an unprepared upstream submodule
fail to link, rather than use upstream's incompatible in-place filename API.
The caller owns
the original filename and can retry the real init once after a recoverable
exec failure. Cleanup accepts fd 0 and never rewrites a filename buffer.
The parent exec path restores its files table before closing the runner fd;
it does not retry after `flush_old_exec()` has replaced the old mm.

The parent module loader marks explicit blacklist rejections, completes normal
cleanup, then invokes the matching BakaSU acknowledgement hook. Other `-EPERM`
errors keep their original return values.

## Preparing a build

`build_a325n.sh` runs preparation automatically. For a direct make build, run
these commands from the repository root first:

```sh
sh scripts/prepare_bakasu.sh --apply
make O=/absolute/path/to/output ARCH=arm64 headers_install \
  INSTALL_HDR_PATH=/absolute/path/to/output/usr
```

Use `sh scripts/prepare_bakasu.sh --check` for a read-only compatibility check.
Preparation accepts a clean upstream worktree or exactly the reviewed patch,
using a temporary Git index to compare all tracked files. It rejects staged
edits, unrelated tracked edits and non-ignored untracked files. It never resets
the submodule or commits changes inside it. The patched submodule therefore
appears modified in `git status`; the tracked patch stores those modifications.

The updater checks the candidate upstream commit before committing its gitlink.
If upstream changes or incorporates this patch, review and regenerate it;
preparation must not silently skip a failed patch. Build logs record both the
upstream SHA and patch SHA256 in `bakasu-source.txt`.

## Validation boundary

An arm64 runner in vmlinux confirms build integration. Device boot logs must
still confirm that Samsung init executes `/system/bin/init selinux_setup`,
that `/metadata` is available then, and that prepared actions run. Use a matching
UAPI v6 Manager/ksud. Kernel module loading and exec recovery need runtime
verification before claiming device support for these new paths.
