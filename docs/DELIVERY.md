# CI/CD/RO and release delivery

CI/RO means continuous integration under a read-only trust contract: build and test source without hardware, deployment credentials,
repository writes, or host control. CD publication is a later, narrowly privileged stage.

## Pipeline

```text
pull request ──> hosted CI/RO + dependency review + PR-title policy
                      │
                      └─ merge to main ──> trusted isolated scans + SonarQube
                                                   │
                                      validated CI workflow_run
                                                   │
                                      annotated SemVer tag
                                                   │
                     self-hosted read-only build/test/scan/package
                                                   │ artifact + checksums
                     hosted protected publish/attest/GHCR/ECR/GitHub Release
```

## Workflow contracts

- `ci.yml`: hosted, untrusted-safe, `contents: read`, no secrets, no hardware, `make ci-ro`.
- `metadata.yml`: validates issue metadata and Conventional Commit PR titles from trusted policy.
- `trusted-ci.yml`: repo-scoped self-hosted runner, trusted main/manual only, runtime isolation plus extended scanners.
- `sonarqube.yml`: trusted runner and protected Sonar token; imports repository assembly rules and waits for the gate.
- `auto-version.yml`: runs only after successful CI on main and tags the exact validated SHA.
- `release.yml`: validates tag provenance, reruns quality/scanners/Sonar, creates package/SBOM/image archive, crosses an artifact trust
  boundary, re-verifies checksums, attests, publishes GHCR and private ECR, then creates the GitHub Release from a hosted protected job.
- `scorecard.yml`: hosted OpenSSF supply-chain assessment and SARIF upload.

All third-party Actions are full-SHA pinned. Jobs have explicit permissions, timeouts, and concurrency. Build jobs cannot publish.

## Artifacts

`make release-artifacts VERSION=X.Y.Z` produces:

- `frame-X.Y.Z-linux-x86_64.tar.gz` with binary and documentation;
- SHA-256 checksum files;
- SPDX JSON and CycloneDX JSON SBOMs;
- a minimal scratch OCI/Docker archive containing only the static binary.

The image is non-root by default. Runtime hardware access is never baked into or inferred by the image. GHCR receives `X.Y.Z`,
`sha-<full-commit>`, and `latest`; private ECR receives only immutable `vX.Y.Z` and `sha-<full-commit>` tags. Deployments select a
digest or immutable SHA/version, never `latest`. OCI labels record the source commit, clean/dirty worktree state, and exact embedded
binary SHA-256; governed tagged builds must report `source-state=clean`. See `ECR_PUBLISHING.md` for the OIDC and infrastructure
contract.

## Versioning

Annotated `vMAJOR.MINOR.PATCH` tags are canonical. `VERSION` supplies the no-tag bootstrap floor (`0.0.141`); it is not rewritten on
each release. `scripts/version.sh` derives current/dev/next values and verifies a release tag points to HEAD.

Automatic bump priority since the prior tag:

| Conventional Commit | Bump |
|---|---|
| `type!:` or `BREAKING CHANGE:` | Major |
| `feat:` | Minor |
| `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert` | Patch |
| No recognized prefix | No tag |

This matches the established `tsctl` tag-driven practice while avoiding version-file merge commits.

## Failure and rollback

- A failed quality/scanner/Sonar/checksum/attestation or ECR-contract validation step publishes nothing.
- Tags are immutable release identities; do not retag. Fix forward with a new patch version.
- GitHub Releases and version/SHA images remain immutable. `latest` may be moved back only through a documented emergency release
  action after the underlying digest is verified.
- A registry failure can leave an already pushed immutable tag even though no GitHub Release was created. Record its digest, never
  delete or retag it to conceal the partial publication, and fix forward or resume only after proving every destination matches.
- Runner/image/scanner failures are delivery incidents, not reasons to bypass gates or grant broader privileges.

## Cross-repository follow-up

Dagobah must supply the immutable `frame-ci-build` runner image/registration through
[issue #431](https://github.com/tacitness/dagobah-infra/issues/431), plus the isolated ECR repository/OIDC role through
[issue #429](https://github.com/tacitness/dagobah-infra/issues/429) and `ECR_PUBLISHING.md`. `tsctl` must add the repo catalog entry and
validate its shared governance rollout. Those are separate reviewed changes in their owning repositories.
