#!/bin/sh
# Apply parent-kernel compatibility patches required by the pinned BakaSU
# revision. This script never modifies the BakaSU submodule.
set -eu

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
KSU="$ROOT/KernelSU"
PATCH_DIR="$ROOT/patches/kernel"
PATCH="$PATCH_DIR/0001-susfs-add-bakasu-sync-up-priority-adapter.patch"

needs_adapter=false
if grep -q 'susfs_parse_priority_app_strings' \
  "$KSU/kernel/supercall/dispatch.c" "$KSU/kernel/manager/pkg_observer.c" 2>/dev/null; then
  needs_adapter=true
fi

if [ "$needs_adapter" = "false" ]; then
  echo 'BakaSU does not require the sync-up priority UID adapter; no kernel patches applied.'
  exit 0
fi

if [ ! -f "$PATCH" ]; then
  echo "Required kernel patch is missing: $PATCH" >&2
  exit 1
fi

# Reject a dirty kernel tree before changing it. CI checkouts are clean;
# local developers must stash or commit unrelated work first.
if [ -n "$(git -C "$ROOT" status --porcelain --untracked-files=normal)" ]; then
  echo 'Kernel worktree is dirty; commit or stash changes before applying patches.' >&2
  exit 1
fi

echo "Checking kernel patch: $(basename "$PATCH")"
git -C "$ROOT" apply --check "$PATCH"
git -C "$ROOT" apply "$PATCH"

echo "Applied kernel patch: $(basename "$PATCH")"
