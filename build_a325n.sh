#!/bin/sh
set -eu

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
# shellcheck source=aosp_clang14.conf
. "$ROOT/scripts/aosp_clang14.conf"
OUT=${OUT_DIR:-"$ROOT/out"}
TOOLCHAIN=${TOOLCHAIN:-"$ROOT/.toolchains/$AOSP_CLANG_DIRECTORY"}
JOBS=${JOBS:-$(nproc)}

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
export KBUILD_BUILD_USER=${KBUILD_BUILD_USER:-bakasu}
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

cp "$TOOLCHAIN/aosp-source.txt" "$OUT/toolchain-source.txt"
"$CC" --version > "$OUT/clang-version.txt"
"$LD" --version > "$OUT/lld-version.txt"
cat "$OUT/clang-version.txt" "$OUT/lld-version.txt" >> "$OUT/toolchain-source.txt"
"$AS" --version >> "$OUT/toolchain-source.txt"

sh "$ROOT/scripts/prepare_bakasu.sh" --apply > "$OUT/bakasu-source.txt"
cat "$OUT/bakasu-source.txt"

"$ROOT/scripts/kconfig/merge_config.sh" -m -O "$OUT" \
  "$ROOT/arch/arm64/configs/mt6768_slm_defconfig" \
  "$ROOT/arch/arm64/configs/a32.config" \
  "$ROOT/arch/arm64/configs/battery.config" \
  "$ROOT/arch/arm64/configs/ksu-a325n-common.config" \
  "$ROOT/arch/arm64/configs/a325n-release.config"

make -C "$ROOT" O="$OUT" olddefconfig
# The embedded preinit runner uses these target headers. Install them before
# Kbuild evaluates its code generators, including on a fresh output directory.
make -C "$ROOT" O="$OUT" headers_install INSTALL_HDR_PATH="$OUT/usr"
make -C "$ROOT" O="$OUT" -j"$JOBS"
