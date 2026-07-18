# Tacitsoft Agent Bootstrap Pack

Purpose: shared operating context for Copilot, Codex, Claude, Gemini, and other repo-local agents working inside the Tacitsoft ecosystem.

Status: temporary shim until brain-backed context injection is available.
Tracked replacement work: #114.

Use this file as the always-on, cross-repo control-plane context.
Put repo-specific product, domain, or coding rules in repo-local instruction files.

## How To Consume This In Other Repos

Preferred when a repo already has local `AGENTS.md` or `.github/copilot-instructions.md` customizations:

```bash
/data/src/tacitsoft/infrastructure/tsctl/scripts/link-agent-bootstrap.sh /path/to/target-repo
```

Sweep every checked-out repo from `repos.yaml` and remediate drift idempotently:

```bash
/data/src/tacitsoft/infrastructure/tsctl/scripts/link-agent-bootstrap.sh
```

That script:

- creates `./tsctl-agents-bootstrap.md` in the target repo as a symlink to this file
- creates a starter `AGENTS.md` when the target repo does not already have one
- appends a short additive reference block to existing `AGENTS.md`
- appends a short additive reference block to existing `.github/copilot-instructions.md`
- leaves the repo's existing instructions in place
- can be rerun safely; it skips repos that are already remediated

For broader `.github/copilot-instructions.md` creation or section backfills
across managed repos, run the `tsctl` repo's `scripts/copilot-sweep.py`. It is
the bulk Copilot-instructions distribution path; `link-agent-bootstrap.sh`
handles the additive shared-bootstrap link plus first-use `AGENTS.md` creation.

Manual equivalent:

```bash
ln -s /data/src/tacitsoft/infrastructure/tsctl/docs/shared/tacitsoft-agent-bootstrap.md tsctl-agents-bootstrap.md
```

Then append an additive reference block to the repo's existing instruction files instead of replacing them.

Less preferred fallback when a repo does not already have a global instruction file:

```bash
ln -s /data/src/tacitsoft/infrastructure/tsctl/docs/shared/tacitsoft-agent-bootstrap.md AGENTS.md
```

If a repo already has important local always-on instructions, do not replace them. Keep the shared pack additive and move repo-specific additions into scoped files such as:

- `.github/instructions/domain.instructions.md`
- `.github/instructions/frontend.instructions.md`
- `.github/instructions/backend.instructions.md`

Do not fork this file lightly. Prefer symlink or copy-then-note-delta so behavior stays consistent across repos.

## Review, Resolve, And Merge Agent Work

Use `directives/review-resolve-and-merge-agent-work.md` when a previous agent
run left behind a branch, pull request, or partial implementation that needs a
final resolver pass.

Post-agent completion hygiene is mandatory before creating any new branch or
pull request:

```bash
gh pr list && git fetch && git branch && git branch -r
```

Decision tree:

1. If pull request(s) already exist for the issue work, review, resolve, and
	merge those existing PRs. Do not create a duplicate branch or PR.
2. If no PR exists but a local or remote branch contains the completed work,
	recover that branch and finish it with the resolver workflow.
3. Create a new branch or PR only when no PR exists for completed work, or the
	work never reached a PR and branch recovery is required.
4. After merge, prune merged agent branches with
	`tsctl agent prune-merged <repo_key>` and leave unmerged branches alone.

Resolver worktree hygiene:

- Keep the repo root checkout on the default branch as the canonical worktree.
- Use external worktrees or separate clone paths for scratch review/merge
	branches instead of repurposing the root checkout.
- Remove temporary worktrees and scratch review branches immediately after the
	review, merge, or recovery flow completes or aborts.

Recommended sequence:

1. Create or confirm the governing GitHub issue.
2. Refresh the shared bootstrap additively with `scripts/link-agent-bootstrap.sh`.
3. Run the post-agent inventory command above and identify existing PRs and
	branches before deciding on recovery work.
4. If an existing draft PR is present from the self-hosted vLLM lane, run
	`tsctl agent review-pr <repo_key> --pr <N>` first so a frontier runner can
	repair the branch without merging it.
