#!/usr/bin/env bash
set -euo pipefail

version="${1:?version required}"
dist="${2:-dist}"
command -v syft >/dev/null || { echo "SBOM generation requires syft" >&2; exit 1; }
mkdir -p "$dist"
root="$(git rev-parse --show-toplevel)"

syft scan "file:./frame" -q -o "spdx-json=$dist/frame-${version}.spdx.json"
syft scan "file:./frame" -q -o "cyclonedx-json=$dist/frame-${version}.cdx.json"
"$root/scripts/update-checksums.sh" "$dist" \
    "frame-${version}.spdx.json" "frame-${version}.cdx.json"

echo "Generated SPDX and CycloneDX SBOMs in $dist"
