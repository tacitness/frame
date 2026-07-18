#!/usr/bin/env python3
"""Repository policy checks and SonarQube external-issue generation."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Rule:
    rule_id: str
    name: str
    description: str
    severity: str
    issue_type: str
    clean_code: str
    software_quality: str
    impact_severity: str
    local_gate: bool = True


@dataclass(frozen=True)
class Finding:
    rule: Rule
    path: Path
    line: int
    message: str


RULES = {
    "ASM001": Rule(
        "ASM001",
        "No privileged userspace instructions",
        "Privileged CPU instructions cannot safely execute in this userspace server.",
        "BLOCKER",
        "VULNERABILITY",
        "TRUSTWORTHY",
        "SECURITY",
        "BLOCKER",
    ),
    "ASM002": Rule(
        "ASM002",
        "Use the x86-64 syscall ABI",
        "Legacy int 0x80 and sysenter entry paths are forbidden in 64-bit frame code.",
        "BLOCKER",
        "BUG",
        "CONVENTIONAL",
        "RELIABILITY",
        "BLOCKER",
    ),
    "ASM003": Rule(
        "ASM003",
        "No duplicate unconditional transfer",
        "Consecutive branches to the same target indicate unreachable or generated code drift.",
        "MAJOR",
        "CODE_SMELL",
        "CLEAR",
        "MAINTAINABILITY",
        "HIGH",
    ),
    "ASM004": Rule(
        "ASM004",
        "Required assembly model declarations",
        "The primary source must explicitly declare 64-bit mode, relative addressing, and an entry point.",
        "CRITICAL",
        "BUG",
        "COMPLETE",
        "RELIABILITY",
        "HIGH",
    ),
    "SEC001": Rule(
        "SEC001",
        "Do not expose unauthenticated X11 clients",
        "A world-connectable X11 socket must authenticate clients before accepting protocol requests.",
        "BLOCKER",
        "VULNERABILITY",
        "TRUSTWORTHY",
        "SECURITY",
        "BLOCKER",
    ),
    "CI001": Rule(
        "CI001",
        "Pin third-party actions by commit",
        "Third-party GitHub Actions must use a full immutable 40-character commit SHA.",
        "CRITICAL",
        "VULNERABILITY",
        "TRUSTWORTHY",
        "SECURITY",
        "HIGH",
    ),
    "CI002": Rule(
        "CI002",
        "No pull_request_target execution",
        "pull_request_target is prohibited because it can combine untrusted changes with repository secrets.",
        "BLOCKER",
        "VULNERABILITY",
        "TRUSTWORTHY",
        "SECURITY",
        "BLOCKER",
    ),
    "CI003": Rule(
        "CI003",
        "No untrusted self-hosted execution",
        "A workflow that accepts pull requests must not select a self-hosted runner.",
        "BLOCKER",
        "VULNERABILITY",
        "TRUSTWORTHY",
        "SECURITY",
        "BLOCKER",
    ),
    "CI004": Rule(
        "CI004",
        "No hardware-taking test invocation",
        "Automated tests must not invoke modeset, display, or live-input frame modes.",
        "BLOCKER",
        "VULNERABILITY",
        "TRUSTWORTHY",
        "SECURITY",
        "BLOCKER",
    ),
}

INSTRUCTION = re.compile(r"^\s*(?:[A-Za-z_.$?][\w.$?]*:\s*)?([A-Za-z][A-Za-z0-9]*)\b", re.I)
PRIVILEGED = {"cli", "sti", "hlt", "lgdt", "lidt", "ltr", "invlpg", "in", "out", "rdmsr", "wrmsr"}
JUMP = re.compile(r"^\s*jmp\s+([^\s;]+)", re.I)
USES = re.compile(r"^\s*-?\s*uses:\s*([^#\s]+)")
SHA = re.compile(r"^[0-9a-fA-F]{40}$")
HARDWARE_MODE = re.compile(r"(?:^|\s)(?:\./)?frame(?:\s+\S+)*\s+(--modeset|--display|--watch-input)(?:\s|$)")


def source_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def check_assembly(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    lines = source_lines(path)
    declarations = {
        "BITS 64": False,
        "DEFAULT REL": False,
        "GLOBAL _start": False,
        "SECTION .bss": False,
        "SECTION .rodata": False,
        "SECTION .text": False,
    }
    previous_jump: tuple[str, int] | None = None

    for number, raw in enumerate(lines, 1):
        code = raw.split(";", 1)[0].rstrip()
        normalized = code.strip().lower()
        declarations["BITS 64"] |= normalized == "bits 64"
        declarations["DEFAULT REL"] |= normalized == "default rel"
        declarations["GLOBAL _start"] |= normalized == "global _start"
        declarations["SECTION .bss"] |= normalized == "section .bss"
        declarations["SECTION .rodata"] |= normalized == "section .rodata"
        declarations["SECTION .text"] |= normalized == "section .text"

        match = INSTRUCTION.match(code)
        if match:
            mnemonic = match.group(1).lower()
            if mnemonic in PRIVILEGED:
                findings.append(Finding(RULES["ASM001"], path, number, f"privileged instruction '{mnemonic}'"))
            if mnemonic == "sysenter" or (mnemonic == "int" and re.search(r"\b(?:0x80|80h)\b", code, re.I)):
                findings.append(Finding(RULES["ASM002"], path, number, "legacy syscall entry instruction"))

        jump = JUMP.match(code)
        if jump:
            target = jump.group(1).lower()
            if previous_jump and previous_jump[0] == target:
                findings.append(
                    Finding(RULES["ASM003"], path, number, f"duplicate jump to {target}; prior jump is line {previous_jump[1]}")
                )
            previous_jump = (target, number)
        elif normalized:
            previous_jump = None

    missing = [name for name, present in declarations.items() if not present]
    if missing:
        findings.append(Finding(RULES["ASM004"], path, 1, "missing declarations: " + ", ".join(missing)))
    source = "\n".join(lines)
    world_socket = re.search(r"^\s*mov\s+esi,\s*0o777\b", source, re.M)
    authenticates = re.search(
        r"^\s*call\s+(?:authenticate_client|verify_peer_credentials)\b", source, re.M
    )
    if world_socket and not authenticates:
        line = next(
            number
            for number, value in enumerate(lines, 1)
            if re.search(r"^\s*mov\s+esi,\s*0o777\b", value)
        )
        findings.append(
            Finding(
                RULES["SEC001"],
                path,
                line,
                "the mode-0777 X11 socket accepts setup auth bytes without validating them",
            )
        )
    return findings


def workflow_files() -> list[Path]:
    directory = ROOT / ".github" / "workflows"
    return sorted([*directory.glob("*.yml"), *directory.glob("*.yaml")]) if directory.exists() else []


def check_workflow(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    lines = source_lines(path)
    text = "\n".join(lines)
    pull_request = bool(re.search(r"^\s*pull_request\s*:", text, re.M))
    self_hosted = bool(re.search(r"runs-on\s*:.*(?:self-hosted|frame-ci-)", text))

    for number, line in enumerate(lines, 1):
        uses = USES.match(line)
        if uses:
            reference = uses.group(1)
            if reference.startswith("./") or "@" not in reference:
                continue
            revision = reference.rsplit("@", 1)[1]
            if not SHA.fullmatch(revision):
                findings.append(Finding(RULES["CI001"], path, number, f"action reference is mutable: {reference}"))
        if re.match(r"^\s*pull_request_target\s*:", line):
            findings.append(Finding(RULES["CI002"], path, number, "prohibited pull_request_target trigger"))
        if HARDWARE_MODE.search(line):
            findings.append(Finding(RULES["CI004"], path, number, "hardware-affecting frame invocation in automation"))

    if pull_request and self_hosted:
        line = next((i for i, value in enumerate(lines, 1) if "runs-on:" in value), 1)
        findings.append(Finding(RULES["CI003"], path, line, "pull-request workflow selects a self-hosted runner"))
    return findings


def all_findings(assembly: Path) -> list[Finding]:
    findings = check_assembly(assembly)
    for workflow in workflow_files():
        findings.extend(check_workflow(workflow))
    return findings


def sonar_report(findings: list[Finding]) -> dict[str, object]:
    used_rules = sorted({finding.rule for finding in findings}, key=lambda rule: rule.rule_id)
    # Keep every rule visible to downstream tooling even when the scan is clean.
    used_rules = sorted(RULES.values(), key=lambda rule: rule.rule_id)
    return {
        "rules": [
            {
                "id": rule.rule_id,
                "name": rule.name,
                "description": rule.description,
                "engineId": "frame-policy",
                "cleanCodeAttribute": rule.clean_code,
                "type": rule.issue_type,
                "severity": rule.severity,
                "impacts": [
                    {
                        "softwareQuality": rule.software_quality,
                        "severity": rule.impact_severity,
                    }
                ],
            }
            for rule in used_rules
        ],
        "issues": [
            {
                "ruleId": finding.rule.rule_id,
                "effortMinutes": 10,
                "primaryLocation": {
                    "message": finding.message,
                    "filePath": finding.path.relative_to(ROOT).as_posix(),
                    "textRange": {
                        "startLine": finding.line,
                        "startColumn": 0,
                        "endLine": finding.line,
                        "endColumn": max(1, len(source_lines(finding.path)[finding.line - 1])),
                    },
                },
            }
            for finding in findings
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("assembly", nargs="?", default="frame.asm")
    parser.add_argument("--sonar-report", type=Path)
    args = parser.parse_args()
    assembly = (ROOT / args.assembly).resolve()
    findings = all_findings(assembly)

    if args.sonar_report:
        destination = args.sonar_report if args.sonar_report.is_absolute() else ROOT / args.sonar_report
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(sonar_report(findings), indent=2) + "\n", encoding="utf-8")
        shown = destination.relative_to(ROOT) if destination.is_relative_to(ROOT) else destination
        print(f"Wrote SonarQube external report: {shown}")

    if findings:
        for finding in findings:
            print(
                f"{finding.path.relative_to(ROOT)}:{finding.line}: "
                f"{finding.rule.severity} {finding.rule.rule_id}: {finding.message}",
                file=sys.stderr,
            )
    blocking = [finding for finding in findings if finding.rule.local_gate]
    if blocking:
        return 1
    if findings:
        print(f"Blocking policy passed; {len(findings)} tracked external issue(s) remain")
    else:
        print("Assembly and workflow policy passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
