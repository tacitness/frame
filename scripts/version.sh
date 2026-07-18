#!/usr/bin/env bash
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
seed="$(sed -n '1p' "$root/VERSION")"
semver='^[0-9]+\.[0-9]+\.[0-9]+$'
[[ "$seed" =~ $semver ]] || { echo "VERSION must contain MAJOR.MINOR.PATCH" >&2; exit 1; }

latest_tag() {
    git -C "$root" tag --list 'v[0-9]*.[0-9]*.[0-9]*' --sort=-v:refname | sed -n '1p'
}

current() {
    local exact latest short
    exact="$(git -C "$root" describe --tags --exact-match --match 'v[0-9]*.[0-9]*.[0-9]*' 2>/dev/null || true)"
    if [[ -n "$exact" ]]; then
        printf '%s\n' "${exact#v}"
        return
    fi
    latest="$(latest_tag)"
    short="$(git -C "$root" rev-parse --short=12 HEAD 2>/dev/null || printf unknown)"
    if [[ -n "$latest" ]]; then
        printf '%s-dev.g%s\n' "${latest#v}" "$short"
    else
        printf '%s-dev.g%s\n' "$seed" "$short"
    fi
}

check() {
    local tag="${1:-}" tag_commit head_commit
    [[ "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
        echo "release tag must be vMAJOR.MINOR.PATCH: $tag" >&2
        exit 1
    }
    tag_commit="$(git -C "$root" rev-parse --verify "refs/tags/${tag}^{commit}")"
    head_commit="$(git -C "$root" rev-parse --verify 'HEAD^{commit}')"
    [[ "$tag_commit" == "$head_commit" ]] || {
        echo "$tag points to $tag_commit, not HEAD $head_commit" >&2
        exit 1
    }
    printf '%s\n' "${tag#v}"
}

next() {
    local kind="${1:?bump kind required}" base major minor patch
    base="$(latest_tag)"
    base="${base#v}"
    [[ -n "$base" ]] || base="$seed"
    IFS=. read -r major minor patch <<<"$base"
    case "$kind" in
        patch) ((patch += 1)) ;;
        minor) ((minor += 1)); patch=0 ;;
        major) ((major += 1)); minor=0; patch=0 ;;
        *) echo "bump kind must be patch, minor, or major" >&2; exit 1 ;;
    esac
    printf 'v%s.%s.%s\n' "$major" "$minor" "$patch"
}

case "${1:-current}" in
    current) current ;;
    check) check "${2:-}" ;;
    next) next "${2:-}" ;;
    *) echo "usage: version.sh {current|check TAG|next KIND}" >&2; exit 1 ;;
esac