5. If an existing non-draft PR is ready to land, run
	`tsctl agent review-merge <repo_key> --pr <N>` or the resolver directive
	against that PR; do not create a new PR.
6. If the candidate work only exists on a local branch, check out that branch
	and run the resolver locally.
7. If no PR or branch exists and issue work must be recovered, create the
	minimum necessary branch/PR.

Examples:

```bash
# Mandatory post-run inventory
gh pr list && git fetch && git branch && git branch -r

# Self-hosted vLLM draft PR frontier review path; repairs but does not merge
tsctl agent review-pr <repo_key> --pr <N> --issue <N> --runner codex

# Existing PR review/merge path; repairs and lands when green
tsctl agent review-merge <repo_key> --pr <N>

# Issue-backed resolver run
tsctl agent dispatch <repo_key> --runner claude --issue <N> --mode implement

# Local branch-only resolver run
tsctl agent run claude <repo_key> directives/review-resolve-and-merge-agent-work.md --mode implement

# After the work lands on the default branch
tsctl agent prune-merged <repo_key>
```

Review/merge, resolver, conflict cleanup, and merge-readiness work should use
the existing PR path instead of a fresh implementation dispatch when a PR
already exists. Use `tsctl agent review-pr` for vLLM draft PRs that need
frontier repair but must remain under operator merge control. Use
`tsctl agent review-merge` only when the PR is ready for the final repair and
landing pass. Both commands should prefer Codex while the Codex Code Review
quota lane can admit another run within the configured safety buffer, then fall
back to Copilot or Claude when that lane is blocked or unavailable. Use
`--runner` only for an intentional operator override.

Use `tsctl agent prune-merged <repo_key>` for remote `agent/*` cleanup after landing. It only deletes
branches already contained in the default branch and leaves unmerged branches alone.

If `AGENTS.md` was missing, the bootstrap script creates a starter file that
explicitly says it was absent and that the first successful build or meaningful
repo-local agent run should refine it with repo-specific guidance. Existing
`AGENTS.md` and `.github/copilot-instructions.md` files must be preserved and
updated additively.

## Branch Naming And Lifecycle Contract

Every producer of branches — tsctl runners, interactive Claude/Codex/Gemini
sessions, and humans — follows one contract so `git branch -r` stays a map of
live work, not a graveyard. Consumer-repo `AGENTS.md` files inherit this by
reference; do not restate it per repo.

### Naming

| Purpose | Namespace | Owner |
| --- | --- | --- |
| Issue-driven change | `fix/<N>-<slug>`, `feat/<N>-<slug>`, `chore/<N>-<slug>`, `docs/<N>-<slug>`, `ci/<N>-<slug>` | any producer |
| tsctl runner delivery | `agent/<repo_key>/…` (minted by `buildAgentBranchName`) | tsctl runner only — never hand-mint |
| Run-recovery | `recover/i<N>-<slug>` | recovery flows only |

- **Include the issue number.** `<N>` is the governing GitHub issue; `<slug>` is
  a short kebab-case summary. Pick one style for the issue and keep it.
- **No bare timestamps** in branch names (e.g. `…-20260702-061831`) and no
  bare-number-vs-slug drift (`fix/issue-42` and `fix/42-thing` for the same
  work). The name derives from the issue, so it is deterministic.

### One branch per issue

Reuse the deterministic branch on every retry of the same issue instead of
minting a variant. Runner branches are already deterministic and reused
(`buildAgentBranchName`, `internal/executor/executor.go`); interactive sessions
must do the same by hand. If a branch for the issue already exists (post-run
inventory above), continue it — do not open a parallel ref.

### Cleanup duty

