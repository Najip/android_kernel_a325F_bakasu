#!/bin/sh
# Check the KSUN build output and package it as an AnyKernel3 ZIP.
# Needs OUT_DIR, PACKAGE_DIR, RUNNER_TEMP (any temp folder) and TOOLCHAIN.
set -eu
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
: "${OUT_DIR:?OUT_DIR is required}"
: "${PACKAGE_DIR:?PACKAGE_DIR is required}"
: "${RUNNER_TEMP:?RUNNER_TEMP is required}"
: "${TOOLCHAIN:?TOOLCHAIN is required}"
case "$PACKAGE_DIR" in /*) ;; *) echo 'PACKAGE_DIR must be absolute' >&2; exit 1 ;; esac
IMAGE_DIR="$OUT_DIR/arch/arm64/boot"
test -s "$IMAGE_DIR/Image"
test -s "$IMAGE_DIR/Image.gz"
test -s "$OUT_DIR/vmlinux"

for option in CONFIG_KSU CONFIG_ALWAYS_ENFORCE CONFIG_KSU_SUSFS; do
  grep -qx "$option=y" "$OUT_DIR/.config" || { echo "Required option missing: $option" >&2; exit 1; }
done
"$TOOLCHAIN/bin/llvm-nm" --defined-only "$OUT_DIR/vmlinux" > "$OUT_DIR/symbols.txt"
grep -q ' ksu_' "$OUT_DIR/symbols.txt" || { echo 'No ksu_ symbols: KernelSU-Next was not linked' >&2; exit 1; }
grep -q ' susfs_' "$OUT_DIR/symbols.txt" || { echo 'No susfs_ symbols: SUSFS was not linked' >&2; exit 1; }
if grep -qi 'nomount\|nm_hijack' "$OUT_DIR/symbols.txt"; then
  echo 'NoMount symbols found in vmlinux' >&2; exit 1
fi

AK3_REPO=https://github.com/osm0sis/AnyKernel3.git
AK3_COMMIT=af770f7b16cf8f8eb7c68614b2a693b3b361c90c
work=$(mktemp -d "$RUNNER_TEMP/ksun-package.XXXXXX")
trap 'rm -rf -- "$work"' 0 1 2 3 15
ak3="$work/AnyKernel3"
git init -q "$ak3"
git -C "$ak3" fetch -q --depth=1 "$AK3_REPO" "$AK3_COMMIT"
git -C "$ak3" checkout -q --detach FETCH_HEAD
test "$(git -C "$ak3" rev-parse HEAD)" = "$AK3_COMMIT"
config="$ROOT/anykernel/a325n-anykernel.sh"
grep -q '^device\.name1=a32$' "$config"
grep -Eq '^BLOCK=/dev/block/by-name/boot;?$' "$config"
rm -rf -- "$ak3/.git" "$ak3/.github"
rm -f "$ak3"/Image* "$ak3"/zImage*
cp "$config" "$ak3/anykernel.sh"

KSU="$ROOT/KernelSU"
tag=$(git -C "$KSU" describe --abbrev=0 --tags 2>/dev/null || echo unknown)
ksu_short=$(git -C "$KSU" rev-parse --short=8 HEAD)
short=$(git -C "$ROOT" rev-parse --short=10 HEAD)
susfs=$(sed -n 's/^#define SUSFS_VERSION "\([^"]*\)"/\1/p' "$ROOT/include/linux/susfs.h" | head -n1)
test -n "$susfs"
sed -i "s|^kernel\.string=.*|kernel.string=A325X KSUN $tag($ksu_short) SUSFS ${susfs#v}|" "$ak3/anykernel.sh"
cp "$IMAGE_DIR/Image" "$IMAGE_DIR/Image.gz" "$ak3/"

mkdir -p "$PACKAGE_DIR"
zip_path="$PACKAGE_DIR/A325X-KSUN-$tag-$ksu_short-SUSFS-$susfs-$short.zip"
rm -f "$zip_path"
(cd "$ak3" && zip -qr "$zip_path" . -x '.git/*' '.github/*' '*.zip' '*~' '*.bak')
unzip -tq "$zip_path"
unzip -p "$zip_path" Image > "$work/Image"
cmp "$IMAGE_DIR/Image" "$work/Image"
unzip -p "$zip_path" anykernel.sh > "$work/anykernel.sh"
grep -q '^kernel.string=A325X KSUN ' "$work/anykernel.sh"
grep -q '^device\.name1=a32$' "$work/anykernel.sh"

cp "$OUT_DIR/kernelsu-source.json" "$OUT_DIR/toolchain-source.txt" "$OUT_DIR/applied-patches.txt" "$PACKAGE_DIR/"
{
  echo "Kernel source: $(git -C "$ROOT" rev-parse HEAD)"
  echo "KernelSU-Next: $(git -C "$KSU" rev-parse HEAD) ($(git -C "$KSU" describe --tags --always))"
  echo "SUSFS: $susfs (Jack source $(python3 -c "import json;print(json.load(open('$ROOT/sources.json'))['susfs']['commit'])"))"
  echo "Kernel release: $(cat "$OUT_DIR/include/config/kernel.release")"
  echo "Kernel patches: $(paste -sd, "$OUT_DIR/applied-patches.txt")"
  cat "$OUT_DIR/manager-signature.txt"
  echo "AnyKernel3: $AK3_REPO@$AK3_COMMIT"
} > "$PACKAGE_DIR/build-info.txt"
(cd "$PACKAGE_DIR" && sha256sum ./*.zip > SHA256SUMS.txt)
cat "$PACKAGE_DIR/build-info.txt"
echo "Created KSUN package: $zip_path"
