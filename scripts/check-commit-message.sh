#!/usr/bin/env bash
set -euo pipefail

message_file="${1:?usage: check-commit-message.sh COMMIT_MESSAGE_FILE}"
subject="$(sed -n '1p' "$message_file")"

if [[ "$subject" =~ ^Merge[[:space:]] || "$subject" =~ ^Revert[[:space:]] ]]; then
    exit 0
fi

pattern='^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-z0-9._/-]+\))?!?: [^[:space:]].*$'
if [[ ! "$subject" =~ $pattern ]]; then
    echo "Commit subject must use Conventional Commits" >&2
    echo "Example: test(protocol): reject truncated setup requests" >&2
    exit 1
fi
if (( ${#subject} > 72 )); then
    echo "Commit subject is ${#subject} characters; maximum is 72" >&2
    exit 1
fi

echo "Commit message policy passed"
