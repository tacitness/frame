#!/usr/bin/env python3
"""Reconcile the versioned frame epic and child-issue catalog with GitHub."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "tacitness/frame"
SPEC_MARKER = "<!-- sdd-spec-version: 1.1 -->"
WORK_ITEM_PATTERN = re.compile(r"<!-- frame-work-item: ([A-Z0-9-]+) -->")
TYPE_LABELS = {"enhancement", "bug", "tech-debt", "spike", "docs", "ci", "test"}
PRIORITY_LABELS = {"p0", "p1", "p2", "p3", "p4"}
STATUS_LABELS = {
    "status:ready",
    "status:blocked",
    "status:review",
    "status:backlog",
}
RELEASE_LABELS = {
    "release:major",
    "release:minor",
    "release:patch",
    "release:none",
}


class SyncError(RuntimeError):
    """A catalog or GitHub reconciliation failure."""


def run_json(arguments: list[str], payload: dict[str, Any] | None = None) -> Any:
    command = ["gh", "api", *arguments]
    result = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        input=None if payload is None else json.dumps(payload),
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise SyncError(f"{' '.join(command)} failed: {detail}")
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)


def api_pages(endpoint: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    page = 1
    separator = "&" if "?" in endpoint else "?"
    while True:
        batch = run_json([f"{endpoint}{separator}per_page=100&page={page}"])
        if not isinstance(batch, list):
            raise SyncError(f"expected a list from {endpoint}")
        records.extend(batch)
        if len(batch) < 100:
            return records
        page += 1


def load_catalog() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    epics = json.loads((ROOT / "ops/github/epics.json").read_text(encoding="utf-8"))
    issues = json.loads((ROOT / "ops/github/issues.json").read_text(encoding="utf-8"))
    if not isinstance(epics, list) or not isinstance(issues, list):
        raise SyncError("epics.json and issues.json must contain arrays")
    validate_catalog(epics, issues)
    return epics, issues


def validate_catalog(epics: list[dict[str, Any]], issues: list[dict[str, Any]]) -> None:
    epic_ids = [entry.get("id") for entry in epics]
    issue_ids = [entry.get("id") for entry in issues]
    all_ids = epic_ids + issue_ids
    if len(set(all_ids)) != len(all_ids):
        raise SyncError("epic and issue work-item IDs must be globally unique")
    if not all(isinstance(item, str) and re.fullmatch(r"E\d{2}", item) for item in epic_ids):
        raise SyncError("epic IDs must use E##")
    if not all(
        isinstance(item, str) and re.fullmatch(r"E\d{2}-I\d{2}", item)
        for item in issue_ids
    ):
        raise SyncError("child IDs must use E##-I##")

    epic_by_id = {entry["id"]: entry for entry in epics}
    issue_id_set = set(issue_ids)
    for epic in epics:
        require_fields(
            epic,
            (
                "id",
                "slug",
                "title",
                "milestone",
                "priority",
                "areas",
                "releaseImpact",
                "status",
                "outcome",
                "baseline",
                "nonGoals",
                "acceptance",
            ),
        )
        validate_labels(epic, is_epic=True)
    for issue in issues:
        require_fields(
            issue,
            (
                "id",
                "epic",
                "title",
                "type",
                "priority",
                "areas",
                "status",
                "releaseImpact",
                "outcome",
                "audit",
                "acceptance",
                "tests",
                "dependencies",
            ),
        )
        if issue["epic"] not in epic_by_id:
            raise SyncError(f"{issue['id']} references unknown epic {issue['epic']}")
        if not issue["id"].startswith(f"{issue['epic']}-"):
            raise SyncError(f"{issue['id']} does not belong to {issue['epic']}")
        validate_labels(issue, is_epic=False)
        if not re.match(r"^\[[a-z0-9-]+\] .+", issue["title"]):
            raise SyncError(f"{issue['id']} has a noncanonical title")
        for dependency in issue["dependencies"]:
            if dependency in issue_id_set:
                continue
            if dependency.startswith(("external:", "cross-repo:", "needs-human-session:")):
                continue
            raise SyncError(f"{issue['id']} references unknown dependency {dependency}")
    for epic_id in epic_by_id:
        if not any(issue["epic"] == epic_id for issue in issues):
            raise SyncError(f"{epic_id} has no child work items")


def require_fields(entry: dict[str, Any], fields: tuple[str, ...]) -> None:
    missing = [field for field in fields if field not in entry]
    if missing:
        raise SyncError(f"{entry.get('id', '<unknown>')} is missing {', '.join(missing)}")


def validate_labels(entry: dict[str, Any], *, is_epic: bool) -> None:
    if not is_epic and entry["type"] not in TYPE_LABELS:
        raise SyncError(f"{entry['id']} has invalid type {entry['type']}")
    if entry["priority"] not in PRIORITY_LABELS:
        raise SyncError(f"{entry['id']} has invalid priority {entry['priority']}")
    if entry["status"] not in STATUS_LABELS:
        raise SyncError(f"{entry['id']} has invalid status {entry['status']}")
    if entry["releaseImpact"] not in RELEASE_LABELS:
        raise SyncError(f"{entry['id']} has invalid release impact")
    if not entry["areas"] or not all(isinstance(area, str) for area in entry["areas"]):
        raise SyncError(f"{entry['id']} must have one or more areas")


def epic_title(epic: dict[str, Any]) -> str:
    return f"[epic:{epic['slug']}] {epic['id']} - {epic['title']}"


def labels_for(entry: dict[str, Any], *, is_epic: bool) -> list[str]:
    labels = ["enhancement" if is_epic else entry["type"], entry["priority"]]
    labels.extend(entry["areas"])
    if is_epic:
        labels.append("epic")
    labels.extend([entry["status"], entry["releaseImpact"]])
    if entry["id"] == "E09" or any(
        str(value).startswith("needs-human-session:")
        for value in entry.get("dependencies", [])
    ):
        labels.append("needs-human-session")
    return list(dict.fromkeys(labels))


def checklist(lines: list[str]) -> str:
    return "\n".join(f"- [ ] {line}" for line in lines)


def bullet_list(lines: list[str]) -> str:
    return "\n".join(f"- {line}" for line in lines) if lines else "- None."


def dependency_text(
    dependencies: list[str], issue_numbers: dict[str, int]
) -> list[str]:
    rendered: list[str] = []
    for dependency in dependencies:
        number = issue_numbers.get(dependency)
        rendered.append(f"#{number} (`{dependency}`)" if number else dependency)
    return rendered


def render_epic(
    epic: dict[str, Any],
    children: list[dict[str, Any]],
    issue_numbers: dict[str, int],
) -> str:
    child_lines = []
    for child in children:
        number = issue_numbers.get(child["id"])
        prefix = f"#{number}" if number else child["id"]
        child_lines.append(f"- [ ] {prefix} — `{child['id']}` {child['title']}")
    child_map = "\n".join(child_lines) or "- [ ] No child work cataloged."
    return f"""{SPEC_MARKER}
