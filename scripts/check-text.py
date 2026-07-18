#!/usr/bin/env python3
"""Fail on text defects that create noisy or ambiguous reviews."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".pdf", ".ico"}


def repository_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / item.decode() for item in result.stdout.split(b"\0") if item]


def main() -> int:
    findings: list[str] = []
    for path in repository_files():
        if not path.is_file() or path.suffix.lower() in SKIP_SUFFIXES:
            continue
        data = path.read_bytes()
        if b"\0" in data:
            continue
        relative = path.relative_to(ROOT)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as error:
            findings.append(f"{relative}: invalid UTF-8 at byte {error.start}")
            continue
        if "\r" in text:
            findings.append(f"{relative}: CR/CRLF line endings are not allowed")
        for number, line in enumerate(text.splitlines(), 1):
            if line.rstrip(" \t") != line:
                findings.append(f"{relative}:{number}: trailing whitespace")
        if data and not data.endswith(b"\n"):
            findings.append(f"{relative}: missing final newline")

    if findings:
        print("Text policy violations:", file=sys.stderr)
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        return 1
    print("Text policy passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
