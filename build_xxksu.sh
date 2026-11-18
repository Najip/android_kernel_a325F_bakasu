#!/bin/sh
set -eu
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"
# Source preparation must succeed before toolchain setup or compilation.
PREPARATION=$(python3 "$ROOT/scripts/prepare_xxksu.py" --apply)
. "$ROOT/scripts/aosp_clang14.conf"
OUT=${OUT_DIR:-"$ROOT/out-xxksu"}
case "$OUT" in /*) ;; *) OUT="$ROOT/$OUT" ;; esac
TOOLCHAIN=${TOOLCHAIN:-"$ROOT/.toolchains/$AOSP_CLANG_DIRECTORY"}
JOBS=${JOBS:-$(nproc)}
sh "$ROOT/scripts/fetch_aosp_clang.sh" "$TOOLCHAIN"
TOOLCHAIN=$(CDPATH='' cd -- "$TOOLCHAIN" && pwd)
for tool in aarch64-linux-gnu-as aarch64-linux-gnu-elfedit; do
  command -v "$tool" >/dev/null || { echo "Missing $tool" >&2; exit 1; }
done
export ARCH=arm64
export PATH="$TOOLCHAIN/bin:$PATH"
export LD_LIBRARY_PATH="$TOOLCHAIN/lib64:$TOOLCHAIN/lib:${LD_LIBRARY_PATH:-}"
export CC="$TOOLCHAIN/bin/clang" LD="$TOOLCHAIN/bin/ld.lld"
export AR="$TOOLCHAIN/bin/llvm-ar" NM="$TOOLCHAIN/bin/llvm-nm"
export STRIP="$TOOLCHAIN/bin/llvm-strip" OBJCOPY="$TOOLCHAIN/bin/llvm-objcopy"
export OBJDUMP="$TOOLCHAIN/bin/llvm-objdump" READELF="$TOOLCHAIN/bin/llvm-readelf"
export CROSS_COMPILE=aarch64-linux-gnu-
AS=$(command -v aarch64-linux-gnu-as)
export AS LLVM=1 LLVM_IAS=0
export KBUILD_BUILD_USER=${KBUILD_BUILD_USER:-xxksu}
export KBUILD_BUILD_HOST=${KBUILD_BUILD_HOST:-builder}
export KBUILD_BUILD_VERSION=${KBUILD_BUILD_VERSION:-1}
KBUILD_BUILD_TIMESTAMP=${KBUILD_BUILD_TIMESTAMP:-$(git show -s --format=%cD HEAD)}
export KBUILD_BUILD_TIMESTAMP
export KCFLAGS=${KCFLAGS:--Wno-error -Wno-error=incompatible-pointer-types -Wno-error=int-conversion -Wno-error=visibility -Wno-error=fortify-source -Wno-error=pointer-to-int-cast -Wno-error=typedef-redefinition -Wno-error=strict-prototypes -Wno-error=implicit-function-declaration}
mkdir -p "$OUT"
printf '%s\n' "$PREPARATION" > "$OUT/xxksu-source.json"
cp "$TOOLCHAIN/aosp-source.txt" "$OUT/toolchain-source.txt"
"$CC" --version >> "$OUT/toolchain-source.txt"
"$LD" --version >> "$OUT/toolchain-source.txt"
"$AS" --version >> "$OUT/toolchain-source.txt"
sh "$ROOT/scripts/kconfig/merge_config.sh" -m -O "$OUT" \
  "$ROOT/arch/arm64/configs/mt6768_slm_defconfig" \
  "$ROOT/arch/arm64/configs/a32.config" \
  "$ROOT/arch/arm64/configs/battery.config" \
  "$ROOT/arch/arm64/configs/ksu-a325n-common.config" \
  "$ROOT/arch/arm64/configs/a325n-release.config"
make -C "$ROOT" O="$OUT" olddefconfig
for option in CONFIG_KSU CONFIG_KSU_SUSFS CONFIG_KSU_LSM_SECURITY_HOOKS CONFIG_KSU_HACK_ARM64_BRANCH_LINK; do
  grep -qx "$option=y" "$OUT/.config" || { echo "Required option missing: $option" >&2; exit 1; }
done
make -C "$ROOT" O="$OUT" headers_install INSTALL_HDR_PATH="$OUT/usr"
make -C "$ROOT" O="$OUT" -j"$JOBS"
test -s "$OUT/vmlinux"
test -s "$OUT/arch/arm64/boot/Image"
"$READELF" -h "$OUT/vmlinux" > "$OUT/vmlinux-header.txt"
grep -q AArch64 "$OUT/vmlinux-header.txt"
"$NM" --defined-only "$OUT/vmlinux" > "$OUT/xxksu-symbols.txt"
git diff --check
git -C KernelSU diff --check
sha256sum "$OUT/vmlinux" "$OUT/arch/arm64/boot/Image" > "$OUT/SHA256SUMS.txt"
echo 'Compile/link checks passed. Boot, root, SUSFS runtime and LKM remain untested.'
