#!/usr/bin/env bash
# Builds the KernelSU-Next manager APK (arm64-v8a, release, signed) from a KernelSU-Next checkout.
# Used by build-ksun-manager.yml and build-ksun-manager-selfhosted.yml.
#
# Required env: SRC (KernelSU-Next checkout), OUT (output dir), ANDROID_NDK_HOME.
# Optional env: SPOOFED=true, RUST_TOOLCHAIN (default stable), CARGO_TARGET_DIR, CARGO_HOME,
#   KEYSTORE_B64 / KEYSTORE_PASSWORD_IN / KEY_ALIAS_IN / KEY_PASSWORD_IN (signing key).
set -euo pipefail

SRC="${SRC:?SRC (KernelSU-Next checkout) is required}"
OUT="${OUT:?OUT (output directory) is required}"
SPOOFED="${SPOOFED:-false}"
RUST_TOOLCHAIN="${RUST_TOOLCHAIN:-stable}"
NDK="${ANDROID_NDK_HOME:?ANDROID_NDK_HOME is required}"
RUST_TARGET=aarch64-linux-android
LLVM_BIN="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin"
SYSROOT="$NDK/toolchains/llvm/prebuilt/linux-x86_64/sysroot"
TARGET_ROOT="${CARGO_TARGET_DIR:-$SRC/.cargo-target}"
WORK="${RUNNER_TEMP:-/tmp}"
mkdir -p "$OUT" "$TARGET_ROOT"
export PATH="${CARGO_HOME:-$HOME/.cargo}/bin:$PATH"

if ! command -v rustup >/dev/null; then
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain none
fi
rustup toolchain install "$RUST_TOOLCHAIN" --profile minimal
rustup default "$RUST_TOOLCHAIN"
rustup target add "$RUST_TARGET"
command -v cargo-ndk >/dev/null || cargo install cargo-ndk --locked

test -d "$SRC/userspace/ksud" || { echo "::error::$SRC/userspace/ksud not found. Pick a ksun_ref that contains the manager (for example dev); the legacy branch has no manager."; exit 1; }
test -d "$SRC/manager" || { echo "::error::$SRC/manager not found."; exit 1; }

echo "== ksuinit (aarch64) =="
(
  cd "$SRC/userspace/ksuinit"
  export CARGO_TARGET_DIR="$TARGET_ROOT/ksuinit"
  clang_path="$LLVM_BIN/aarch64-linux-android26-clang"
  export CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER="$clang_path"
  builtins="$("$clang_path" --print-resource-dir)/lib/linux/libclang_rt.builtins-aarch64-android.a"
  test -f "$builtins"
  export RUSTFLAGS="-C target-feature=+crt-static -C link-arg=-Wl,-z,max-page-size=16384 -C link-arg=-Wno-unused-command-line-argument -C link-arg=$builtins"
  cargo build --target="$RUST_TARGET" --release
)
bin="$SRC/userspace/ksud/bin"
mkdir -p "$bin/aarch64" "$bin/x86_64" "$bin/riscv64"
cp -f "$TARGET_ROOT/ksuinit/$RUST_TARGET/release/ksuinit" "$bin/aarch64/ksuinit"
for d in x86_64 riscv64; do
  [ -e "$bin/$d/ksuinit" ] || : > "$bin/$d/ksuinit"
done

echo "== ksud (aarch64) =="
"$LLVM_BIN/clang" --target=aarch64-linux-gnu -c -nostdlib \
  -o "$SRC/userspace/ksud/.lkm_image_bootstrap.o" \
  "$SRC/userspace/ksud/src/lkm_image_bootstrap.S"
(
  cd "$SRC/userspace/ksud"
  export CARGO_TARGET_DIR="$TARGET_ROOT/ksud"
  export BINDGEN_EXTRA_CLANG_ARGS_aarch64_linux_android="--sysroot=$SYSROOT -I$SYSROOT/usr/include/aarch64-linux-android -I$SYSROOT/usr/include"
  cargo ndk -P 26 -t arm64-v8a build --release
)
ksud_bin="$TARGET_ROOT/ksud/$RUST_TARGET/release/ksud"
test -s "$ksud_bin"

