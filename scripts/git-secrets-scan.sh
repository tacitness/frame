#!/usr/bin/env bash
set -euo pipefail

mode="${1:-tree}"
message_file="${2:-}"
root="$(git rev-parse --show-toplevel)"
patterns="$root/.git-secrets-patterns"

command -v git-secrets >/dev/null || {
    echo "git-secrets is required; run scripts/install-git-secrets.sh" >&2
    exit 1
}
[[ -r "$patterns" ]] || { echo "Missing $patterns" >&2; exit 1; }

git_config=(-c "secrets.providers=git secrets --aws-provider")
while IFS= read -r pattern || [[ -n "$pattern" ]]; do
    [[ -z "$pattern" || "$pattern" == \#* ]] && continue
    git_config+=(-c "secrets.patterns=$pattern")
done <"$patterns"

report="$(mktemp)"
trap 'rm -f -- "$report"' EXIT

run_quietly() {
    if git "${git_config[@]}" secrets "$@" >"$report" 2>&1; then
        return
    fi
    echo "git-secrets found a prohibited credential pattern; matched content is suppressed." >&2
    echo "Inspect locally with git secrets using the rules in .git-secrets-patterns." >&2
    return 1
}

case "$mode" in
    staged)
        run_quietly --scan --cached --quiet
        ;;
    tree)
        run_quietly --scan --untracked --quiet
        ;;
    history)
        run_quietly --scan-history
        ;;
    message)
        [[ -n "$message_file" && -f "$message_file" ]] || {
            echo "git-secrets message scan requires a commit-message file" >&2
            exit 1
        }
        run_quietly --scan --quiet -- "$message_file"
        ;;
    all)
        run_quietly --scan --untracked --quiet
        run_quietly --scan-history
        ;;
    *)
        echo "usage: git-secrets-scan.sh {staged|tree|history|all|message FILE}" >&2
        exit 1
        ;;
esac

echo "git-secrets $mode scan passed"
