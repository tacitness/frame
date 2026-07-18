---
description: 'GitHub Actions, self-hosted runner, SonarQube, and release standards'
applyTo: '.github/**/*.yml,.github/**/*.yaml,ops/**,Dockerfile,Makefile,scripts/*.sh'
---

# Delivery instructions

- Pin every third-party Action to a full commit SHA with a version comment.
- Declare least permissions, timeout, concurrency, and `persist-credentials: false` unless a job must push.
- Pull requests run only on hosted disposable runners with no repository secrets.
- Self-hosted jobs accept only trusted `main`, version tags, or manual dispatch and use `frame-ci-build`.
- Build jobs are read-only. Only the final hosted publisher gets contents/packages/id-token write access.
- Prefer rootless Buildah. Never mount a host Docker socket or use privileged Docker-in-Docker.
- Verify checksums on both sides of artifact transfer; generate SBOMs, scan, attest, and publish immutable version/SHA tags.
- Sonar credentials are available only through the protected `sonarqube` environment.