echo "== manager =="
cd "$SRC/manager"
if [ "$SPOOFED" = true ]; then
  chmod +x spoof
  ./spoof
fi
mkdir -p app/src/main/jniLibs/arm64-v8a
cp -f "$ksud_bin" app/src/main/jniLibs/arm64-v8a/libksud.so

ks="$WORK/ksun-sign.jks"
rm -f "$ks"
if [ -n "${KEYSTORE_B64:-}" ]; then
  echo "$KEYSTORE_B64" | base64 -d > "$ks"
  alias_name="${KEY_ALIAS_IN:?KEY_ALIAS secret is required with KEYSTORE}"
  store_pass="${KEYSTORE_PASSWORD_IN:?KEYSTORE_PASSWORD secret is required with KEYSTORE}"
  key_pass="${KEY_PASSWORD_IN:-$store_pass}"
  signing="repository secrets"
else
  store_pass="$(openssl rand -hex 24)"
  key_pass="$store_pass"
  alias_name="ksun-dev"
  keytool -genkeypair -alias "$alias_name" -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass "$store_pass" -keypass "$key_pass" -dname "CN=KernelSU-Next self-built" \
    -storetype JKS -keystore "$ks"
  signing="temporary key (not reusable)"
  echo "::warning::No KEYSTORE secret set: signed with a one-off key. Add KEYSTORE, KEYSTORE_PASSWORD, KEY_ALIAS and KEY_PASSWORD secrets so every build has the same signature."
fi
echo "::add-mask::$store_pass"
echo "::add-mask::$key_pass"
{
  echo
  echo "KEYSTORE_FILE=$ks"
  echo "KEYSTORE_PASSWORD=$store_pass"
  echo "KEY_ALIAS=$alias_name"
  echo "KEY_PASSWORD=$key_pass"
} >> gradle.properties

commit="$(git -C "$SRC" rev-parse HEAD)"
describe="$(git -C "$SRC" describe --tags --always)"
./gradlew clean assembleRelease --build-cache

apk_dir=app/build/outputs/apk/release
test -n "$(find "$apk_dir" -maxdepth 1 -name '*.apk' -print -quit)"
cp -f "$apk_dir"/*.apk "$OUT/"

keytool -exportcert -alias "$alias_name" -keystore "$ks" -storepass "$store_pass" -file "$WORK/ksun-cert.der"
size_hex="$(printf '0x%x' "$(stat -c%s "$WORK/ksun-cert.der")")"
hash="$(sha256sum "$WORK/ksun-cert.der" | awk '{print $1}')"

{
  echo "KernelSU-Next commit: $commit"
  echo "KernelSU-Next describe: $describe"
  echo "Spoofed package: $SPOOFED"
  echo "Signing: $signing"
  echo "KSU_NEXT_MANAGER_SIZE=$size_hex"
  echo "KSU_NEXT_MANAGER_HASH=$hash"
  echo "Rust toolchain: $(rustc --version)"
} > "$OUT/build-info.txt"
cat "$OUT/build-info.txt"

if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    echo "### KernelSU-Next manager (release, arm64-v8a)"
    echo
    echo "| Item | Value |"
    echo "|---|---|"
    echo "| KernelSU-Next | \`$describe\` (\`${commit:0:8}\`) |"
    echo "| Spoofed package | $SPOOFED |"
    echo "| Signing | $signing |"
    echo "| KSU_NEXT_MANAGER_SIZE | \`$size_hex\` |"
    echo "| KSU_NEXT_MANAGER_HASH | \`$hash\` |"
    echo
    echo "The kernel only crowns an APK as manager when its signing certificate matches these two values. The kernel defaults to the official KernelSU-Next key, so a kernel built for this APK must be given these values."
  } >> "$GITHUB_STEP_SUMMARY"
fi
