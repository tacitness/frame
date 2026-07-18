# Agent operating contract

This file is authoritative for every coding agent and every path in this repository.
Adapter files may add tool-specific mechanics but may not weaken this contract.

## Mission

Maintain `frame` as a small, auditable x86-64 NASM X11 server. Correct protocol
behavior, client isolation, recovery, and hardware safety outrank compatibility shortcuts
and speculative optimization. Preserve the original developer's direct, documented style
while adding the checks needed for safe collaboration.

## Non-negotiable safety

- Ordinary tests are headless. Start `frame` with a numeric isolated display,
  `--noinput`, and a temporary `HOME`.
- Never run `--display`, `--modeset`, or `--watch-input` in hooks, CI, fuzzing,
  benchmarks, or autonomous agent sessions.
- Never use root, `sudo`, `/dev/dri`, `/dev/input`, `/dev/kvm`, a Docker socket, or
  the user's live X socket in automated work.
- Hardware acceptance is a human-controlled manual test from a recoverable TTY. Read
  `tests/manual/README.md` first.
- Treat every client byte, command-line value, environment value, config byte, kernel
  record, and descriptor result as untrusted. Check size, range, overflow, and syscall
  results before use.
- Do not expose secrets in source, issues, logs, fixtures, artifacts, comments, or prompts.
- Do not claim a test, benchmark, scanner, or hardware result that was not actually run.

## Work intake and GitHub metadata

Non-trivial work starts from a specification issue. The issue must have:

- a canonical `[area]` title (or `[epic:slug]` for an epic);
- exactly one type and priority label;
- at least one area label;
- one parent epic and the same release milestone as that epic;
- one release-impact label when milestoned;
- measurable acceptance criteria, tests, non-goals, and safety constraints.

Use `docs/GITHUB_GOVERNANCE.md` and `ops/github/policy.json`. Do not silently expand an
issue into another protocol area, hardware path, or release goal.

## Required development loop

1. Read the issue, this file, and the relevant documentation.
2. Inventory existing labels, tables, handlers, tests, and cleanup paths before adding one.
3. For protocol behavior, consult current `xorgproto` definitions and the canonical X.Org
   server implementation. Record any deliberate incompatibility.
4. Add or identify the lowest-layer failing test. A bug fix requires a regression test.
5. Make the smallest coherent change. Preserve unrelated work and generated data.
6. Run focused tests, then `make quality`. Run `make ci-local` when scanner databases are
   available. Record exact commands and limitations.
7. Review all changed control-flow, lengths, ownership, cleanup, and error paths manually.
8. Use a Conventional Commit/PR title. Let validated `main` create the SemVer tag.

## Assembly structure and style

- Keep `BITS 64`, `DEFAULT REL`, and the explicit `.bss`, `.rodata`, and `.text` sections.
- Use four spaces; never tabs or trailing whitespace in NASM source.
- Use `UPPER_SNAKE_CASE` for constants, `snake_case` for global labels/data, and
  `.local_labels` within one routine. Macro-local labels use NASM's `%%` form.
- One routine owns one clear contract. Its header documents inputs, outputs, preserved or
  clobbered registers, state touched, wire layout, and error behavior.
- Prefer symbolic syscall, protocol, ioctl, mask, record-size, and offset constants over
  unexplained literals. Cite the ABI source next to kernel encodings.
- Keep hot-path comments focused on invariants and why; do not narrate every instruction.
- Keep fixed tables sorted or indexed as their consumer expects. Derive lengths with
  NASM expressions (`equ`, `$ - label`, `%strlen`) rather than duplicated manual counts.
- Align code/data only for an ABI requirement or a measured benefit. Document the reason.
- Preserve stack balance across every branch. Keep the stack 16-byte aligned at any
  interface that requires it. This binary has no libc ABI, so routine register conventions
  must be explicit and consistent locally.
- Check negative syscall returns before treating `rax` as a count, pointer, or descriptor.
- Do not add privileged instructions, legacy `int 0x80`/`sysenter`, self-modifying code,
  executable data, runtime relocations, or writable/executable segments.

## X11 request checklist

Before a handler reads a field or variable payload:

1. Convert the 4-byte-unit request length with overflow-safe arithmetic.
2. Require the exact fixed size or a documented minimum size.
3. Validate count-derived and padded sizes without wraparound.
4. Validate enum, mask, resource ID, ownership, and table capacity.
5. Distinguish reply-bearing requests from void requests. Never silently drop a request
   whose client is waiting for a reply.
6. Increment the per-client sequence for every request and copy it to replies/errors/events.
7. Return the protocol-defined error where implemented; otherwise close only the offending
   client on an unsafe stream state. Never crash or desynchronize the server.
8. On disconnect, release every resource, selection, subscription, grab, mapping, backing,
   and redirect claim owned by that client. Prove slot reuse starts clean.