<!-- frame-work-item: {epic['id']} -->

## Release-level outcome

{epic['outcome']}

## Repository & System Clarity

- Repository: `tacitness/frame`
- tsctl repos.yaml key: `frame`
- System/subdomain: freestanding x86-64 NASM X11 display server
- Protocol authority: https://www.x.org/releases/current/doc/xproto/x11protocol.html

## Existing System Audit

{epic['baseline']}

Relevant versioned sources: `frame.asm`, `AGENTS.md`, `docs/`, `tests/`, `ops/github/`, and the canonical X.Org/xorgproto references named by the epic.

## Implementation Constraints

- Preserve client isolation, exact wire framing, deterministic cleanup, and hardware safety.
- Non-goal: {epic['nonGoals']}
- Automated work must use isolated numeric displays, temporary `HOME`, and `--noinput`; no root, DRM, evdev, KVM, container socket, or live user X socket.

## Ordered child issue map

{child_map}

## Epic acceptance and release gates

{checklist(epic['acceptance'])}
- [ ] Every child issue is closed or explicitly removed from scope.
- [ ] `make quality` and `make ci-local` pass on the exact candidate commit.
- [ ] Security, SonarQube, compatibility, performance, and manual evidence required by this milestone is attached.
- [ ] Release notes, known limitations, rollback, and recovery requirements are documented.

## Testing Strategy

```sh
make quality
make ci-local
```

## Exact release milestone

`{epic['milestone']}`

## Related Issues & Blockers

