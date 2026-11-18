# Samsung Galaxy A32 4G KernelSU-Next + SUSFS Kernel

This is the **ksun** branch. The repository has three variants, one branch each:
`common` (BakaSU), `ksun` (KernelSU-Next, this one) and `xxksu` (xxKSU).

Custom kernel for the **Samsung Galaxy A32 4G (SM-A325 series, MediaTek MT6768, Linux 4.14)** with
**KernelSU-Next** (legacy branch) and **SUSFS v2.4.0** from JackA1ltman's non-GKI patch set.

Keep a backup of your original `boot` image before flashing.

## What is included

- KernelSU-Next from the `legacy` branch of [KernelSU-Next/KernelSU-Next](https://github.com/KernelSU-Next/KernelSU-Next),
  accepting the official KernelSU-Next manager.
- SUSFS v2.4.0 core from [JackA1ltman/NonGKI_Kernel_Build_2nd](https://github.com/JackA1ltman/NonGKI_Kernel_Build_2nd),
  including the priority UID filter. App lists are refreshed when apps are installed or removed.
  SUSFS logging is off.
- Wi-Fi/network fix and performance tuning patch (`patches/kernel/0001-wifi-fix-perf-1100mhz-...`), always applied.
- AnyKernel3 flashable ZIP.

The exact upstream commits used are in [`sources.json`](sources.json).

## Download and flash

1. Open **Actions -> A325X Kernel**, or the **Releases** page.
2. Open the newest green run for branch `ksun` and download the artifact named `A325X-KSUN-...`.
3. Unzip it once. Inside is the flashable `A325X-KSUN-<version>-SUSFS-<version>-<commit>.zip`.
4. Flash that ZIP in your recovery or with a kernel flasher app, then reboot.
5. Install the KernelSU-Next manager if you do not have it yet.

## Building

Builds run on GitHub; you do not need a PC.

- **Automatic:** every change on the `ksun` branch builds a ZIP on a GitHub runner.
- **By hand:** Actions -> **A325X Kernel** -> **Run workflow** -> branch `ksun`.
  - `self_hosted`: on = your own PC runner (faster, cached compiler); off = GitHub runner.
  - `publish_release`: also puts the ZIP on the Releases page.

What the build does (`build_ksun.sh`, then `package_ksun.sh`):

1. Downloads KernelSU-Next at the commit in `sources.json` into `KernelSU/` and applies `patches/kernelsu/`.
2. Applies the device patches in `patches/kernel/`.
3. Downloads the pinned AOSP Clang 14.0.6 (`clang-r450784d`) and compiles.
4. Checks that KernelSU-Next and SUSFS are linked, then packages the AnyKernel3 ZIP.

## Updating KernelSU-Next and SUSFS

The **Update sources** workflow runs every day at 08:23 WIB (started from the `common` branch).
To run it by hand: Actions -> **Update sources** -> **Run workflow** -> branch `ksun`.

1. It checks KernelSU-Next and Jack's SUSFS for new commits.
2. If there is something new, it opens a pull request named **Update ksun: KernelSU-Next / SUSFS update**
   and starts a test build of it.
3. Open the pull request, download the test ZIP from its **A325X Kernel** run and flash it.
4. If it works, press **Merge pull request**. The merge builds the final ZIP on `ksun`.

The updater never applies risky changes silently:

- A KernelSU-Next update is only taken if every patch in `patches/kernelsu/` still applies.
- A SUSFS core update (`fs/susfs.c`, `susfs.h`, `susfs_def.h`) is taken from Jack's patch, with
  our local additions in `patches/susfs/` applied on top.
- If Jack changes the kernel hook part of his patch, the pull request is titled
  **(needs review)** and shows the changes; those hooks must be ported by hand before merging.
- If something no longer applies, the update run fails and its summary says why.

## Repository layout

| Path | Purpose |
|---|---|
| `sources.json` | Pinned KernelSU-Next and SUSFS upstream commits |
| `patches/kernelsu/` | Small patches applied to KernelSU-Next at build time |
| `patches/susfs/` | Local additions on top of Jack's SUSFS core |
| `patches/kernel/` | Device patches: network fix and tuning, link fix |
| `fs/susfs*.c`, `include/linux/susfs*.h` | SUSFS v2.4.0 core and KernelSU-Next glue |
| `arch/arm64/configs/` | Kernel config fragments |
| `build_ksun.sh`, `package_ksun.sh` | Build and package scripts |
| `.github/workflows/kernel.yml` | Build workflow |
| `.github/workflows/update.yml` | Updater workflow |

The kernel config is `mt6768_slm_defconfig` + `a32.config` + `battery.config` +
`ksu-a325n-common.config` + `a325n-release.config`.

## Credits

- Base kernel: [Samsung-MT6769-Devs/android_kernel_samsung_mt6768](https://github.com/Samsung-MT6769-Devs/android_kernel_samsung_mt6768)
  and the original A32 BakaSU kernel tree by mzggr0914.
- KernelSU-Next: [KernelSU-Next/KernelSU-Next](https://github.com/KernelSU-Next/KernelSU-Next), based on
  [tiann/KernelSU](https://github.com/tiann/KernelSU).
- SUSFS: [simonpunk/susfs4ksu](https://gitlab.com/simonpunk/susfs4ksu); non-GKI 4.14 port by
  [JackA1ltman/NonGKI_Kernel_Build_2nd](https://github.com/JackA1ltman/NonGKI_Kernel_Build_2nd).
- AnyKernel3: [osm0sis/AnyKernel3](https://github.com/osm0sis/AnyKernel3).
