#!/bin/sh
# Apply parent-kernel compatibility patches required by the selected BakaSU
# revision. BakaSU itself must remain an unmodified upstream checkout.
set -eu

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
PATCH_DIR="$ROOT/patches/kernel"

if [ ! -d "$PATCH_DIR" ]; then
	echo "Missing kernel patch directory: $PATCH_DIR" >&2
	exit 1
fi

# Reject a dirty kernel tree so a failed or repeated patch run cannot hide
# local edits. CI checkouts are clean by definition.
if [ -n "$(git -C "$ROOT" status --porcelain --untracked-files=normal)" ]; then
	echo 'Kernel worktree is dirty; commit or stash local changes before applying patches' >&2
	exit 1
fi

patches=$(find "$PATCH_DIR" -maxdepth 1 -type f -name '*.patch' | sort)

if [ -z "$patches" ]; then
	echo "No kernel compatibility patches found in $PATCH_DIR."
	exit 0
fi

for patch in $patches; do
	echo "Checking kernel patch: $(basename "$patch")"
	git -C "$ROOT" apply --check "$patch"
	git -C "$ROOT" apply "$patch"
	echo "Applied kernel patch: $(basename "$patch")"
done
