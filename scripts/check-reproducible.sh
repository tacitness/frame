#!/usr/bin/env bash
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
tmpdir="$(mktemp -d)"
trap 'rm -rf -- "$tmpdir"' EXIT

for build in one two; do
    mkdir -p "$tmpdir/$build"
    cp "$root/Makefile" "$root/VERSION" "$root/frame.asm" "$tmpdir/$build/"
    make --no-print-directory -C "$tmpdir/$build" all >/dev/null
done

if ! cmp -s "$tmpdir/one/frame" "$tmpdir/two/frame"; then
    echo "Reproducibility check failed: clean builds differ" >&2
    sha256sum "$tmpdir/one/frame" "$tmpdir/two/frame" >&2
    exit 1
fi

echo "Reproducible build passed: $(sha256sum "$tmpdir/one/frame" | awk '{print $1}')"
