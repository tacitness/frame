#!/usr/bin/env bash
set -euo pipefail

apply=0
install_ruleset=0
for argument in "$@"; do
    case "$argument" in
        --apply) apply=1 ;;
        --ruleset) install_ruleset=1 ;;
        --dry-run) ;;
        *) echo "usage: github-bootstrap.sh [--dry-run|--apply] [--ruleset]" >&2; exit 1 ;;
    esac
done

root="$(git rev-parse --show-toplevel)"
cd "$root"
for tool in gh jq python3; do
    command -v "$tool" >/dev/null || { echo "$tool is required" >&2; exit 1; }
done

repo="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
[[ "$repo" == "tacitness/frame" ]] || {
    echo "Refusing to configure unexpected repository: $repo" >&2
    exit 1
}

if ((apply == 0)); then
    echo "DRY RUN: would configure settings, environments, labels, milestones, and variables for $repo"
    echo "  security: secret scanning/push protection, Dependabot alerts/updates, private reporting"
    echo "  environment: release (current user approval; main and v* only)"
    echo "  environment: sonarqube (main and v* only)"
    echo "  remove obsolete default labels: documentation, question"
    jq -r '.[].name | "  label: \(.)"' ops/github/labels.json
    jq -r '.[].title | "  milestone: \(.)"' ops/github/milestones.json
    python3 scripts/github-issues-sync.py --dry-run
    ((install_ruleset == 0)) || echo "  ruleset: Protected main delivery"
    exit 0
fi

gh api --method PATCH "repos/$repo" \
    -F has_issues=true \
    -F allow_squash_merge=true \
    -F allow_merge_commit=false \
    -F allow_rebase_merge=true \
    -F delete_branch_on_merge=true \
    -f squash_merge_commit_title=PR_TITLE \
    -f squash_merge_commit_message=COMMIT_MESSAGES >/dev/null

security_payload="$(jq -nc '{
  security_and_analysis: {
    secret_scanning: {status: "enabled"},
    secret_scanning_push_protection: {status: "enabled"}
  }
}')"
gh api --method PATCH "repos/$repo" --input - <<<"$security_payload" >/dev/null
gh api --method PUT "repos/$repo/vulnerability-alerts" >/dev/null
gh api --method PUT "repos/$repo/automated-security-fixes" >/dev/null
gh api --method PUT "repos/$repo/private-vulnerability-reporting" >/dev/null
security_state="$(gh api "repos/$repo" --jq '.security_and_analysis')"
jq -e '
  .secret_scanning.status == "enabled" and
  .secret_scanning_push_protection.status == "enabled" and
  .dependabot_security_updates.status == "enabled"
' <<<"$security_state" >/dev/null || {
    echo "GitHub security backstops did not reach the required enabled state" >&2
    exit 1
}
[[ "$(gh api "repos/$repo/private-vulnerability-reporting" --jq .enabled)" == true ]] || {
    echo "Private vulnerability reporting did not reach the required enabled state" >&2
    exit 1
}

reviewer_id="$(gh api user --jq .id)"
release_payload="$(jq -nc --argjson reviewer "$reviewer_id" '{
  wait_timer: 0,
  prevent_self_review: false,
  reviewers: [{type: "User", id: $reviewer}],
  can_admins_bypass: false,
  deployment_branch_policy: {protected_branches: false, custom_branch_policies: true}
}')"
sonar_payload="$(jq -nc '{
  wait_timer: 0,
  prevent_self_review: false,
  reviewers: [],
  can_admins_bypass: false,
  deployment_branch_policy: {protected_branches: false, custom_branch_policies: true}
}')"
gh api --method PUT "repos/$repo/environments/release" --input - \
    <<<"$release_payload" >/dev/null
gh api --method PUT "repos/$repo/environments/sonarqube" --input - \
    <<<"$sonar_payload" >/dev/null

ensure_deployment_policy() {
    local environment="$1" name="$2" type="$3" existing
    existing="$(gh api "repos/$repo/environments/$environment/deployment-branch-policies")"
    if ! jq -e --arg name "$name" --arg type "$type" \
        '.branch_policies[] | select(.name == $name and .type == $type)' \
        <<<"$existing" >/dev/null; then
        gh api --method POST \
            "repos/$repo/environments/$environment/deployment-branch-policies" \
            -f name="$name" -f type="$type" >/dev/null
    fi
}

ensure_deployment_policy release main branch
ensure_deployment_policy release 'v*' tag
ensure_deployment_policy sonarqube main branch
ensure_deployment_policy sonarqube 'v*' tag

remove_deployment_policy() {
    local environment="$1" name="$2" type="$3" existing policy_id
    existing="$(gh api "repos/$repo/environments/$environment/deployment-branch-policies")"
    while IFS= read -r policy_id; do
        [[ -n "$policy_id" ]] || continue
        gh api --method DELETE \
            "repos/$repo/environments/$environment/deployment-branch-policies/$policy_id" \
            >/dev/null
    done < <(
        jq -r --arg name "$name" --arg type "$type" \
            '.branch_policies[] | select(.name == $name and .type == $type) | .id' \
            <<<"$existing"
    )
}

remove_deployment_policy release master branch
remove_deployment_policy sonarqube master branch

while IFS=$'\t' read -r name color description; do
    gh label create "$name" --repo "$repo" --color "$color" \
        --description "$description" --force >/dev/null
done < <(jq -r '.[] | [.name, .color, .description] | @tsv' ops/github/labels.json)

for obsolete_label in documentation question; do
    if gh api "repos/$repo/labels/$obsolete_label" >/dev/null 2>&1; then
        gh api --method DELETE "repos/$repo/labels/$obsolete_label" >/dev/null
    fi
done

milestones="$(gh api "repos/$repo/milestones?state=all&per_page=100")"
while IFS=$'\t' read -r title description; do
    number="$(jq -r --arg title "$title" '.[] | select(.title == $title) | .number' <<<"$milestones" | sed -n '1p')"
    if [[ -n "$number" ]]; then
        gh api --method PATCH "repos/$repo/milestones/$number" \
            -f title="$title" -f description="$description" -f state=open >/dev/null
    else
        gh api --method POST "repos/$repo/milestones" \
            -f title="$title" -f description="$description" >/dev/null
    fi
done < <(jq -r '.[] | [.title, .description] | @tsv' ops/github/milestones.json)

python3 scripts/github-issues-sync.py --apply

gh variable set FRAME_SELF_HOSTED_ENABLED --repo "$repo" --body false
gh variable set SONARQUBE_ENABLED --repo "$repo" --body false
gh variable set ECR_ENABLED --repo "$repo" --body false
gh variable set AWS_REGION --repo "$repo" --body us-west-2
gh variable set ECR_REPOSITORY --repo "$repo" \
    --body 494111853453.dkr.ecr.us-west-2.amazonaws.com/frame

if ((install_ruleset)); then
    if ! gh api "repos/$repo/contents/.github/workflows/ci.yml?ref=main" >/dev/null 2>&1; then
        echo "Refusing ruleset install until ci.yml exists on remote main" >&2
        exit 1
    fi
    ruleset_id="$(gh api "repos/$repo/rulesets" --jq '.[] | select(.name == "Protected main delivery" or .name == "Protected master delivery") | .id' | sed -n '1p')"
    if [[ -n "$ruleset_id" ]]; then
        gh api --method PUT "repos/$repo/rulesets/$ruleset_id" \
            --input ops/github/ruleset-main.json >/dev/null
    else
        gh api --method POST "repos/$repo/rulesets" \
            --input ops/github/ruleset-main.json >/dev/null
    fi
fi

echo "GitHub governance configured for $repo"