- The session that **merges** a PR deletes its head branch. This is automatic
  once catalog `delete_branch_on_merge` is enabled (issue #489); until then it
  is manual and mandatory.
- The session that **abandons** work does one of: (a) leave a **draft** PR
  labeled `agent-blocked` or `agent-superseded` so the state is legible and the
  automated janitor can reclaim it, or (b) delete the branch. Never leave a bare
  orphan ref with no PR and no label.
- After a merge lands, `tsctl agent prune-merged <repo_key>` clears merged
  remote `agent/*`.

### Forbidden on the remote

- Scratch/backup refs: `_reb`, `backup/*`, `wip/*`, `tmp/*`, and ad-hoc
  `…-before-review-merge-*`. Backups belong in **local-only** refs or a
  `git stash` annotated with the ticket — never pushed.
- Hand-minted `agent/*` branches (that namespace is reserved for tsctl runners).

### Enforced vs. expected

Automation backstops part of this contract; the rest is review-enforced:

- `delete_branch_on_merge` across the catalog — **#489** (removes merged-PR
  heads at merge time).
- Deterministic recovery refs + automated supersession-aware prune of remote
  `agent/*` — **#488**.
- Local checkout GC (`tsctl repos gc`) for `[gone]` locals and worktree
  leftovers — **#490**.

Interactive-session branches are the one producer class those three do not fully
cover, which is why this naming + cleanup contract is mandatory, not aspirational.

## Rapid Need To Know

- `tsctl` is the control plane for cross-repo agent work.
- `repos.yaml` in the `tsctl` repo is the source of truth for repo keys, remotes, owners, and canonical `install` / `test` / `lint` commands.
- Never invent a repo key. Resolve it from `tsctl repos list` or `repos.yaml`.
- **Non-trivial work requires a GitHub issue before implementation.** Issues must be filed using the SDD spec forms (see §Issue Filing Standard below) — free-text issues without the required sections will be blocked at dispatch time.
- Close implementation issues with a commit footer such as `Closes #123` and paste validation evidence into the issue before marking it done.
- Prefer issue-driven agent dispatch over ad hoc shell work.
- For write tasks, validation is not optional. Use the repo's canonical commands from `repos.yaml`.
- Fail closed when repo metadata, runtime expectations, or governance are ambiguous.

## Issue Filing Standard (SDD Spec v1.1)

All non-trivial GitHub issues must be filed using the SDD spec issue forms. The
forms are distributed to every managed repo via `scripts/link-agent-bootstrap.sh`.

**Use the right form for the work type:**

| Work type | Form file |
|-----------|-----------|
| New feature or capability | `.github/ISSUE_TEMPLATE/enhancement-spec.yml` |
| Defect or regression | `.github/ISSUE_TEMPLATE/bug-spec.yml` |
| Research / evaluation | `.github/ISSUE_TEMPLATE/spike-spec.yml` |
| Refactor or cleanup | `.github/ISSUE_TEMPLATE/tech-debt-spec.yml` |
| Documentation | `.github/ISSUE_TEMPLATE/docs-spec.yml` |
| CI / build pipeline | `.github/ISSUE_TEMPLATE/ci-spec.yml` |

**Required sections in every spec issue (SDD v1.1):**

1. **Repository & System Clarity** — exact repos.yaml key, system/subdomain, API doc link.
2. **Existing System Audit** — concrete evidence you checked before building (grep results, file paths). Not a checkbox.
3. **Testing Strategy** — literal verification commands (curl, SELECT, make test).
4. **Related Issues & Blockers** — explicit deps; "none" only when genuinely absent.

**Conditionally required:**
- **API / Data Contracts** — required for issues labeled `api` or `backend`: exact schemas, closed enums, error-code table.
- **Implementation Constraints** — required when auth, timezone, ORM, or K8s specifics apply.

**Dispatch-time gate:** `tsctl agent dispatch` validates SDD completeness before spending
an agent run. Incomplete issues are blocked. Use `--skip-spec-check` to override
(override is logged in the audit trail).

Spec version stamp: `<!-- sdd-spec-version: 1.1 -->` in each form header.

## Issue Taxonomy Conventions

Canonical label definitions live in `docs/shared/github-label-taxonomy.yaml` in
the `tsctl` repo.

**Labels are the authoritative workflow and domain taxonomy.** Title prefixes in
brackets (e.g. `[agents]`, `[server]`, `[docs]`) identify the primary
implementation surface or owning workflow for human readability — they do not
satisfy any required label axis and must not be used as a substitute for labels.

Every non-trivial issue must carry all three required axes before implementation
or dispatch begins:

