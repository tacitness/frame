#!/usr/bin/env bash
set -euo pipefail

mode="${1:-hosted}"
tools=(bash git git-secrets make nasm ld python3 shellcheck yamllint actionlint)

case "$mode" in
    hosted) ;;
    self-hosted)
        tools+=(gitleaks trivy syft grype)
        ;;
    sonarqube)
        tools+=(sonar-scanner)
        ;;
    release)
        tools+=(gitleaks trivy syft grype buildah sonar-scanner)
        ;;
    *)
        echo "Unknown toolchain mode: $mode" >&2
        exit 1
        ;;
esac

missing=()
for tool in "${tools[@]}"; do
    command -v "$tool" >/dev/null 2>&1 || missing+=("$tool")
done
if ((${#missing[@]})); then
    printf 'Runner image is missing required tools: %s\n' "${missing[*]}" >&2
    exit 1
fi

nasm_version="$(nasm -v | awk '{print $3}')"
if [[ ! "$nasm_version" =~ ^2\.(1[6-9]|[2-9][0-9])([.]|$) ]]; then
    echo "NASM 2.16 or newer is required; found $nasm_version" >&2
    exit 1
fi

echo "Toolchain contract passed for $mode"