- Child dependencies are authoritative in their own issue bodies and native sub-issue links.
- Hardware-affecting acceptance remains human-controlled from a recoverable TTY.
"""


def render_issue(
    issue: dict[str, Any],
    epic: dict[str, Any],
    issue_numbers: dict[str, int],
) -> str:
    epic_number = issue_numbers.get(epic["id"])
    parent = f"#{epic_number}" if epic_number else epic["id"]
    tests = "\n".join(issue["tests"])
    dependencies = dependency_text(issue["dependencies"], issue_numbers)
    return f"""{SPEC_MARKER}
<!-- frame-work-item: {issue['id']} -->

## Required outcome

{issue['outcome']}

## Repository & System Clarity

- Repository: `tacitness/frame`
- tsctl repos.yaml key: `frame`
- System/subdomain: freestanding x86-64 NASM X11 display server
- Protocol authority: https://www.x.org/releases/current/doc/xproto/x11protocol.html

## Existing System Audit

{issue['audit']}

Relevant versioned sources: `frame.asm`, `AGENTS.md`, `docs/`, `tests/`, `ops/github/`, and the canonical X.Org/xorgproto references named by the implementation issue.

## Parent epic and milestone

- Parent: {parent} (`{epic['id']}` — {epic['title']})
- Milestone: `{epic['milestone']}`

## Acceptance criteria

{checklist(issue['acceptance'])}
- [ ] Source, tests, documentation, compatibility status, and diagnostics agree.
- [ ] `make quality` passes; implementation work also completes `make ci-local` or records the exact external blocker.

## Testing Strategy

```sh
{tests}
```

## Related Issues & Blockers

{bullet_list(dependencies)}

## Implementation Constraints

- Validate every client-controlled length, count, ID, state transition, syscall result, and cleanup edge before use.
- Automated runs use an isolated numeric display, temporary `HOME`, and `--noinput`.
- Automated work never uses root, DRM, evdev, KVM, a container socket, or the user's live X socket.
- Hardware acceptance and bare-console measurements require `needs-human-session` and `tests/manual/README.md`.

## Non-goals

