# Samsung Galaxy A32 4G xxKSU + SUSFS Kernel

This is the **xxksu** branch. The repository has three variants, one branch each:
`common` (BakaSU), `ksun` (KernelSU-Next) and `xxksu` (this one).

Custom kernel for the **Samsung Galaxy A32 4G (SM-A325 series, MediaTek MT6768, Linux 4.14)** with
**xxKSU** (backslashxx KernelSU, manual hooks) and **SUSFS v2.4.0** from JackA1ltman's non-GKI patch set.

Keep a backup of your original `boot` image before flashing.

## What is included

- xxKSU from [backslashxx/KernelSU](https://github.com/backslashxx/KernelSU), built in with source-level manual hooks
  (no kprobes, no syscall-table or LSM hook modes).
- SUSFS v2.4.0 core from [JackA1ltman/NonGKI_Kernel_Build_2nd](https://github.com/JackA1ltman/NonGKI_Kernel_Build_2nd)
  with all ten features enabled: SUS_PATH, SUS_MOUNT, SUS_KSTAT, SPOOF_UNAME, ENABLE_LOG,
  HIDE_KSU_SUSFS_SYMBOLS, SPOOF_CMDLINE_OR_BOOTCONFIG, OPEN_REDIRECT, SUS_MAP and PRIORITY_UID_FILTER.
- Jack's priority UID filter and sus_path UID filter. App lists are refreshed when apps are installed or removed.
- Network fix (WiFi "connected, no internet" / VPN reconnect hang, UDP-only GSO), always applied.
- Optional performance tuning (`perf_tuning`, unticked by default): GPU 1100 MHz @ 1.035 V,
  CPU/CCI undervolt, GPU meter at `/sys/kernel/gpu/gpu_fmeter`, fast charging with the screen on,
  zram zstd, USB autosuspend off, BORE scheduler, 250 Hz, schedutil, BBR + fq_codel.
  The CPU undervolt was tuned on one phone; if yours freezes or reboots under load, build without it.
- AnyKernel3 flashable ZIP.

The exact upstream commits used are in [`sources.json`](sources.json).

## Download and flash

1. Open **Actions -> A325X Kernel**, or the **Releases** page.
2. Open the newest green run for branch `xxksu` and download the artifact named `A325X-xxKSU-SUSFS-...`.
3. Unzip it once. Inside is the flashable `A325X-xxKSU-SUSFS-<version>-<commit>.zip`.
4. Flash that ZIP in your recovery or with a kernel flasher app, then reboot.
5. Install the KernelSU manager from backslashxx/KernelSU if you do not have it yet.

## Building

Builds run on GitHub; you do not need a PC.

- **Automatic:** every change on the `xxksu` branch builds a ZIP on a GitHub runner.
- **By hand:** Actions -> **A325X Kernel** -> **Run workflow** -> branch `xxksu`.
  - `self_hosted`: on = your own PC runner (faster, cached compiler); off = GitHub runner.
  - `perf_tuning`: applies the optional tuning patch and `a325n-tuning.config`.
  - `publish_release`: also puts the ZIP on the Releases page.

What the build does (`build_xxksu.sh`, then `package_xxksu.sh`):

1. Downloads xxKSU at the commit in `sources.json` into `KernelSU/` and applies `patches/kernelsu/`.
2. Applies the device patches in `patches/kernel/`.
3. Downloads the pinned AOSP Clang 14.0.6 (`clang-r450784d`) and compiles.
4. Checks that the root hooks and SUSFS functions are linked, then packages the AnyKernel3 ZIP.

To build on your own Linux PC: `git clone` this repository, then run `sh build_xxksu.sh` and
`OUT_DIR=$PWD/out-xxksu PACKAGE_DIR=$PWD/package RUNNER_TEMP=/tmp TOOLCHAIN=$PWD/.toolchains/clang-r450784d sh package_xxksu.sh`.

## NoMount LKM

This kernel has no built-in NoMount. To use NoMount, build the module for this branch:
Actions -> **NoMount LKM** -> **Run workflow** -> branch `xxksu`. Leave `self_hosted` unticked
to use a GitHub runner; `nomount_ref` picks the upstream NoMount version (default `dev`).
Download the `nomount-lkm-...` artifact, unzip it once and flash the `NoMount-...zip` in your root manager.

## Updating xxKSU and SUSFS

The **Update sources** workflow runs every day at 08:23 WIB (started from the `common` branch).
To run it by hand: Actions -> **Update sources** -> **Run workflow** -> branch `xxksu`.

1. It checks xxKSU and Jack's SUSFS for new commits.
2. If there is something new, it opens a pull request named **Update xxksu: xxKSU / SUSFS update** and starts a
   test build of it.
3. Open the pull request, download the test ZIP from its **A325X Kernel** run and flash it.
4. If it works, press **Merge pull request**. The merge builds the final ZIP on `xxksu`.

The updater never applies risky changes silently:

- An xxKSU update is only taken if every patch in `patches/kernelsu/` still applies.
- A SUSFS core update (`fs/susfs.c`, `susfs.h`, `susfs_def.h`) is taken from Jack's patch, with
  our small local additions in `patches/susfs/` applied on top.
- If Jack changes the kernel hook part of his patch, the pull request is titled
  **(needs review)** and shows the changes; those hooks must be ported by hand before merging.
- If something no longer applies, the update run fails and its summary says why.

## Repository layout

| Path | Purpose |
|---|---|
| `sources.json` | Pinned xxKSU and SUSFS upstream commits |
| `patches/kernelsu/` | Small patches applied to xxKSU at build time |
| `patches/susfs/` | Local additions on top of Jack's SUSFS core |
| `patches/kernel/` | Device patches: network fix (always), optional tuning |
| `fs/susfs.c`, `include/linux/susfs*.h` | SUSFS v2.4.0 core |
| `arch/arm64/configs/` | Kernel config fragments |
| `build_xxksu.sh`, `package_xxksu.sh` | Build and package scripts |
| `.github/workflows/kernel.yml` | Build workflow |
| `.github/workflows/update.yml` | Updater workflow |
| `.github/workflows/nomount-lkm.yml` | NoMount module (LKM) workflow |

The kernel config is `mt6768_slm_defconfig` + `a32.config` + `battery.config` +
`ksu-a325n-common.config` + `a325n-release.config`. Some files keep the `a325n` name from the original
development device; the kernel targets the whole SM-A325 family.

## Reporting issues

Include: device model, ROM and Android version, KernelSU manager version, a screenshot of the
SUSFS module status, and the kernel log filtered for `KernelSU`, `ksu`, `susfs` and `init.rc`.

## Credits

- Base kernel: [Samsung-MT6769-Devs/android_kernel_samsung_mt6768](https://github.com/Samsung-MT6769-Devs/android_kernel_samsung_mt6768)
  and the original A32 BakaSU kernel tree by mzggr0914.
- xxKSU: [backslashxx/KernelSU](https://github.com/backslashxx/KernelSU), based on
  [tiann/KernelSU](https://github.com/tiann/KernelSU).
- SUSFS: [simonpunk/susfs4ksu](https://gitlab.com/simonpunk/susfs4ksu); non-GKI 4.14 port by
  [JackA1ltman/NonGKI_Kernel_Build_2nd](https://github.com/JackA1ltman/NonGKI_Kernel_Build_2nd).
- AnyKernel3: [osm0sis/AnyKernel3](https://github.com/osm0sis/AnyKernel3).
