# Self-hosted runner contract

## Trust and scope

`tacitness` is a user account, so `frame` uses a repo-scoped runner. Its unique scheduling label is `frame-ci-build` in addition to
`self-hosted`, `Linux`, and `X64`. Do not reuse a broad label that lets another repository schedule onto this trust boundary.

The runner is opt-in through repository variable `FRAME_SELF_HOSTED_ENABLED`. Until a runner is provisioned and validated, trusted
jobs skip and releases fail closed.

## Required isolation

- Ephemeral job environment or reliably scrubbed workspace; one job at a time.
- Non-root identity, ordinary umask, no passwordless elevation.
- No `/dev/dri`, `/dev/input`, `/dev/kvm`, `/dev/mem`, host Docker/Podman socket, or other host control plane.
- Rootless Buildah for image construction; no privileged Docker-in-Docker service.
- No untrusted PR/pull_request_target trigger and no fork secrets.
- Network only to GitHub, package/scanner sources approved by infrastructure policy, GHCR, ECR/STS, and internal SonarQube as needed.
- Immutable runner image pinned by digest; rebuild/scan/promote rather than mutate packages during a job.

`scripts/check-runner-safety.sh` enforces the runtime subset it can observe. Infrastructure policy must enforce the rest.

## Tool image contract

`scripts/check-toolchain.sh` fails fast. The release image needs:

- Bash, Git, Make, NASM 2.16+, binutils, Python 3;
- ShellCheck, yamllint, actionlint, pinned awslabs/git-secrets;
- Gitleaks, Trivy, Syft, Grype;
- rootless Buildah;
- AWS CLI for OIDC-backed ECR login/publication;
- SonarScanner CLI;
- standard `tar`, `gzip`, `sha256sum`, `readelf`, `awk`, `sed`, and `find`.

Pin tool versions and verify downloaded checksums in the runner image build. Do not silently `sudo apt install` missing tools inside a
self-hosted job.

## Dagobah-infra integration finding

The current `dagobah-runner-python-go-native` base already provides native compilers/build tools and the broader base provides
Buildah/Podman, file, Make, Syft, Grype, and Trivy. It does not currently guarantee NASM, ShellCheck, actionlint, Gitleaks,
git-secrets, yamllint, pre-commit, or SonarScanner. Add a `frame-ci-build` overlay/image (or explicitly extend the governed native
image), pin it by digest, scan it, and provision a repo registration for `tacitness/frame`.

[Dagobah issue #431](https://github.com/tacitness/dagobah-infra/issues/431) is the SDD and human-approval boundary for that image and
runner registration work. It is intentionally separate from the ECR/OIDC infrastructure in issue #429.

The shared `tsctl` bootstrap documentation describes daemonless Buildah/no services, while some current runner values/workflows use
Docker-in-Docker. Treat that as infrastructure drift; `frame` follows the daemonless contract.

## tsctl catalog integration

After the frame changes land, add an SDD-backed entry to the canonical `tsctl/repos.yaml` in that repository, for example:

```yaml
- key: frame
  path: /data/src/tacitsoft/infrastructure/frame
  remote: https://github.com/tacitness/frame.git
  branch: main
  owner: platform
  purpose: Pure x86_64 NASM X11 display server for CHasm
  install: make all
  test: make test
  lint: make lint
  quality: make quality
```

Validate the actual catalog schema and run the `tsctl` quality gate there; do not edit another repository as an incidental frame change.

## Rollout

1. Merge the frame workflows and runner contract.
2. Build, scan, and publish the immutable Dagobah runner image.
3. Provision the repo-scoped ephemeral runner with `frame-ci-build` and no device/socket mounts.
4. Manually dispatch trusted CI with the opt-in variable still false to confirm it skips.
5. Set `FRAME_SELF_HOSTED_ENABLED=true`, dispatch, and verify toolchain/safety/quality/security.
6. Configure SonarQube and enable it separately.
7. Only then permit a release tag.