- No unrelated protocol expansion, compatibility claim without evidence, benchmark threshold on noisy hosts, or security/safety bypass.
"""


def issue_marker(issue: dict[str, Any]) -> str | None:
    body = issue.get("body") or ""
    match = WORK_ITEM_PATTERN.search(body)
    return match.group(1) if match else None


def current_labels(issue: dict[str, Any]) -> set[str]:
    return {entry["name"] for entry in issue.get("labels", [])}


def needs_update(
    current: dict[str, Any],
    *,
    title: str,
    body: str,
    labels: list[str],
    milestone_number: int,
) -> bool:
    current_milestone = (current.get("milestone") or {}).get("number")
    return any(
        (
            current.get("title") != title,
            (current.get("body") or "") != body,
            current_labels(current) != set(labels),
            current_milestone != milestone_number,
            current.get("state") != "open",
        )
    )


def create_placeholder(
    entry: dict[str, Any], *, title: str, labels: list[str], milestone_number: int
) -> dict[str, Any]:
    return run_json(
        ["--method", "POST", f"repos/{REPOSITORY}/issues", "--input", "-"],
        {
            "title": title,
            "body": f"{SPEC_MARKER}\n<!-- frame-work-item: {entry['id']} -->\n\nSynchronization in progress.",
            "labels": labels,
            "milestone": milestone_number,
        },
    )


def update_issue(
    current: dict[str, Any],
    *,
    title: str,
    body: str,
    labels: list[str],
    milestone_number: int,
) -> dict[str, Any]:
    return run_json(
        [
            "--method",
            "PATCH",
            f"repos/{REPOSITORY}/issues/{current['number']}",
            "--input",
            "-",
        ],
        {
            "title": title,
            "body": body,
            "labels": labels,
            "milestone": milestone_number,
            "state": "open",
        },
    )


def ensure_native_children(
    parent: dict[str, Any], children: list[dict[str, Any]]
) -> int:
    existing = api_pages(
        f"repos/{REPOSITORY}/issues/{parent['number']}/sub_issues?"
    )
    existing_ids = {entry["id"] for entry in existing}
    added = 0
    for child in children:
        if child["id"] in existing_ids:
            continue
        run_json(
            [
                "--method",
                "POST",
                f"repos/{REPOSITORY}/issues/{parent['number']}/sub_issues",
                "--input",
                "-",
            ],
            {"sub_issue_id": child["id"]},
        )
        added += 1
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="create and reconcile issues")
    mode.add_argument("--dry-run", action="store_true", help="show planned reconciliation")
    arguments = parser.parse_args()

    epics, children = load_catalog()
    if not arguments.apply:
        print(
            f"DRY RUN: would reconcile {len(epics)} epics and {len(children)} child issues in {REPOSITORY}"
        )
        for epic in epics:
            count = sum(child["epic"] == epic["id"] for child in children)
            print(f"  {epic['id']}: {epic_title(epic)} ({count} children; {epic['milestone']})")
        return 0

    repository = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    if repository != REPOSITORY:
        raise SyncError(f"refusing to configure unexpected repository {repository}")

    milestones = api_pages(f"repos/{REPOSITORY}/milestones?state=all&")
    milestone_numbers = {entry["title"]: entry["number"] for entry in milestones}
    missing_milestones = {
        epic["milestone"] for epic in epics if epic["milestone"] not in milestone_numbers
    }
    if missing_milestones:
        raise SyncError(f"missing milestones: {', '.join(sorted(missing_milestones))}")

    existing = [
        issue
        for issue in api_pages(f"repos/{REPOSITORY}/issues?state=all&")
        if "pull_request" not in issue
    ]
    by_number = {issue["number"]: issue for issue in existing}
    by_title = {issue["title"]: issue for issue in existing}
    by_marker = {
        marker: issue
        for issue in existing
        if (marker := issue_marker(issue)) is not None
    }

    catalog = [*epics, *children]
    records: dict[str, dict[str, Any]] = {}
    created = 0
    for entry in catalog:
        title = epic_title(entry) if "slug" in entry else entry["title"]
        current = by_marker.get(entry["id"])
        legacy_number = entry.get("legacyIssueNumber")
        if current is None and legacy_number is not None:
            current = by_number.get(legacy_number)
        if current is None:
            current = by_title.get(title)
        if current is None:
            milestone_title = (
                entry["milestone"]
                if "milestone" in entry
                else next(epic["milestone"] for epic in epics if epic["id"] == entry["epic"])
            )
            current = create_placeholder(
                entry,
                title=title,
                labels=labels_for(entry, is_epic="slug" in entry),
                milestone_number=milestone_numbers[milestone_title],
            )
            created += 1
            print(f"created #{current['number']} {entry['id']} {title}", flush=True)
        records[entry["id"]] = current

    issue_numbers = {item_id: issue["number"] for item_id, issue in records.items()}
    epic_by_id = {entry["id"]: entry for entry in epics}

    update_jobs: list[tuple[dict[str, Any], str, str, list[str], int]] = []
    for epic in epics:
        epic_children = [child for child in children if child["epic"] == epic["id"]]
        title = epic_title(epic)
        body = render_epic(epic, epic_children, issue_numbers)
        labels = labels_for(epic, is_epic=True)
        milestone_number = milestone_numbers[epic["milestone"]]
        current = records[epic["id"]]
        if needs_update(
            current,
            title=title,
            body=body,
            labels=labels,
            milestone_number=milestone_number,
        ):
            update_jobs.append((current, title, body, labels, milestone_number))
    for issue in children:
        epic = epic_by_id[issue["epic"]]
        body = render_issue(issue, epic, issue_numbers)
        labels = labels_for(issue, is_epic=False)
        milestone_number = milestone_numbers[epic["milestone"]]
        current = records[issue["id"]]
        if needs_update(
            current,
            title=issue["title"],
            body=body,
            labels=labels,
            milestone_number=milestone_number,
        ):
            update_jobs.append(
                (current, issue["title"], body, labels, milestone_number)
            )

    updated = 0
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(
                update_issue,
                current,
                title=title,
                body=body,
                labels=labels,
                milestone_number=milestone_number,
            ): (current["number"], title)
            for current, title, body, labels, milestone_number in update_jobs
        }
        for future in as_completed(futures):
            number, title = futures[future]
            future.result()
            updated += 1
            print(f"updated #{number} {title}", flush=True)

    native_links = 0
    for epic in epics:
        parent = records[epic["id"]]
        epic_children = [
            records[child["id"]] for child in children if child["epic"] == epic["id"]
        ]
        native_links += ensure_native_children(parent, epic_children)

    print(
        f"GitHub issue catalog synchronized: {created} created, {updated} updated, "
        f"{native_links} native sub-issue links added"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SyncError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"github-issues-sync: {error}", file=sys.stderr)
        raise SystemExit(1)
