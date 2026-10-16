#!/usr/bin/env bash
# Internal release acceptance only; host deploy.py/run.py are not changed.
set -euo pipefail
payload="$VINS_REMOTE_PAYLOAD"
archive=install-ros1-v0.2-linux-aarch64.tar.gz
(cd "$payload" && sha256sum -c "$archive.sha256")
release="$VINS_REMOTE_WORKSPACE/releases/ros1-v0.2"
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
cd "$VINS_REMOTE_CWD"
/usr/bin/python3 -I "$payload/verify_runner.py" "$install" "$VINS_REMOTE_ROOT/logs" "$VINS_REMOTE_CWD/data/euroc/MH_01_easy.bag"
# The fault injection above restores the exact file bytes; verify before select.
"$install/bin/check" --sha --json "$VINS_REMOTE_ROOT/logs/final-sha.json"
link="$VINS_REMOTE_WORKSPACE/install"
if test -e "$link" && ! test -L "$link"; then echo "Refusing real install directory: $link" >&2; exit 2; fi
next="$VINS_REMOTE_WORKSPACE/.install-v02-accept"
ln -s "$install" "$next"
mv -Tf "$next" "$link"
printf '%s\n' "$install" > "$VINS_REMOTE_ROOT/logs/selected-install.txt"
vins_event V02_ACCEPTED 'Package/checks/lifecycle accepted; original VINS shutdown -6 remains documented'
