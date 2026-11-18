#!/bin/sh
# Split network patch is mandatory; tuning is opt-in.
set -eu
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
PATCH_DIR="$ROOT/patches/kernel"
test -d "$PATCH_DIR"
if [ -n "$(git -C "$ROOT" status --porcelain --untracked-files=normal)" ]; then
  echo 'Kernel worktree is dirty; commit or stash local changes before applying patches' >&2
  exit 1
fi
NO_PERF_TUNING=${NO_PERF_TUNING:-1}
case $NO_PERF_TUNING in 0|1) ;; *) echo 'NO_PERF_TUNING must be 0 or 1' >&2; exit 1;; esac
network=0003-net-udp-gso-qdisc-juan.patch
combined=0003-wifi-fix-perf-1100mhz-1035mv_uv75_zstd_usbnoauto-juan.patch
restore=0006-restore-original-gpu-voltages.patch
test -s "$PATCH_DIR/$network"
test -s "$PATCH_DIR/$restore"
if [ -n "${APPLIED_PATCHES_FILE:-}" ]; then : > "$APPLIED_PATCHES_FILE"; fi
apply_one() {
  git -C "$ROOT" apply --check "$1"
  git -C "$ROOT" apply "$1"
  echo "Applied kernel patch: $(basename "$1")"
  if [ -n "${APPLIED_PATCHES_FILE:-}" ]; then basename "$1" >> "$APPLIED_PATCHES_FILE"; fi
}
for patch in $(find "$PATCH_DIR" -maxdepth 1 -type f -name '*.patch' | sort); do
  name=$(basename "$patch")
  case $name in
    "$combined") echo "Skipping superseded combined patch: $name"; continue;;
    "$restore") continue;;
    *-tuning-*)
      if [ "$NO_PERF_TUNING" = 1 ]; then echo "Skipping optional tuning: $name"; continue; fi;;
  esac
  apply_one "$patch"
done
# Restoration must follow tuning, including when both have the 0006 prefix.
apply_one "$PATCH_DIR/$restore"
