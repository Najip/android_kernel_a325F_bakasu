#!/bin/sh
# Hook for build-fgetpriority-lkm.yml: the workflow runs this file, when present,
# right after it checks out kernel_ref. It lets that workflow build the module
# against this branch, which has no fgetpriority submodule or prepare script.
#   1. applies patches/kernel/*.patch, like build_a325n_ksun.sh;
#   2. takes scripts/prepare_fgetpriority.sh and patches/fgetpriority/*.patch from
#      FGP_TOOLING_REF (default nomount-lkm-sync-up-patch);
#   3. clones fgetpriority at the commit FGP_TOOLING_REF pins.
set -eu

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
TOOLING_REF=${FGP_TOOLING_REF:-nomount-lkm-sync-up-patch}
FGP_URL=${FGP_URL:-https://github.com/aerath-stuff/fgetpriority.git}

if [ -d patches/kernel ]; then
  for p in $(find patches/kernel -maxdepth 1 -type f -name '*.patch' | sort); do
    if git apply --check --reverse "$p" >/dev/null 2>&1; then
      echo "Kernel patch already applied: $(basename "$p")"
    else
      git apply --check "$p" || {
        echo "Kernel patch does not apply: $(basename "$p")" >&2
        exit 1
      }
      git apply "$p"
      echo "Applied kernel patch: $(basename "$p")"
    fi
  done
fi

git fetch --no-tags --depth=1 origin "$TOOLING_REF"

if [ ! -f scripts/prepare_fgetpriority.sh ]; then
  git show FETCH_HEAD:scripts/prepare_fgetpriority.sh > scripts/prepare_fgetpriority.sh
fi
test -s scripts/prepare_fgetpriority.sh

mkdir -p patches/fgetpriority
for f in $(git ls-tree -r --name-only FETCH_HEAD -- patches/fgetpriority | grep '\.patch$' || true); do
  git show "FETCH_HEAD:$f" > "$f"
  echo "Copied $f"
done

if [ ! -e fgetpriority/.git ]; then
  sha=$(git ls-tree FETCH_HEAD fgetpriority | awk '{print $3}')
  if [ -z "$sha" ]; then
    echo "No fgetpriority commit is pinned on $TOOLING_REF" >&2
    exit 1
  fi
  rm -rf fgetpriority
  git init -q fgetpriority
  git -C fgetpriority fetch -q --depth=1 "$FGP_URL" "$sha"
  git -C fgetpriority checkout -q --detach FETCH_HEAD
  echo "fgetpriority cloned at $sha"
fi
