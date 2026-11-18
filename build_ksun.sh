#!/bin/sh
# KernelSU-Next (legacy) + SUSFS build of the A325X 4.14 kernel.
#  1. downloads KernelSU-Next at the commit pinned in sources.json into KernelSU/
#     and applies patches/kernelsu/ (scripts/setup_sources.py);
#  2. applies every patches/kernel/*.patch in file-name order;
#  3. compiles with the pinned AOSP Clang 14.
# The names of applied kernel patches go to $OUT/applied-patches.txt.
#
# Manager signature: KSU_NEXT_MANAGER_SIZE and KSU_NEXT_MANAGER_HASH (environment)
# select the manager signing certificate the kernel accepts. Leave both unset to
# keep the official KernelSU-Next key.
set -eu

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
# shellcheck source=scripts/aosp_clang14.conf
. "$ROOT/scripts/aosp_clang14.conf"
OUT=${OUT_DIR:-"$ROOT/out-ksun"}
case "$OUT" in /*) ;; *) OUT="$ROOT/$OUT" ;; esac
TOOLCHAIN=${TOOLCHAIN:-"$ROOT/.toolchains/$AOSP_CLANG_DIRECTORY"}
JOBS=${JOBS:-$(nproc)}

python3 "$ROOT/scripts/setup_sources.py" "$OUT"

KSU_NEXT_MANAGER_SIZE=${KSU_NEXT_MANAGER_SIZE:-}
KSU_NEXT_MANAGER_HASH=${KSU_NEXT_MANAGER_HASH:-}
if [ -n "$KSU_NEXT_MANAGER_SIZE" ] || [ -n "$KSU_NEXT_MANAGER_HASH" ]; then
  case $KSU_NEXT_MANAGER_SIZE in
    0x[0-9a-fA-F]*) ;;
    *) echo "::error::KSU_NEXT_MANAGER_SIZE must look like 0x3e6 and be set together with the hash" >&2; exit 1 ;;
  esac
  case $KSU_NEXT_MANAGER_HASH in
    ''|*[!0-9a-f]*) echo "::error::KSU_NEXT_MANAGER_HASH must be 64 lowercase hex characters" >&2; exit 1 ;;
  esac
  if [ "${#KSU_NEXT_MANAGER_HASH}" -ne 64 ]; then
    echo "::error::KSU_NEXT_MANAGER_HASH must be 64 lowercase hex characters" >&2
    exit 1
  fi
  export KSU_NEXT_MANAGER_SIZE KSU_NEXT_MANAGER_HASH
  echo "Manager signature: custom (size $KSU_NEXT_MANAGER_SIZE)"
else
  unset KSU_NEXT_MANAGER_SIZE KSU_NEXT_MANAGER_HASH
  echo "Manager signature: official KernelSU-Next key (default)"
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
  for p in $(find "$ROOT/patches/kernel" -maxdepth 1 -type f -name '*.patch' | sort); do
    apply_one "$p"
  done
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
  echo "Manager signature size: ${KSU_NEXT_MANAGER_SIZE:-default (official key)}"
  echo "Manager signature hash: ${KSU_NEXT_MANAGER_HASH:-default (official key)}"
} > "$OUT/manager-signature.txt"
cat "$OUT/manager-signature.txt"

set -- \
  "$ROOT/arch/arm64/configs/mt6768_slm_defconfig" \
  "$ROOT/arch/arm64/configs/a32.config" \
  "$ROOT/arch/arm64/configs/battery.config" \
  "$ROOT/arch/arm64/configs/ksu-a325n-common.config" \
  "$ROOT/arch/arm64/configs/a325n-release.config"
"$ROOT/scripts/kconfig/merge_config.sh" -m -O "$OUT" "$@"

make -C "$ROOT" O="$OUT" olddefconfig
# The embedded preinit runner uses these target headers. Install them before
# Kbuild evaluates its code generators, including on a fresh output directory.
make -C "$ROOT" O="$OUT" headers_install INSTALL_HDR_PATH="$OUT/usr"
make -C "$ROOT" O="$OUT" -j"$JOBS"
