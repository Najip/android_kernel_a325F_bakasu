#!/bin/sh
# KernelSU-Next (legacy) build of the A325F/N 4.14 kernel.
# Same toolchain and config fragments as build_a325n.sh, without the BakaSU checks.
# NO_NOMOUNT=1 appends "# CONFIG_NOMOUNT is not set" as the last config fragment.
#
# Kernel patches are always applied:
#   1. every patches/kernel/*.patch on this branch, in file-name order;
#   2. if there are none, the perf patch (a file named NNNN-*perf-1100mhz*.patch)
#      is looked up anywhere in the tree of PERF_PATCH_REF
#      (default nomount-lkm-sync-up-patch) and applied.
# The names of applied patches go to $OUT/applied-patches.txt.
# NO_KERNEL_PATCHES=1 skips all of it (local experiments only).
set -eu

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
# shellcheck source=scripts/aosp_clang14.conf
. "$ROOT/scripts/aosp_clang14.conf"
OUT=${OUT_DIR:-"$ROOT/out"}
TOOLCHAIN=${TOOLCHAIN:-"$ROOT/.toolchains/$AOSP_CLANG_DIRECTORY"}
JOBS=${JOBS:-$(nproc)}

if [ ! -f "$ROOT/KernelSU/kernel/Kconfig" ]; then
  echo "KernelSU submodule is empty; run the setup-ksun-submodules workflow first" >&2
  exit 1
fi
if ! git -C "$ROOT" config -f .gitmodules --get submodule.KernelSU.url | grep -qi 'KernelSU-Next'; then
  echo "KernelSU submodule is not KernelSU-Next; run the setup-ksun-submodules workflow first" >&2
  exit 1
fi

sh "$ROOT/scripts/fetch_aosp_clang.sh" "$TOOLCHAIN"
# Keep the recorded compiler path independent of the caller's directory.
TOOLCHAIN=$(CDPATH='' cd -- "$TOOLCHAIN" && pwd)
for tool in aarch64-linux-gnu-as aarch64-linux-gnu-elfedit; do
  command -v "$tool" >/dev/null || {
    echo "Missing $tool; install binutils-aarch64-linux-gnu" >&2
    exit 1
  }
done

export ARCH=arm64
export PATH="$TOOLCHAIN/bin:$PATH"
export LD_LIBRARY_PATH="$TOOLCHAIN/lib64:$TOOLCHAIN/lib:${LD_LIBRARY_PATH:-}"
export CC="$TOOLCHAIN/bin/clang"
export LD="$TOOLCHAIN/bin/ld.lld"
export AR="$TOOLCHAIN/bin/llvm-ar"
export NM="$TOOLCHAIN/bin/llvm-nm"
export STRIP="$TOOLCHAIN/bin/llvm-strip"
export OBJCOPY="$TOOLCHAIN/bin/llvm-objcopy"
export OBJDUMP="$TOOLCHAIN/bin/llvm-objdump"
export READELF="$TOOLCHAIN/bin/llvm-readelf"
export CROSS_COMPILE=aarch64-linux-gnu-
AS=$(command -v aarch64-linux-gnu-as)
export AS
export LLVM=1
export LLVM_IAS=0
export KBUILD_BUILD_USER=${KBUILD_BUILD_USER:-ksun}
export KBUILD_BUILD_HOST=${KBUILD_BUILD_HOST:-builder}
export KBUILD_BUILD_VERSION=${KBUILD_BUILD_VERSION:-1}
if [ -z "${KBUILD_BUILD_TIMESTAMP:-}" ]; then
  KBUILD_BUILD_TIMESTAMP=$(git -C "$ROOT" show -s --format=%cD HEAD)
  export KBUILD_BUILD_TIMESTAMP
fi
VENDOR_WARN_FLAGS="-Wno-error \
-Wno-error=incompatible-pointer-types \
-Wno-error=int-conversion \
-Wno-error=visibility \
-Wno-error=fortify-source \
-Wno-error=pointer-to-int-cast \
-Wno-error=typedef-redefinition \
-Wno-error=strict-prototypes \
-Wno-error=implicit-function-declaration"
export KCFLAGS=${KCFLAGS:-$VENDOR_WARN_FLAGS}

