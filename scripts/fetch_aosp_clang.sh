#!/bin/sh
set -eu

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
# shellcheck source=aosp_clang14.conf
. "$ROOT/scripts/aosp_clang14.conf"
destination=${1:-"$ROOT/.toolchains/$AOSP_CLANG_DIRECTORY"}
archive_url="$AOSP_CLANG_REPOSITORY/+archive/$AOSP_CLANG_REVISION/$AOSP_CLANG_DIRECTORY.tar.gz"

verify_installation() {
  installation=$1
  for binary in clang clang++ ld.lld llvm-ar llvm-nm llvm-objcopy llvm-objdump llvm-readelf llvm-strip; do
    test -x "$installation/bin/$binary" || return 1
  done
  test -s "$installation/lib64/clang/$AOSP_CLANG_VERSION/include/stdarg.h" || return 1
  grep -qxF "AOSP Clang revision: $AOSP_CLANG_REVISION" "$installation/aosp-source.txt" || return 1
  grep -qxF "AOSP Clang directory: $AOSP_CLANG_DIRECTORY" "$installation/aosp-source.txt" || return 1
  grep -qxF "AOSP Clang version: $AOSP_CLANG_VERSION" "$installation/aosp-source.txt" || return 1
  grep -qxF "AOSP Clang tree: $AOSP_CLANG_TREE" "$installation/aosp-source.txt" || return 1
}

if [ -e "$destination" ] || [ -L "$destination" ]; then
  verify_installation "$destination" || {
    echo "Existing toolchain is not the pinned AOSP installation: $destination" >&2
    exit 1
  }
  cat "$destination/aosp-source.txt"
  exit 0
fi

cache=${AOSP_CLANG_CACHE:-"${XDG_CACHE_HOME:-$HOME/.cache}/bakasu-toolchains"}
mkdir -p "$cache"
archive=${AOSP_CLANG_ARCHIVE:-"$cache/$AOSP_CLANG_DIRECTORY-$AOSP_CLANG_REVISION.tar.gz"}
stage=
temporary_archive=
validation_git=
cleanup() {
  if [ -n "$temporary_archive" ]; then rm -f -- "$temporary_archive"; fi
  if [ -n "$validation_git" ]; then rm -rf -- "$validation_git"; fi
  if [ -n "$stage" ]; then rm -rf -- "$stage"; fi
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

private_git() {
  GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_ATTR_NOSYSTEM=1 \
    git -c core.attributesFile=/dev/null -c core.autocrlf=false \
    -c core.filemode=true -c core.compression=1 "$@"
}

source_archive=$archive
if [ ! -f "$archive" ]; then
  if [ -n "${AOSP_CLANG_ARCHIVE:-}" ]; then
    echo "Specified AOSP archive does not exist: $archive" >&2
    exit 1
  fi
  temporary_archive=$(mktemp "$cache/.aosp-download.XXXXXX")
  curl --fail --location --retry 5 --retry-delay 2 --retry-all-errors \
    --connect-timeout 30 --max-time 1200 "$archive_url" -o "$temporary_archive"
  source_archive=$temporary_archive
fi

actual_archive_sha256=$(sha256sum "$source_archive" | cut -d ' ' -f 1)
parent=$(dirname -- "$destination")
mkdir -p "$parent"
stage=$(mktemp -d "$parent/.aosp-install.XXXXXX")
tar --no-same-owner -xzf "$source_archive" -C "$stage"
# Reconstruct the official Git subtree before executing any downloaded binary.
# This verifies all bytes, paths, symlink targets and executable bits while
# ignoring the non-reproducible timestamps in Gitiles archive headers.
validation_git=$(mktemp -d "$parent/.aosp-tree.XXXXXX")
private_git init --bare --quiet --object-format=sha1 --initial-branch=verify "$validation_git"
private_git --git-dir="$validation_git" --work-tree="$stage" add --all --force
actual_tree=$(private_git --git-dir="$validation_git" write-tree)
test "$actual_tree" = "$AOSP_CLANG_TREE" || {
  echo "AOSP toolchain content mismatch: expected $AOSP_CLANG_TREE, got $actual_tree" >&2
  exit 1
}
rm -rf -- "$validation_git"
validation_git=
cat > "$stage/aosp-source.txt" <<EOF
AOSP Clang repository: $AOSP_CLANG_REPOSITORY
AOSP Clang revision: $AOSP_CLANG_REVISION
AOSP Clang directory: $AOSP_CLANG_DIRECTORY
AOSP Clang version: $AOSP_CLANG_VERSION
AOSP Clang tree: $AOSP_CLANG_TREE
AOSP Clang archive SHA256: $actual_archive_sha256
EOF
verify_installation "$stage" || {
  echo "AOSP archive is missing required compiler tools or resource headers" >&2
  exit 1
}
# Verify that the included runtime works without a host libxml2 override.
env -u LD_LIBRARY_PATH "$stage/bin/clang" --version > "$stage/clang-version.txt"
env -u LD_LIBRARY_PATH "$stage/bin/ld.lld" --version > "$stage/lld-version.txt"
grep -qF "based on r450784d" "$stage/clang-version.txt"
if [ -n "$temporary_archive" ]; then
  mv "$temporary_archive" "$archive"
  temporary_archive=
fi
mv -T "$stage" "$destination"
stage=
cat "$destination/aosp-source.txt"
