#!/usr/bin/env bash
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
source_file="${1:-frame.asm}"
tmpdir="$(mktemp -d)"
trap 'rm -rf -- "$tmpdir"' EXIT

cd "$root"
python3 scripts/assembly_policy.py "$source_file"
nasm -f elf64 -Werror -Wno-unknown-warning "$source_file" -o "$tmpdir/frame.o"

echo "Assembly syntax and policy passed"
