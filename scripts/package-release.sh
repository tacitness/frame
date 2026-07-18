#!/usr/bin/env bash
set -euo pipefail

version="${1:?version required}"
binary="${2:-./frame}"
dist="${3:-dist}"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Invalid SemVer: $version" >&2; exit 1; }
[[ -x "$binary" ]] || { echo "Missing executable: $binary" >&2; exit 1; }

root="$(git rev-parse --show-toplevel)"
epoch="$(git -C "$root" log -1 --format=%ct 2>/dev/null || date +%s)"
tmpdir="$(mktemp -d)"
trap 'rm -rf -- "$tmpdir"' EXIT
package="frame-${version}-linux-x86_64"
stage="$tmpdir/$package"

mkdir -p "$stage/bin" "$stage/share/doc/frame" "$dist"
install -m 0755 "$binary" "$stage/bin/frame"
install -m 0644 "$root/LICENSE" "$root/README.md" "$stage/share/doc/frame/"
[[ ! -f "$root/SECURITY.md" ]] || install -m 0644 "$root/SECURITY.md" "$stage/share/doc/frame/"

find "$stage" -exec touch -h -d "@$epoch" {} +
tar --sort=name --mtime="@$epoch" --owner=0 --group=0 --numeric-owner \
    -C "$tmpdir" -cf - "$package" | gzip -n >"$dist/$package.tar.gz"
sha256sum "$dist/$package.tar.gz" >"$dist/$package.tar.gz.sha256"
chmod 0644 "$dist/$package.tar.gz" "$dist/$package.tar.gz.sha256"
"$root/scripts/update-checksums.sh" "$dist" "$package.tar.gz"

echo "Packaged $dist/$package.tar.gz"
