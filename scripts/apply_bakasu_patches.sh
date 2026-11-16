#!/bin/sh
# Apply build-time fixes to a BakaSU checkout without touching our submodule.
# usage: apply_bakasu_patches.sh <bakasu-checkout> <patch-dir>
# A patch that is already fixed upstream is skipped; one that no longer applies fails the build.
set -eu

dst=$1
pdir=$2

if [ ! -d "$pdir" ]; then
	echo "No BakaSU patch directory: $pdir"
	exit 0
fi

for p in $(find "$pdir" -maxdepth 1 -type f -name '*.patch' | sort); do
	if git -C "$dst" apply --check "$p" 2>/dev/null; then
		git -C "$dst" apply "$p"
		echo "Applied BakaSU patch: $(basename "$p")"
	elif git -C "$dst" apply --check -R "$p" 2>/dev/null; then
		echo "Already fixed upstream, skipped: $(basename "$p")"
	else
		echo "::error::$(basename "$p") no longer applies to this BakaSU revision" >&2
		exit 1
	fi
done