mkdir -p "$OUT"
: > "$OUT/applied-patches.txt"

apply_one() {
  name=$(basename "$1")
  if git -C "$ROOT" apply --check --reverse "$1" >/dev/null 2>&1; then
    echo "Kernel patch already applied: $name"
  else
    git -C "$ROOT" apply --check "$1" || {
      echo "::error::Kernel patch does not apply: $name" >&2
      exit 1
    }
    git -C "$ROOT" apply "$1"
    echo "Applied kernel patch: $name"
  fi
  printf '%s\n' "$name" >> "$OUT/applied-patches.txt"
}

apply_kernel_patches() {
  found=0
  if [ -d "$ROOT/patches/kernel" ]; then
    for p in $(find "$ROOT/patches/kernel" -maxdepth 1 -type f -name '*.patch' | sort); do
      found=1
      apply_one "$p"
    done
  fi
  if [ "$found" = 1 ]; then
    return 0
  fi

  src_ref=${PERF_PATCH_REF:-nomount-lkm-sync-up-patch}
  echo "No patches/kernel/*.patch on this branch; looking for the perf patch on $src_ref"
  git -C "$ROOT" fetch --no-tags --depth=1 origin "$src_ref"
  path=$(git -C "$ROOT" ls-tree -r --name-only FETCH_HEAD \
    | grep -E '(^|/)[0-9]{4}-.*perf-1100mhz.*\.patch$' | sort | tail -n1 || true)
  if [ -z "$path" ]; then
    echo "::error::No *perf-1100mhz*.patch found on $src_ref. Add patches/kernel/0001-*.patch to this branch." >&2
    exit 1
  fi
  echo "Using $path from $src_ref"
  git -C "$ROOT" show "FETCH_HEAD:$path" > "$OUT/$(basename "$path")"
  test -s "$OUT/$(basename "$path")"
  apply_one "$OUT/$(basename "$path")"
}

if [ "${NO_KERNEL_PATCHES:-0}" = 1 ]; then
  echo "Kernel patches skipped (NO_KERNEL_PATCHES=1)"
else
  apply_kernel_patches
fi

cp "$TOOLCHAIN/aosp-source.txt" "$OUT/toolchain-source.txt"
"$CC" --version > "$OUT/clang-version.txt"
"$LD" --version > "$OUT/lld-version.txt"
cat "$OUT/clang-version.txt" "$OUT/lld-version.txt" >> "$OUT/toolchain-source.txt"
"$AS" --version >> "$OUT/toolchain-source.txt"

{
  echo "KernelSU-Next commit: $(git -C "$ROOT/KernelSU" rev-parse HEAD)"
  echo "KernelSU-Next describe: $(git -C "$ROOT/KernelSU" describe --tags --always 2>/dev/null || echo unknown)"
} > "$OUT/ksun-source.txt"
cat "$OUT/ksun-source.txt"

set -- \
  "$ROOT/arch/arm64/configs/mt6768_slm_defconfig" \
  "$ROOT/arch/arm64/configs/a32.config" \
  "$ROOT/arch/arm64/configs/battery.config" \
  "$ROOT/arch/arm64/configs/ksu-a325n-common.config" \
  "$ROOT/arch/arm64/configs/a325n-release.config"
if [ "${NO_NOMOUNT:-0}" = 1 ]; then
  printf '# CONFIG_NOMOUNT is not set\n' > "$OUT/no-nomount.config"
  set -- "$@" "$OUT/no-nomount.config"
fi
"$ROOT/scripts/kconfig/merge_config.sh" -m -O "$OUT" "$@"

make -C "$ROOT" O="$OUT" olddefconfig
# The embedded preinit runner uses these target headers. Install them before
# Kbuild evaluates its code generators, including on a fresh output directory.
make -C "$ROOT" O="$OUT" headers_install INSTALL_HDR_PATH="$OUT/usr"
make -C "$ROOT" O="$OUT" -j"$JOBS"