- Exactly one **type** label: `enhancement` · `bug` · `tech-debt` · `spike` · `docs` · `ci`
- Exactly one **priority** label: `p0` · `p1` · `p2` · `p3` · `p4`
- At least one **area** label (surface or domain)

**Priority tiers:**

| Label | Expectation | Stale after |
|-------|-------------|-------------|
| `p0` | Same-day response — active production/security/operator emergency | 1 business day |
| `p1` | This-week response — urgent current-iteration work | 7 calendar days |
| `p2` | Next planned slot — default-priority planned work | 14 calendar days |
| `p3` | Backlog when capacity allows — opportunistic improvement or deferred enhancement | 30 calendar days |
| `p4` | Revisit only when reprioritized — parking-lot or speculative backlog item | 90 calendar days |

**Area labels:**

- Surface (one or more): `server` · `api` · `agents` · `repos` · `k8s` · `dns` · `cli` · `wui` · `gui` · `tui`
- Domain (combinable with surface): `brain` · `security` · `deps` · `auth`

Do not use the legacy `ui` label on new issues. Map it to the specific canonical
surface labels that actually own the work (`wui`, `gui`, `tui`, or `cli`).

**Workflow labels** (`agent-review`, `agent-merge-ready`, `agent-blocked`,
`agent-superseded`, `agent-cleanup`, `agent-merged`) are optional and never
replace the required type, priority, or area axes.

Use `brain` for Digital Brain, context injection, knowledge-pack, memory, and
indexing work. For new brain issues, apply the `brain` label instead of relying
on `[brain]` in the title. Legacy issues may still carry `[brain]` in the title
but must also carry the `brain` label when touched.

## Core Operating Model

### 1. Repo Catalog

The `tsctl` repo owns the central repo catalog:

- file: `repos.yaml`
- source of truth for repo key, path, remote, owner, purpose
- canonical validation commands live here

Use:

```bash
tsctl repos list
tsctl repos check <repo_key>
tsctl repos validate
tsctl repos onboard <repo_key> ... --publish --namespace tsctl-agents
tsctl repos sync --namespace tsctl-agents
```

If a repo key is missing, stop instead of inventing one. Ask the operator to
register it with `tsctl repos onboard ... --publish` or update `repos.yaml` and
then run `tsctl repos sync --namespace tsctl-agents` before dispatch.

### 2. Work Intake

Preferred flow:

1. Create or confirm a GitHub issue.
2. Confirm the target repo key exists in `repos.yaml`.
3. Run preflight or dry-run when risk is non-trivial.
4. Dispatch or run the agent.
5. Validate with repo-defined commands.
6. Review artifacts and audit trail.

### 3. Execution Modes

- `read-only`: inspect, analyze, propose, report
- `implement`: edit files, run tests, prepare commits

Default to `read-only` for discovery when risk or scope is unclear.
Use `implement` when the issue and acceptance criteria are already defined.

## Canonical Commands

### Local runs

```bash
tsctl agent run <runner> <repo_key> <directive_or_issue_args>
```

Examples:

```bash
tsctl agent run codex lcm --issue 42 --mode implement
tsctl agent run gemini dagobah-infra prompts/security-audit.md --mode read-only
```

### Kubernetes dispatch

```bash
tsctl agent dispatch <repo_key> --runner codex --issue <N> --mode implement
tsctl agent dispatch <repo_key> --runner codex --issue <N> --dry-run
```

### Monitoring

```bash
tsctl agent jobs
tsctl agent jobs -w
tsctl agent logs <repo_key> --issue <N> --follow
tsctl agent history
tsctl agent history <run_id>
```


## Validation Contract

For implementation work:

- run the repo's canonical `install`, `test`, and `lint` commands when applicable
- keep diffs scoped to the issue objective
- do not silently skip validation for write tasks
- if validation cannot run, say why explicitly and record the gap

The canonical commands are the ones defined in `repos.yaml`, not ad hoc substitutes, unless the operator approves a deviation.

## Runtime Contract

### CI Runner Constraints — buildah, daemonless (NO DinD, NO `services:`)

