#!/usr/bin/env bash
# Internal release acceptance only; host deploy.py/run.py are not changed.
set -euo pipefail
payload="$VINS_REMOTE_PAYLOAD"
version=v0.2
expected=-6
if test -f "$payload/version.txt"; then version=$(cat "$payload/version.txt"); fi
if test -f "$payload/expected-vins-exit.txt"; then expected=$(cat "$payload/expected-vins-exit.txt"); fi
[[ "$version" =~ ^v[0-9]+\.[0-9]+(\.[0-9]+)?$ ]] || exit 2
[[ "$expected" = 0 || "$expected" = -6 ]] || exit 2
archive="install-ros1-$version-linux-aarch64.tar.gz"
(cd "$payload" && sha256sum -c "$archive.sha256")
release="$VINS_REMOTE_WORKSPACE/releases/ros1-$version"
mkdir -p "$release"
test ! -e "$release/install" || { echo "Refusing existing release: $release/install" >&2; exit 2; }
stage=$(mktemp -d "$release/.accept-XXXXXX")
trap 'rm -rf -- "$stage"' EXIT
tar -xzf "$payload/$archive" -C "$stage" 2>"$VINS_REMOTE_ROOT/logs/unpack.stderr"
mv -T -n "$stage/install" "$release/install"
test ! -e "$stage/install"
install="$release/install"
"$install/bin/check" --arc --lib --sha --dir --output "$VINS_REMOTE_ROOT/logs/next-run" --json "$VINS_REMOTE_ROOT/logs/package-check.json"
"$install/bin/check" --config --bag "$VINS_REMOTE_CWD/data/euroc/MH_01_easy.bag" --output "$VINS_REMOTE_ROOT/logs/next-run" --json "$VINS_REMOTE_ROOT/logs/bag-check.json"
"$install/bin/vins" check "$VINS_REMOTE_ROOT/logs/lifecycle"
/usr/bin/python3 -I - "$VINS_REMOTE_ROOT/logs/lifecycle/logs/validation.json" "$expected" <<'PY_CHECK'
import json,sys
result=json.load(open(sys.argv[1]));assert result['vins_exit_code']==int(sys.argv[2]),result
PY_CHECK
cd "$VINS_REMOTE_CWD"
/usr/bin/python3 -I "$payload/verify_runner.py" "$install" "$VINS_REMOTE_ROOT/logs" "$VINS_REMOTE_CWD/data/euroc/MH_01_easy.bag" --expect-vins-exit "$expected"
# The fault injection above restores the exact file bytes; verify before select.
"$install/bin/check" --sha --json "$VINS_REMOTE_ROOT/logs/final-sha.json"
link="$VINS_REMOTE_WORKSPACE/install"
if test -e "$link" && ! test -L "$link"; then echo "Refusing real install directory: $link" >&2; exit 2; fi
next="$VINS_REMOTE_WORKSPACE/.install-$version-accept"
ln -s "$install" "$next"
mv -Tf "$next" "$link"
printf '%s\n' "$install" > "$VINS_REMOTE_ROOT/logs/selected-install.txt"
vins_event PACKAGE_ACCEPTED "Version $version accepted; expected VINS shutdown $expected verified"
