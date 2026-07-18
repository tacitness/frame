# Contributing

Read `AGENTS.md`, `docs/ASSEMBLY_STANDARDS.md`, `docs/TESTING.md`, and the relevant issue specification before changing code.

## Local setup

Required core tools: NASM 2.16+, binutils, Make, Python 3, ShellCheck, yamllint, actionlint, pre-commit, Git, and `git-secrets`.
Security/release work additionally uses Gitleaks, Trivy, Syft, Grype, rootless Buildah, AWS CLI, and SonarScanner. Install the pinned
`git-secrets` build with `sudo scripts/install-git-secrets.sh` when it is not already supplied by the workstation image.

```bash
make all
make install-hooks
make quality
```

The versioned hooks make `git-secrets` mandatory and use repository-owned AWS/Bedrock patterns without writing secret rules into local
Git config. Prepared/final commit messages and staged content are scanned; pre-push runs `make ci-local`, including full-history
`git-secrets` and Gitleaks scans. Matched content is suppressed so a failed scan cannot print a newly discovered credential. You may
run focused layers while developing, but do not bypass the final gate.

## Work and review

- Start non-trivial changes from the correct issue form and complete the label/epic/milestone policy.
- Keep one outcome per branch/PR and preserve unrelated work.
- A bug fix needs a regression test; a protocol capability needs positive/boundary/malformed/multi-client/cleanup coverage as applicable.
- Automated tests are headless and use `--noinput`; never run hardware modes in an agent or CI session.
- Use a Conventional Commit subject/PR title such as `fix(protocol): reject an oversized setup request`.
- Include exact validation output/commands and disclose unrun manual checks. Do not assert compatibility from compilation alone.

## Useful commands

```bash
make test-unit
make test-static
make test-integration
make test-regression
make test-fuzz
make test-reproducible
make git-secrets-history
make quality
make ci-local
make bench-protocol
make sonar-report
```

`make ci-self-hosted`, Sonar analysis, packaging, and publication belong on the governed runner/workflows. See `docs/DELIVERY.md`.

## Source and optimization evidence

Use current xorgproto and canonical X.Org server source for X11 behavior. Record deliberate deviations. For low-level optimization, first
identify a representative hotspot, retain a correctness oracle, and report before/after distributions and environment. See
`docs/XORG_SOURCE_AUDIT.md`, `docs/REFERENCE_NOTES.md`, and `docs/PERFORMANCE.md`.