Tacitsoft self-hosted CI runners (GitHub ARC scale sets, e.g.
`jmh-devel-ci-app` / `*-ci-build`) are **buildah-based and run no Docker
daemon** by design — image builds use buildah, not Docker-in-Docker (see a
repo's `production-promotion.yml` buildah path). Authoring CI for any repo,
agents MUST respect this:

- **Never add GitHub Actions `services:` containers.** They require a Docker
  daemon on the runner and fail at "Initialize containers" with
  `Value cannot be null (Parameter 'network')` / a `docker version` error.
  This is a hard constraint, not a preference.
- **Never add steps that assume `docker` / DinD** (`docker run`, `docker build`,
  `docker compose`). Use buildah for builds.
- **Database integration tests (MariaDB/MySQL/Postgres):** do NOT spin the DB
  up with `services:`. Provision it the daemonless way — a DB sidecar on the
  runner pod (request via `dagobah-infra`), `podman run` if podman is present,
  or an existing cluster DB endpoint. If none is available, file an infra need
  in `dagobah-infra` rather than introducing `services:`/DinD.
- A green run on your laptop's Docker does NOT mean it passes on these runners.
  When in doubt, mirror an existing working job in the same repo.

Regression of record: an agent run added a `services: mariadb:11.5` gate to
`turnstileops.com` that can never pass on the buildah runners. Do not repeat it.

### Current Agent Image Model

The standard agent image is pre-baked with common toolchains.
The image is selected by `tsctl` dispatch, not by each target repo.

Current notable runtime behavior:

- Node is preinstalled in the shared image.
- Python is preinstalled in the shared image.
- PHP is now multi-version in the shared image.

### PHP Runtime Selection

Current supported PHP versions in the standard agent image:

- `8.4`
- `8.3`

Selection precedence today:

1. explicit `php:` version in `repos.yaml`
2. Composer metadata inference from `composer.lock` / `composer.json`
3. default image version when no stronger signal exists

Implementation notes:

- preflight checks Composer metadata and blocks incompatible dispatches
- the job manifest injects repo-specific PHP selection into the pod
- the container entrypoint switches the active `php` binary before `tsctl` runs

Not implemented yet:

- operator override flag for forcing a PHP version during dispatch or local run
- tracked in `#112`

Catalog hardening still needed:

- explicit PHP pins should be backfilled in `repos.yaml` for managed PHP repos
- tracked in `#111`

## Secrets And Auth

Agent credentials are centrally managed and injected into pods.
Do not hardcode, log, or commit secrets.

Key command group:

```bash
tsctl agent auth status
tsctl agent auth push <runner>
tsctl agent auth pull <runner>
```

If a runner credential is missing, stop and ask the operator to push or provision it.

## Artifacts And Audit

Every run produces structured output.
Local artifacts live under `out/` and may also be uploaded to S3.

Typical artifacts:

- `summary.md`
- `changes.json`
- `validation.json`
- `audit.jsonl`
- `result.txt`

Treat `audit.jsonl` as append-only.
Do not rewrite or delete audit history as part of normal work.

## What Repo-Local Instructions Should Still Add

This shared file does not replace repo-specific context.
Each target repo should still define:

- product/domain constraints
- architectural boundaries inside that repo
- local coding style beyond the shared baseline
- deployment or compliance rules specific to that repo
- any additional validation commands not represented in `repos.yaml`

Good pattern:

- keep this shared pack as the global base
- put repo-local specifics in `.github/instructions/*.instructions.md`
- keep repo-local files short and delta-focused

## Decision Rules For Agents

When operating inside a Tacitsoft-managed repo:

- Prefer `tsctl` workflows over bespoke cross-repo shell workflows.
- Use issue-driven execution for non-trivial work.
- Prefer the smallest scoped change that satisfies the issue.
- If repo metadata and runtime requirements disagree, fail closed and surface the mismatch.
- If the target repo has its own local instructions, combine them with this file.
- When local repo instructions conflict with central control-plane safety rules, stop and escalate instead of guessing.

## Pre-PR Quality Gate (MANDATORY — no exceptions)

Before opening any pull request or pushing a final branch:

1. Run the repo's full quality gate:
   ```
   make quality
   ```
   This is not optional. Run it even if you believe no quality issues exist.

2. Run the repo's full-parity gate where present (quality + the build CI runs):
   ```
   make ci-local
   ```
   This mirrors CI verbatim: `make quality`, then docker/package builds of every
   changed surface.

3. If either fails:
   a. Read the full error output carefully.
   b. Fix every reported issue — do not suppress or skip.
   c. Re-run from the beginning.
   d. Repeat until it exits 0.

4. Do not run individual tools (ruff, black, pint) and assume the suite passes.
   Always end with `make quality` (and `make ci-local`) exit 0 as the final gate.

5. If `make quality` takes > 5 minutes and you are iterating fixes, run only the
   failing sub-target (e.g. `make python-quality`) between iterations, but always
   run the full gate as the final pass before push.

6. No-bypass clause: `SKIP=`, `--no-verify`, and build-skip env vars are for local
   iteration only — NEVER for a PR push.

7. 3-attempt-then-handoff: if the gate is still red after 3 honest fix attempts,
   stop and document a handoff (what's failing, what you tried) rather than
   pushing red or bypassing.

---

## Current Temporary Gaps

This file is a bridge, not the final state.
Current known gaps:

- no brain-backed automatic context injection yet
- no automatic distribution of this file into every managed repo yet
- no operator PHP override flag yet
- not every managed PHP repo is explicitly pinned in `repos.yaml`

Tracked follow-on issues:

- `#111` Backfill explicit PHP version pins in repos catalog
- `#112` Add PHP version override to agent dispatch and run
- `#113` Add shared cross-repo agent bootstrap pack
- `#114` Design brain-backed context injection for repo agent runs

## Change Log

### 2026-06-09

- Replaced duplicate "Pre-Push Quality Gate" sections with a single authoritative "Pre-PR Quality Gate (MANDATORY — no exceptions)" section encoding the Prong 1 canon from #251: mandatory `make quality` + `make ci-local`, iterate-until-exit-0, 3-attempt-then-handoff rule, no-bypass clause.
- Dropped the previous surface-mapping guidance that gave agents too much discretion (root cause of recurring CI gate failures on agent PRs).
- Added `## Issue Filing Standard (SDD Spec v1.1)` section establishing the SDD issue forms as the required filing standard for all non-trivial issues across managed repos.
- SDD spec v1.1 adds six new sections to all issue forms: Repository & System Clarity, Existing System Audit, API / Data Contracts, Implementation Constraints, Testing Strategy, Related Issues & Blockers.
- `tsctl agent dispatch` now validates SDD spec completeness before dispatching; incomplete issues are blocked (use `--skip-spec-check` to override). Verdict is recorded in the run's `audit.jsonl`.
- `scripts/link-agent-bootstrap.sh` extended to provision `.github/ISSUE_TEMPLATE/` forms and reconcile the label taxonomy via `gh label` to every repo in `repos.yaml`. Coverage report gains ISSUE_TEMPLATES and LABELS columns.
- Tracked as #255 (input gate), paired with #251 (output / CI-parity gate).

### 2026-06-06

- Added `## Pre-Push Quality Gate (MANDATORY)` section with five-step self-discovery protocol: read instruction files, inventory build-file targets, map changed files to surfaces, run all applicable gates before push, and re-run the full suite after every fix.
- Covers PHP (Pint + PHPStan), Python (ruff + isort + black + mypy), JS/Vue (eslint + build), and K8s YAML surfaces with exact commands per surface.
- Addresses recurring CI gate failures on agent PRs caused by agents not treating instruction-file quality sections as mandatory pre-push checklists (tracked in tacitness/tsctl#244).

### 2026-04-24

- Added the first shared cross-repo bootstrap pack as a temporary knowledge shim.
- Documented the issue-before-code workflow and `repos.yaml` validation contract.
- Documented the new multi-PHP agent runtime model with PHP `8.3` and `8.4`.
- Documented the current selection precedence: repo pin, Composer inference, then default image version.
- Added follow-on issue references for PHP pin backfill, operator override, shared bootstrap evolution, and brain-backed context injection.
