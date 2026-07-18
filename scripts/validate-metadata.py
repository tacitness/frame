#!/usr/bin/env python3
"""Validate GitHub issue labels/titles and pull-request title policy."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "ops/github/policy.json").read_text(encoding="utf-8"))


def label_names(issue: dict[str, Any]) -> set[str]:
    return {
        label["name"] if isinstance(label, dict) else str(label)
        for label in issue.get("labels", [])
    }


def validate_axis(labels: set[str], axis: str, errors: list[str]) -> None:
    allowed = set(POLICY["axes"][axis]["labels"])
    selected = sorted(labels & allowed)
    if axis == "area":
        if not selected:
            errors.append("at least one area label is required")
    elif len(selected) != 1:
        errors.append(f"exactly one {axis} label is required; found {selected or 'none'}")


def validate_issue(issue: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    title = issue.get("title", "")
    labels = label_names(issue)
    milestone = issue.get("milestone")
    body = issue.get("body") or ""

    if not re.fullmatch(POLICY["issueTitlePattern"], title):
        errors.append("title must start with a canonical [area] or [epic:slug] prefix")
    validate_axis(labels, "type", errors)
    validate_axis(labels, "priority", errors)
    validate_axis(labels, "area", errors)

    release_labels = labels & set(POLICY["axes"]["release"]["labels"])
    if milestone and len(release_labels) != 1:
        errors.append(
            f"milestoned work needs exactly one release-impact label; found {sorted(release_labels) or 'none'}"
        )
    if "epic" in labels and not milestone:
        errors.append("an epic must belong to exactly one release milestone")
    if "status:ready" in labels and not milestone:
        errors.append("ready work must be assigned to a release milestone")
    if "status:ready" in labels and "needs-triage" in labels:
        errors.append("ready work cannot retain needs-triage")
    if milestone and "epic" not in labels and not re.search(r"(?:E\d{2}|#[1-9]\d*)", body):
        errors.append("milestoned child work must name a parent epic ID or issue number")
    return errors


def validate_pr_title(title: str) -> list[str]:
    if not re.fullmatch(POLICY["pullRequestTitlePattern"], title):
        return [
            "PR title must be a Conventional Commit, for example "
            "'fix(protocol): reject an oversized setup request'"
        ]
    if len(title) > 72:
        return [f"PR title is {len(title)} characters; maximum is 72"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", type=Path, default=os.environ.get("GITHUB_EVENT_PATH"))
    parser.add_argument("--pr-title")
    args = parser.parse_args()

    if args.pr_title is not None:
        errors = validate_pr_title(args.pr_title)
        subject = "pull request"
    elif args.event:
        event = json.loads(args.event.read_text(encoding="utf-8"))
        if "issue" not in event:
            print("No issue in event; nothing to validate")
            return 0
        errors = validate_issue(event["issue"])
        subject = f"issue #{event['issue'].get('number', '?')}"
    else:
        parser.error("--event or --pr-title is required")

    if errors:
        print(f"Metadata policy failed for {subject}:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print(f"Metadata policy passed for {subject}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
