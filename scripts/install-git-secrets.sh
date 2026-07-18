#!/usr/bin/env bash
set -euo pipefail

readonly commit="7d6b970cbd3c216353cb22b383b70c150140662e"
readonly expected="775e3f0d2f2f8e4b5922115f1235f7369805de76f4efc69cb674bcba5590d0fa"
destination="${1:-/usr/local/bin/git-secrets}"
tmpdir="$(mktemp -d)"
trap 'rm -rf -- "$tmpdir"' EXIT

url="https://raw.githubusercontent.com/awslabs/git-secrets/$commit/git-secrets"
curl -fsSL "$url" -o "$tmpdir/git-secrets"
echo "$expected  $tmpdir/git-secrets" | sha256sum -c -
install -m 0755 "$tmpdir/git-secrets" "$destination"
echo "Installed pinned git-secrets $commit to $destination"
