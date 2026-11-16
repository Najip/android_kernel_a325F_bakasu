#!/bin/sh
# Validate the unmodified fgetpriority submodule and its kernel compatibility
# patches. With --export DEST, write a patched copy of the module source to DEST.
set -eu

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
FGP="$ROOT/fgetpriority"
PATCH_DIR="$ROOT/patches/fgetpriority"

usage() { echo "Usage: $0 --check | --export DEST" >&2; exit 2; }
mode=${1:---check}
case "$mode" in
  --check) ;;
  --export) [ $# -eq 2 ] || usage ;;
  *) usage ;;
esac

[ -e "$FGP/.git" ] || {
  echo "fgetpriority submodule is missing; run the 'Update fgetpriority' workflow or: git submodule update --init fgetpriority" >&2
  exit 1
}
git -C "$FGP" rev-parse --verify HEAD >/dev/null
if [ -n "$(git -C "$FGP" status --porcelain --untracked-files=normal)" ]; then
  echo "fgetpriority must match its upstream commit; preserve local edits first" >&2
  exit 1
fi

for f in kernel/Makefile kernel/main.c kernel/kernel.h kernel/routine.h; do
  test -s "$FGP/$f" || { echo "Upstream layout changed: missing $f" >&2; exit 1; }
done
grep -q 'obj-\$(CONFIG_FGETPRIORITY)' "$FGP/kernel/Makefile" || {
  echo "Upstream Makefile no longer exposes CONFIG_FGETPRIORITY; review the builder" >&2
  exit 1
}

if [ "$mode" = "--check" ]; then
  DEST=$(mktemp -d)
  trap 'rm -rf "$DEST"' EXIT
else
  DEST=$2
  rm -rf "$DEST"
  mkdir -p "$DEST"
fi

git -C "$FGP" archive HEAD | tar -x -C "$DEST"

n=0
for patch in $(find "$PATCH_DIR" -maxdepth 1 -type f -name '*.patch' 2>/dev/null | sort); do
  echo "Applying fgetpriority patch: $(basename "$patch")"
  (cd "$DEST" && git apply --check "$patch" && git apply "$patch") || {
    echo "Patch $(basename "$patch") does not apply to this fgetpriority revision" >&2
    exit 1
  }
  n=$((n + 1))
done

printf 'fgetpriority upstream: %s\n' "$(git -C "$FGP" rev-parse HEAD)"
printf 'fgetpriority worktree: clean\n'
printf 'fgetpriority patches applied: %s\n' "$n"
