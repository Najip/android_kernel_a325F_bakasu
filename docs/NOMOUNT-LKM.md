# NoMount LKM workflow guide (Linux 4.14, A325X)

This guide explains the **Build NoMount LKM + flashable ZIP (4.14)** workflow:
what the two input fields do, what to type (or leave blank), and what to flash.

## Quick links

- [Open the workflow in Actions](https://github.com/Najip/android_kernel_a325F_bakasu/actions/workflows/build-nomount-lkm.yml) (click **Run workflow** on the right)
- [Workflow file](https://github.com/Najip/android_kernel_a325F_bakasu/blob/nomount-lkm/.github/workflows/build-nomount-lkm.yml)
- [All branches](https://github.com/Najip/android_kernel_a325F_bakasu/branches)
- [Upstream NoMount branches](https://github.com/maxsteeel/nomount/branches) and [tags](https://github.com/maxsteeel/nomount/tags)
- [Upstream NoMount releases](https://github.com/maxsteeel/nomount/releases)

GitHub does not make links clickable inside the **Run workflow** form, so open this guide first.

## What it builds

One run produces:

- `nomount-4.14.ko`, the NoMount kernel module built against the chosen kernel's config.
- A flashable NoMount module ZIP (KernelSU/APatch) that already contains `lkm/nomount-4.14.ko`, `nm` and `lkmloader`.
- `SHA256SUMS.txt` and `build-info.txt` (which refs and commits were used).

It is for kernels **without NoMount built in**. If the kernel already has NoMount built in, the module installer detects it and removes the bundled `.ko`.

## How to run

1. Open the [workflow page](https://github.com/Najip/android_kernel_a325F_bakasu/actions/workflows/build-nomount-lkm.yml).
2. Click **Run workflow**.
3. Set **Use workflow from** to `nomount-lkm`. The workflow file itself lives on that branch.
4. Fill in the two fields below, or leave them blank.
5. Click **Run workflow**, then download the artifact when it finishes.

## The two fields

| Field | Blank means | You can type |
|---|---|---|
| `kernel_ref` | Build the kernel from the branch you chose in **Use workflow from** (`nomount-lkm`) | A kernel branch, tag or commit: `common`, `sync-up`, `sync-up-patch` |
| `nomount_ref` | Use the NoMount commit already vendored in that kernel (the first line of `fs/nomount/Makefile`) | An upstream NoMount branch, tag or commit: `master`, `dev`, `v2.3.0-720`, or a sha |

Both fields are optional.

### What `kernel_ref` controls

The kernel source, config fragments and toolchain scripts come from this ref. The `.ko` is compiled against this exact kernel, so choose the same branch you use for the kernel you flash.

### What `nomount_ref` controls

- **Blank:** the build uses the NoMount source that is already inside the chosen kernel branch. The module ZIP is built from the matching upstream commit.
- **Set:** the workflow copies upstream's `kernel/src` into `fs/nomount/` for this run only. Nothing is committed to any branch. The `.ko`, `nm`, `lkmloader` and module scripts all come from that same upstream commit, so they match each other.

## Examples

| Goal | `kernel_ref` | `nomount_ref` |
|---|---|---|
| Match what `common` currently vendors | `common` | blank |
| Same, for the `sync-up-patch` kernel | `sync-up-patch` | blank |
| Latest upstream dev NoMount on the `common` kernel | `common` | `dev` |
| Released NoMount on the `sync-up` kernel | `sync-up` | `v2.3.0-720` |
| Everything default | blank | blank |

## What to flash

Use a kernel that does not have NoMount built in, then the module ZIP:

1. Build and flash the kernel from the [A325X Kernel (no NoMount)](https://github.com/Najip/android_kernel_a325F_bakasu/actions/workflows/kernel-no-nomount.yml) workflow, on the same branch as `kernel_ref`.
2. Flash the NoMount module ZIP from this workflow's artifact in KernelSU or APatch.
3. Reboot.

The ZIP name shows what went into it: `...-k<kernel sha>-n<nomount sha>.zip`.

## What the build checks

- `CONFIG_MODULES=y` in the final kernel config (the build stops if it is off).
- The module's vermagic matches the build's `kernel.release`.
- The ZIP contains `lkm/nomount-4.14.ko`, `bin/nm-arm64` and `bin/lkmloader-arm64`.

If the kernel branch has no `CONFIG_NOMOUNT` symbol, the build prints a warning and passes `CONFIG_NOMOUNT=m` on the command line instead.

## What happens when you flash it

The installer loads the `.ko` while flashing. If it cannot load a driver it aborts with "Kernel module not detected" and prints the loader's error. It also aborts if the loaded driver is older than the version the module needs. `lkmloader` can retry a vermagic mismatch by patching the string, but that does not fix real ABI differences.

## Troubleshooting

| Symptom | Likely cause | What to try |
|---|---|---|
| "This kernel has no vendored NoMount" | The chosen kernel has no `fs/nomount/Makefile` | Set `nomount_ref` (for example `master` or `dev`) |
| "CONFIG_MODULES is not enabled" | That kernel config cannot load modules | Enable `CONFIG_MODULES` in the kernel config first |
| vermagic does not match | Build used a different release string than expected | Check the `Verify and collect module` log lines |
| `nm` step fails on headers | Upstream changed the layout of `nm.h` | Send the failing step's log |
| Flash aborts: kernel module not detected | `.ko` rejected by the running kernel, or NoMount is in a different mode | Make sure the running kernel is the no-NoMount build from the same branch, then read the printed loader error |

## Notes

- Everything here has been written but not yet confirmed on a device. Treat the first flash as a test.
- `nomount_ref` accepts anything `git checkout` understands in the upstream repository.
- Builds expire from Actions after 14 days; re-run to get a fresh artifact.
