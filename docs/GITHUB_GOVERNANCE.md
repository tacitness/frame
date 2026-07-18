# GitHub issue, epic, milestone, and release governance

The machine-readable sources are `ops/github/policy.json`, `labels.json`, `milestones.json`, `epics.json`, and `issues.json`. Issue forms and
`metadata.yml` enforce the human workflow. Do not create a second taxonomy in agent prompts or project notes.

## Labels

Every open non-trivial issue has exactly one type (`enhancement`, `bug`, `tech-debt`, `spike`, `docs`, `ci`, `test`), exactly one
priority (`p0` through `p4`), and one or more areas (`assembly`, `protocol`, `compositor`, `drm`, `input`, `render`, `xkb`,
`extensions`, `build`, `release`, `security`, `performance`, `agents`).

Milestoned issues also have exactly one release-impact label: `release:major`, `release:minor`, `release:patch`, or `release:none`.
Workflow/supplemental labels never replace the required axes. `p0` is reserved for an active security, data-loss, or operator emergency;
`p2` is the planning default.

## Titles

Issue titles start with one canonical area, for example:

```text
[protocol] Reject truncated ChangeProperty payloads
[drm] Restore the prior CRTC after interrupted acquisition
[epic:test-system] E02 - Layered protocol and regression test system
```

PR titles use Conventional Commits and stay at most 72 characters:

```text
fix(protocol): reject truncated property payloads
test(client): prove pixmaps are reclaimed on disconnect
```

Squash merge uses the PR title, so title review directly controls changelog and automatic SemVer intent.

## Milestones and epics

Milestones are versioned release goals, not time buckets. An epic is a native GitHub issue labeled `epic` and assigned to exactly one
milestone. Child issues name the epic issue/ID and use the same milestone. Cross-milestone dependency is allowed; cross-milestone child
membership is not.

| Milestone | Epic IDs | Release goal |
|---|---|---|
| v0.1.0 | E01-E03 | Assembly/test/security/delivery foundation |
| v0.2.0 | E04-E05 | Core protocol and resource lifecycle |
| v0.3.0 | E06 | Rendering and compositor correctness |
| v0.4.0 | E07-E08 | Input/XKB/extensions interoperability |
| v0.5.0 | E09 | Hardware backend reliability |
| v1.0.0 | E10 | Representative desktop compatibility |

`ops/github/epics.json` is authoritative for exact titles and mapping. The roadmap does not prove existing README phase claims; an epic
closes only when its own acceptance evidence is complete.

## State transitions

1. `needs-triage`: form exists, but area/owner/evidence/dependency/milestone details may be incomplete.
2. `status:backlog`: valid work, deliberately outside a committed release.
3. `status:ready`: fully specified, one milestone/epic, no blocker, testable acceptance criteria; remove `needs-triage`.
4. `status:blocked`: issue records the concrete blocker and dependent issue/state.
5. `status:review`: implementation exists and acceptance evidence awaits independent review.
6. Closed: acceptance met, superseded/duplicate, or explicit no-change decision; epic checklist/milestone is reconciled.

Use `needs-human-session` for credentials, live product judgment, interactive hardware/session work, or human approval that an autonomous
agent must not guess.

## Release readiness

A milestone is releasable when every epic is closed or explicitly descoped, required CI/Sonar/security checks are green, current known
blockers are resolved, compatibility/manual evidence is attached, release notes are coherent, and the exact main commit has passed CI.
The automatic tag workflow then creates the SemVer tag from Conventional Commit history; `release.yml` verifies it points to HEAD.

## Bootstrap

Preview declarative GitHub changes:

```bash
scripts/github-bootstrap.sh --dry-run
```

After review, enable Issues, private vulnerability reporting, secret-scanning defenses, Dependabot security updates, and synchronize
settings, labels, milestones, epics, native sub-issues, environments, and disabled opt-in variables:

```bash
scripts/github-bootstrap.sh --apply
```

To reconcile only the declarative epic/child issue catalog after editing `epics.json` or `issues.json`:

```bash
make github-issues
```

The synchronizer uses stable `frame-work-item` markers, adopts the declared legacy issue numbers, and updates rather than duplicates
existing work. It never closes or deletes issues.

After workflows are merged to remote `main`, install/update the branch ruleset:

```bash
scripts/github-bootstrap.sh --apply --ruleset
```

The script refuses any repository except `tacitness/frame` and refuses the ruleset before `ci.yml` exists remotely. The ruleset requires
PRs, linear history, resolved conversations, and `Read-only quality gate`, `Dependency review`, and `PR title` checks. Approval count is
zero initially to avoid making a single-maintainer repo impossible to operate; enable required independent/code-owner approval when a
second regular maintainer is available.
