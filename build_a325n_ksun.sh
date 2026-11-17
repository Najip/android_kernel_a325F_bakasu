#!/bin/sh
# KernelSU-Next (legacy) build of the A325F/N 4.14 kernel.
# Same toolchain and config fragments as build_a325n.sh, without the BakaSU checks.
# NO_NOMOUNT=1 appends "# CONFIG_NOMOUNT is not set" as the last config fragment.
# APPLY_PERF_PATCH=1 (default) fetches the 0003 perf patch from PERF_PATCH_REF
# (default nomount-lkm-sync-up-patch) and applies it; PERF_PATCH_EXCLUDE is a
# comma-separated list of path globs whose hunks are dropped from that patch.
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

apply_perf_patch() {
  perf_patch='0003-wifi-fix-perf-1100mhz-1035mv_uv75_zstd_usbnoauto-juan.patch'
  src_ref=${PERF_PATCH_REF:-nomount-lkm-sync-up-patch}
  # Path globs must reach git apply unexpanded.
  set -f
  for path in $(printf '%s' "${PERF_PATCH_EXCLUDE:-}" | tr ',' ' '); do
    echo "Perf patch: dropping hunks for $path"
    set -- "$@" "--exclude=$path"
  done
  git -C "$ROOT" fetch --no-tags --depth=1 origin "$src_ref"
  git -C "$ROOT" show "FETCH_HEAD:patches/kernel/$perf_patch" > "$OUT/$perf_patch"
  test -s "$OUT/$perf_patch"
  if git -C "$ROOT" apply --check --reverse "$@" "$OUT/$perf_patch" >/dev/null 2>&1; then
    echo "Perf patch already applied: $perf_patch"
  else
    git -C "$ROOT" apply --check "$@" "$OUT/$perf_patch"
    git -C "$ROOT" apply "$@" "$OUT/$perf_patch"
    echo "Applied perf patch from $src_ref: $perf_patch"
  fi
  set +f
}

if [ "${APPLY_PERF_PATCH:-1}" = 1 ]; then
  apply_perf_patch
else
  echo "Perf patch skipped (APPLY_PERF_PATCH=${APPLY_PERF_PATCH:-})"
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
