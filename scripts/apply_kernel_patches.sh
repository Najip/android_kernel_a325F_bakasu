#!/bin/sh
# Apply parent-kernel compatibility patches required by the selected BakaSU
# revision. BakaSU itself must remain an unmodified upstream checkout.
set -eu

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
KSU="$ROOT/KernelSU"
PATCH_DIR="$ROOT/patches/kernel"
PATCH="$PATCH_DIR/0001-susfs-add-bakasu-sync-up-priority-adapter.patch"

needs_adapter=false
if grep -q 'susfs_parse_priority_app_strings' \
	"$KSU/kernel/supercall/dispatch.c" \
	"$KSU/kernel/manager/pkg_observer.c" 2>/dev/null; then
	needs_adapter=true
fi

if [ "$needs_adapter" = false ]; then
	echo 'BakaSU does not require the parent priority UID refresh adapter.'
	exit 0
fi

if [ ! -s "$PATCH" ]; then
	echo "Missing required kernel patch: $PATCH" >&2
	exit 1
fi

# Reject a dirty kernel tree so a failed or repeated patch run cannot hide
# local edits. CI checkouts are clean by definition.
if [ -n "$(git -C "$ROOT" status --porcelain --untracked-files=normal)" ]; then
	echo 'Kernel worktree is dirty; commit or stash local changes before applying patches' >&2
	exit 1
fi

git -C "$ROOT" apply --check "$PATCH"
git -C "$ROOT" apply "$PATCH"

echo "Applied kernel patch: $(basename "$PATCH")"
