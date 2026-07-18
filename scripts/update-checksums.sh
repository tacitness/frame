#!/usr/bin/env bash
set -euo pipefail

dist="${1:?distribution directory required}"
shift
(( $# > 0 )) || { echo "at least one artifact name is required" >&2; exit 1; }
mkdir -p -- "$dist"

checksum_file="$dist/SHA256SUMS"
tmp="$(mktemp "$dist/.SHA256SUMS.XXXXXX")"
trap 'rm -f -- "$tmp" "${tmp}.filtered"' EXIT
if [[ -f "$checksum_file" ]]; then
    cp -- "$checksum_file" "$tmp"
fi

for name in "$@"; do
    [[ "$name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || {
        echo "invalid artifact name: $name" >&2
        exit 1
    }
    [[ -f "$dist/$name" ]] || { echo "missing artifact: $dist/$name" >&2; exit 1; }
    awk -v target="$name" '$2 != target' "$tmp" >"${tmp}.filtered"
    mv -- "${tmp}.filtered" "$tmp"
    (cd "$dist" && sha256sum "$name") >>"$tmp"
done

sort -k2,2 -o "$tmp" "$tmp"
chmod 0644 "$tmp"
mv -- "$tmp" "$checksum_file"
trap - EXIT
