#!/usr/bin/env bash
set -euo pipefail

binary="${1:-./frame}"
[[ -x "$binary" ]] || { echo "ELF check: not executable: $binary" >&2; exit 1; }

headers="$(readelf -W -h "$binary")"
programs="$(readelf -W -l "$binary")"
sections="$(readelf -W -S "$binary")"

grep -Eq 'Class:[[:space:]]+ELF64' <<<"$headers"
grep -Eq 'Machine:[[:space:]]+Advanced Micro Devices X86-64' <<<"$headers"
grep -Eq 'Type:[[:space:]]+EXEC' <<<"$headers"
grep -Eq 'Entry point address:[[:space:]]+0x[1-9a-fA-F][0-9a-fA-F]*' <<<"$headers"

if grep -Eq 'INTERP|DYNAMIC' <<<"$programs"; then
    echo "ELF check: frame must remain static and interpreter-free" >&2
    exit 1
fi
if readelf -W -r "$binary" | grep -Eq 'R_X86_64_|Relocation section'; then
    echo "ELF check: linked image contains runtime relocations" >&2
    exit 1
fi
if awk '$1 == "LOAD" && $0 ~ /W/ && $0 ~ /E/ { found=1 } END { exit !found }' <<<"$programs"; then
    echo "ELF check: writable/executable LOAD segment found" >&2
    exit 1
fi
stack_line="$(awk '$1 == "GNU_STACK" { print; exit }' <<<"$programs")"
[[ -n "$stack_line" ]] || { echo "ELF check: GNU_STACK declaration missing" >&2; exit 1; }
if grep -Eq 'RWE|E[[:space:]]+0x' <<<"$stack_line"; then
    echo "ELF check: executable stack found" >&2
    exit 1
fi
grep -Eq '\.text[[:space:]].*AX' <<<"$sections"
grep -Eq '\.rodata[[:space:]].*A' <<<"$sections"
grep -Eq '\.bss[[:space:]].*WA' <<<"$sections"
grep -q '.note.gnu.build-id' <<<"$sections"

bss_hex="$(awk '$3 == ".bss" { print $7; exit }' <<<"$sections")"
[[ -n "$bss_hex" ]] || { echo "ELF check: could not measure BSS" >&2; exit 1; }
bss_size=$((16#$bss_hex))
max_bss=$((64 * 1024 * 1024))
if (( bss_size > max_bss )); then
    echo "ELF check: BSS $bss_size exceeds the 64 MiB budget" >&2
    exit 1
fi

echo "ELF contract passed (static, NX stack, W^X, no relocations, BSS=${bss_size} bytes)"