Little-endian clients are the current supported contract. Big-endian setup is rejected
cleanly and tested. Adding swapped clients requires a complete swap-dispatch design, not
isolated byte swaps.

## Security baseline

The X11 Unix socket is owner-only (`0700`), and setup authentication fields are drained but
not validated. `frame-policy/SEC001` blocks any world-connectable socket unless an explicit
authentication or verified-peer call exists. Do not weaken this mode or add a keyword-only
exception. Cross-user support requires a complete credential lifecycle and negative tests.

Use allowlists, bounded lengths, least privilege, fail-closed errors, and descriptor-based
operations. Be especially suspicious of `/tmp` races, config paths, inherited environment,
SysV shared memory, resource ownership, and arithmetic involving width × height × bpp.

## Testing expectations

- `make test-unit`: pure encoding, padding, policy, and table logic.
- `make test-static`: linked ELF, section, NX, W^X, relocation, and memory-budget contract.
- `make test-integration`: live headless setup, replies, fragmentation, and multi-client flow.
- `make test-regression`: a named test for every repaired failure.
- `make test-fuzz`: bounded deterministic malformed-input seeds.
- `make test-reproducible`: two clean byte-identical builds.
- `make quality`: required local and hosted read-only gate, including git-secrets tree scan.
- `make ci-local`: quality plus full-history git-secrets, redacted Gitleaks, and security checks.

Extend helpers in `tests/lib/`; do not copy ad-hoc socket lifecycle code into each test.
Every server test must prove cleanup and leave no `/tmp/.X11-unix/XN` socket. Timing-based
tests need a monotonic deadline and useful captured logs.

Never print a suspected credential to logs. Keep `scripts/git-secrets-scan.sh`
output-suppressed, use the versioned AWS/Bedrock patterns, and pair git-secrets
with Gitleaks and GitHub secret scanning/push protection.

## Optimization contract

Correctness and observability come first. Before changing instructions or layout:

- identify a representative workload and a specific hotspot;
- capture a repeatable baseline with `make bench-protocol`, `perf`, or a small extracted
  `llvm-mca` region as appropriate;
- consider syscall count, cache footprint, branch prediction, code size, dependency chains,
  and total application behavior—not only an isolated instruction latency;
- preserve a readable implementation and add a regression test;
- report noise controls, CPU/tool versions, sample count, and before/after distributions.

Never gate ordinary PRs on noisy wall-clock thresholds. A performance regression gate needs
a pinned runner, reviewed baseline, tolerance, and repeat confirmation.

## Delivery and dependencies

- Third-party GitHub Actions are pinned to full commit SHAs. Tool downloads use fixed
  versions and verified checksums.
- Pull requests use GitHub-hosted, read-only jobs. Self-hosted `frame-ci-build` jobs run only
  trusted `main`, tags, or manual dispatch after opt-in.
- Build/package jobs cannot publish. The hosted publish job alone receives write scopes.
- Release tags are annotated `vMAJOR.MINOR.PATCH`; artifacts use version and immutable
  `sha-<commit>` identities, checksums, SBOMs, scans, and attestations.
- Prefer rootless Buildah on self-hosted runners. Do not introduce Docker-in-Docker or mount
  a host container socket.

## Agent roles and review

- Auditor: maps existing behavior, protocol sources, invariants, risks, and missing tests;
  does not implement while acting only as auditor.
- Implementer: works from an approved spec, adds tests first, and records exact validation.
- Reviewer: assumes every length, branch, resource, syscall, and cleanup claim may be wrong;
  checks diff and tests independently.
- Optimizer: requires a measured hotspot and cannot weaken correctness, security, or clarity.
- Orchestrator: keeps epic/milestone/dependency state accurate and prevents scope creep.

An agent must hand off uncertainties and unrun checks explicitly. Approval from another
agent is not a substitute for maintainer review on security, release, or hardware changes.


<!-- tsctl-agent-bootstrap-reference:start -->

## Shared tsctl Agent Bootstrap

Also read `./tsctl-agents-bootstrap.md` for Tacitsoft agent dispatch rules,
`tsctl` interaction patterns, `repos.yaml` contract expectations, issue
taxonomy, review/merge workflow, runtime selection behavior, validation flow,
post-agent PR/branch hygiene, and shared control-plane operating rules.

Treat it as additive control-plane context. Keep this repo's local product,
domain, architecture, and coding instructions authoritative for repo-specific
behavior.

After agent runs complete, inventory PR and branch sprawl before creating any
new branch or PR:

```bash
gh pr list && git fetch && git branch && git branch -r
```

If a PR already exists for the issue work, review, resolve, and merge that
existing PR. Create a new branch or PR only when no PR exists for completed
work, or work never reached a PR and needs branch recovery.

<!-- tsctl-agent-bootstrap-reference:end -->
