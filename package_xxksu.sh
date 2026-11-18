#!/bin/sh
set -eu
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
: "${OUT_DIR:?OUT_DIR is required}"
: "${PACKAGE_DIR:?PACKAGE_DIR is required}"
: "${RUNNER_TEMP:?RUNNER_TEMP is required}"
: "${TOOLCHAIN:?TOOLCHAIN is required}"
case "$PACKAGE_DIR" in /*) ;; *) echo 'PACKAGE_DIR must be absolute' >&2; exit 1 ;; esac
IMAGE="$OUT_DIR/arch/arm64/boot/Image"
test -s "$IMAGE"
test -s "$OUT_DIR/vmlinux"
for disabled in CONFIG_KSU_LSM_SECURITY_HOOKS CONFIG_KSU_HACK_ARM64_BRANCH_LINK CONFIG_KSU_TAMPER_SYSCALL_TABLE; do
  if grep -q "^$disabled=" "$OUT_DIR/.config"; then
    echo "Automated hook mode unexpectedly enabled: $disabled" >&2; exit 1
  fi
done
for option in CONFIG_KSU CONFIG_KSU_SUSFS CONFIG_XXKSU_MANUAL_HOOKS; do
  grep -qx "$option=y" "$OUT_DIR/.config"
done
"$TOOLCHAIN/bin/llvm-nm" --defined-only "$OUT_DIR/vmlinux" > "$OUT_DIR/xxksu-symbols.txt"
for symbol in xxksu_parent_sucompat_enabled xxksu_parent_uid_allowed xxksu_parent_reset_task xxksu_parent_deny_task xxksu_parent_finish_umount xxksu_parent_post_fs_data xxksu_parent_packages_changed ksu_handle_newfstat_ret ksu_handle_fstat64_ret susfs_set_priority_uid_filter susfs_is_priority_uid_filtered susfs_set_sus_path_uid_filter; do
  grep -Eq "[[:space:]]$symbol$" "$OUT_DIR/xxksu-symbols.txt" || {
    echo "Missing linked xxKSU/SUSFS symbol: $symbol" >&2; exit 1;
  }
done
AK3_REPO=https://github.com/osm0sis/AnyKernel3.git
AK3_COMMIT=af770f7b16cf8f8eb7c68614b2a693b3b361c90c
work=$(mktemp -d "$RUNNER_TEMP/xxksu-package.XXXXXX")
trap 'rm -rf -- "$work"' 0 1 2 3 15
ak3="$work/AnyKernel3"
git init -q "$ak3"
git -C "$ak3" fetch --depth=1 "$AK3_REPO" "$AK3_COMMIT"
git -C "$ak3" checkout --detach FETCH_HEAD
test "$(git -C "$ak3" rev-parse HEAD)" = "$AK3_COMMIT"
config="$ROOT/anykernel/a325n-anykernel.sh"
grep -q '^device\.name1=a32$' "$config"
grep -Eq '^BLOCK=/dev/block/by-name/boot;?$' "$config"
rm -rf -- "$ak3/.git" "$ak3/.github"
rm -f "$ak3"/Image* "$ak3"/zImage*
cp "$config" "$ak3/anykernel.sh"
short=$(git -C "$ROOT" rev-parse --short=10 HEAD)
susfs=$(sed -n 's/^#define SUSFS_VERSION "\([^"]*\)"/\1/p' "$ROOT/include/linux/susfs.h" | head -n1)
test -n "$susfs"
sed -i "s|^kernel\.string=.*|kernel.string=A325X xxKSU SUSFS $susfs $short|" "$ak3/anykernel.sh"
cp "$IMAGE" "$ak3/Image"
gzip -n -c "$IMAGE" > "$ak3/Image.gz"
gzip -t "$ak3/Image.gz"
mkdir -p "$PACKAGE_DIR"
zip_path="$PACKAGE_DIR/A325X-xxKSU-SUSFS-$susfs-$short.zip"
rm -f "$zip_path"
(cd "$ak3" && zip -qr "$zip_path" . -x '.git/*' '.github/*' '*.zip' '*~' '*.bak')
unzip -tq "$zip_path"
unzip -p "$zip_path" Image > "$work/Image"
cmp "$IMAGE" "$work/Image"
unzip -p "$zip_path" Image.gz | gzip -dc > "$work/Image-uncompressed"
cmp "$IMAGE" "$work/Image-uncompressed"
unzip -p "$zip_path" anykernel.sh > "$work/anykernel.sh"
grep -q '^kernel.string=A325X xxKSU SUSFS ' "$work/anykernel.sh"
grep -q '^device\.name1=a32$' "$work/anykernel.sh"
grep -Eq '^BLOCK=/dev/block/by-name/boot;?$' "$work/anykernel.sh"
cp "$OUT_DIR/xxksu-source.json" "$OUT_DIR/toolchain-source.txt" "$PACKAGE_DIR/"
{
  echo "Kernel source: $(git -C "$ROOT" rev-parse HEAD)"
  echo "KernelSU source: $(git -C "$ROOT/KernelSU" rev-parse HEAD)"
  echo "SUSFS: $susfs (Jack source $(python3 -c "import json;print(json.load(open('$ROOT/sources.json'))['susfs']['commit'])"))"
  echo "Kernel release: $(cat "$OUT_DIR/include/config/kernel.release")"
  echo "AnyKernel3: $AK3_REPO@$AK3_COMMIT"
} > "$PACKAGE_DIR/build-info.txt"
(cd "$PACKAGE_DIR" && sha256sum ./*.zip > SHA256SUMS.txt)
echo "Created xxKSU package: $zip_path"
