# SonarQube assembly quality gate

## Design decision

SonarQube does not provide a native NASM/assembly analyzer. `frame` therefore uses SonarQube for centralized issue history, security
text analysis, visibility, and release gating while the repository owns the assembly/workflow rules in
`scripts/assembly_policy.py`. The script emits the current generic external-issue format to
`out/sonar/frame-policy.json`; `sonar-project.properties` imports it.

This is the effective assembly profile. External rules cannot be activated/deactivated through a Sonar Quality Profile and are not
shown on the normal Rules page. Change a rule only through reviewed source and tests in this repository. If native Quality Profile
management becomes mandatory, that requires a maintained Sonar language/analyzer plugin, not a property-file trick.

Primary documentation:

- [Supported languages](https://docs.sonarsource.com/sonarqube-community-build/analyzing-source-code/languages)
- [Generic external issue format](https://docs.sonarsource.com/sonarqube-server/2026.1/analyzing-source-code/importing-external-issues/generic-issue-import-format)
- [Quality gates](https://docs.sonarsource.com/sonarqube-server/2026.1/quality-standards-administration/managing-quality-gates/introduction-to-quality-gates)
- [Text/secret inclusions](https://docs.sonarsource.com/sonarqube-server/analyzing-source-code/languages/secrets)

## Versioned policy

Current rules cover privileged/legacy instructions, required NASM model declarations, duplicate control transfer, immutable Actions,
dangerous workflow triggers, untrusted self-hosted execution, automated hardware modes, and exposure of an unauthenticated X socket.

`SEC001` is a blocking local and external rule. The current owner-only (`0700`) socket satisfies the single-uid baseline; changing it
back to world-connectable fails local lint, CI, and the imported Sonar gate unless a real authentication or verified-peer path is present.

Run locally:

```bash
make sonar-report
SONAR_HOST_URL=https://sonar.example.test SONAR_TOKEN=... make sonar
```

Never put the token in a command history, config file, issue, or log. Prefer an ephemeral environment injection.

## Project and gate setup

1. Run a supported SonarQube Server and scanner capable of the 10.8+ generic report format.
2. Create project key `tacitness_frame`, name `frame`, default branch `main`.
3. Create and assign custom gate `Frame Assembly Gate` from `ops/sonarqube/frame-quality-gate.json`:
   - new-code issue count greater than zero fails;
   - new security-hotspots-reviewed below 100% fails.
4. Use **Previous Version** for main-branch new code. The workflow passes the tag-derived `sonar.projectVersion`.
5. Do not add coverage or duplication conditions yet. NASM has no trustworthy coverage import in this repository, and fabrication is
   worse than a visible missing metric.
6. Create a project analysis token with no administrative scope. Store it as `SONAR_TOKEN` in protected GitHub environment
   `sonarqube`; store `SONAR_HOST_URL` as a repository/environment variable.
7. Keep `SONARQUBE_ENABLED=false` while proving connectivity and inspecting the first analysis. Confirm the imported report is clean
   before enabling the release gate. Any baseline exception needs a security issue, owner, rationale, expiry/review milestone, and
   compensating control.
8. Set `SONARQUBE_ENABLED=true` only after the gate is assigned and `FRAME_SELF_HOSTED_ENABLED=true` only after the isolated runner
   contract is satisfied.

The Sonar workflow runs only trusted `main`/manual source on `frame-ci-build`; forked pull requests never receive the token or touch
the self-hosted runner. Deterministic `make quality` remains the required PR blocker. The release workflow reruns Sonar and waits for
the gate before packaging.

## Troubleshooting

- “External issue file not indexed”: confirm `sonar.text.inclusions.activate=true`, the `.asm` inclusion, exclusions, base directory,
  and exact `filePath` values in the JSON.
- Every issue appears as maintainability/medium: the server is too old for the current rule/impact format or the report schema is wrong.
- Scanner succeeds while the workflow passes a failed gate: verify `sonar.qualitygate.wait=true`, timeout, and token permission.
- Rules do not appear in Quality Profiles: expected for external issues; inspect the JSON, analysis issues, and repository policy.
- No analysis job: both opt-in variables must be the string `true` and the repo-scoped runner must be online with `frame-ci-build`.
