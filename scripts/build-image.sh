#!/usr/bin/env bash
set -euo pipefail

version="${1:?version required}"
binary="${2:-./frame}"
dist="${3:-}"
image="ghcr.io/tacitness/frame:${version}"
root="$(git rev-parse --show-toplevel)"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Invalid SemVer: $version" >&2; exit 1; }
[[ -x "$binary" ]] || { echo "Missing executable: $binary" >&2; exit 1; }
binary_path="$(readlink -f "$binary")"
[[ "$binary_path" == "$root/frame" ]] || {
    echo "Image builds require the repository binary at $root/frame" >&2
    exit 1
}
revision="$(git -C "$root" rev-parse 'HEAD^{commit}')"
created_epoch="$(git -C "$root" log -1 --format=%ct)"
created="$(date -u -d "@$created_epoch" +%Y-%m-%dT%H:%M:%SZ)"
binary_sha256="$(sha256sum "$binary_path" | awk '{print $1}')"
source_state=clean
if ! git -C "$root" diff --quiet --ignore-submodules -- ||
    ! git -C "$root" diff --cached --quiet --ignore-submodules -- ||
    [[ -n "$(git -C "$root" ls-files --others --exclude-standard)" ]]; then
    source_state=dirty
fi
if [[ "${REQUIRE_CLEAN_SOURCE:-0}" == 1 && "$source_state" != clean ]]; then
    echo "Refusing governed image build from a dirty source tree" >&2
    exit 1
fi

if command -v buildah >/dev/null; then
    buildah bud --pull-never \
        --build-arg "VERSION=$version" \
        --build-arg "REVISION=$revision" \
        --build-arg "CREATED=$created" \
        --build-arg "SOURCE_STATE=$source_state" \
        --build-arg "BINARY_SHA256=$binary_sha256" \
        -t "$image" "$root"
    if [[ -n "$dist" ]]; then
        mkdir -p "$dist"
        buildah push "$image" "docker-archive:$dist/frame-${version}-linux-x86_64.oci.tar:$image"
        chmod 0644 "$dist/frame-${version}-linux-x86_64.oci.tar"
    fi
elif command -v docker >/dev/null; then
    docker build --pull=false \
        --build-arg "VERSION=$version" \
        --build-arg "REVISION=$revision" \
        --build-arg "CREATED=$created" \
        --build-arg "SOURCE_STATE=$source_state" \
        --build-arg "BINARY_SHA256=$binary_sha256" \
        -t "$image" "$root"
    if [[ -n "$dist" ]]; then
        mkdir -p "$dist"
        docker save -o "$dist/frame-${version}-linux-x86_64.oci.tar" "$image"
        chmod 0644 "$dist/frame-${version}-linux-x86_64.oci.tar"
    fi
else
    echo "Image build requires rootless Buildah (preferred) or Docker" >&2
    exit 1
fi

if [[ -n "$dist" ]]; then
    "$root/scripts/update-checksums.sh" "$dist" \
        "frame-${version}-linux-x86_64.oci.tar"
    if command -v trivy >/dev/null; then
        trivy image --quiet --input "$dist/frame-${version}-linux-x86_64.oci.tar" \
            --exit-code 1 --severity HIGH,CRITICAL
    fi
fi

echo "Built $image (source-state=$source_state binary-sha256=$binary_sha256)"
