#!/usr/bin/env bash
set -euo pipefail

binary="${1:-./frame}"
root="$(git rev-parse --show-toplevel)"
tmpdir="$(mktemp -d)"
trap 'rm -rf -- "$tmpdir"' EXIT
cd "$root"

for tool in trivy syft grype; do
    command -v "$tool" >/dev/null || { echo "Security scan requires $tool" >&2; exit 1; }
done

trivy fs --quiet --exit-code 1 --severity HIGH,CRITICAL \
    --scanners vuln,secret,misconfig --skip-dirs .git .
syft scan "dir:." -q -o "cyclonedx-json=$tmpdir/frame.cdx.json"
grype "sbom:$tmpdir/frame.cdx.json" --fail-on high --only-fixed
trivy rootfs --quiet --exit-code 1 --severity HIGH,CRITICAL \
    --scanners vuln "$binary"

echo "Extended security scans passed"
