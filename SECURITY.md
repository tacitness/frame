# Security policy

## Reporting a vulnerability

Use a [private GitHub security advisory](https://github.com/tacitness/frame/security/advisories/new)
for exploitable vulnerabilities. Do not open a public issue containing an exploit, credential,
private environment detail, or unpatched reproduction. Include the affected commit, impact,
preconditions, a minimal private reproduction, and suggested mitigations when known.

Public hardening work that does not disclose an exploitable defect may use the Security issue form.

## Supported versions

`frame` is pre-1.0 experimental software. Security fixes target the latest `main` and the newest
published version unless a release advisory states otherwise.

## Current security boundary

The binary is static and unprivileged by default, but display and input modes can access sensitive
hardware. Ordinary operation should run as a dedicated unprivileged user with only explicitly
required device groups. Never expose DRM, evdev, KVM, a container socket, or root to CI.

The Unix X11 socket is owner-only (`0700`) because setup credentials are not yet validated. This is
a single-uid containment baseline, not cross-user authentication: run frame and its clients as the
same dedicated unprivileged uid. `frame-policy/SEC001` blocks any return to a world-connectable socket
until real authentication or verified peer credentials exist. See `docs/SECURITY_MODEL.md`.

## Security gates

- `make quality`: git-secrets working-tree scan, syntax/policy, text, workflow, ELF, protocol, regression, fuzz, reproducibility.
- `make ci-local`: quality plus full-history git-secrets, redacted Gitleaks, and local security checks.
- `make ci-self-hosted`: isolated-runner checks plus Trivy, Syft/Grype, and secret scanning.
- SonarQube imports the repository-owned assembly/workflow rules and blocks gated releases.

GitHub secret scanning, push protection, Dependabot alerts/security updates, and private vulnerability reporting are enabled as
server-side backstops. GitHub currently reports the account-gated non-provider-pattern and provider-validity options as disabled for
this user-owned repository; mandatory repository `git-secrets` and Gitleaks scans cover that gap locally and in CI. Never place
credentials in allowlists; only canonical public fixtures or a narrowly anchored rule-definition path may be exempted.
