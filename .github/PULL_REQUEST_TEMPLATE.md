## Outcome

Describe the user/protocol/maintainer result, not only the edited files.

Closes #
Parent epic: #
Milestone:
Release impact: major / minor / patch / none

## Contract and risk

- Protocol, ABI, or state invariant changed:
- Bounds, ownership, and cleanup behavior:
- Security or compatibility impact:
- Explicit non-goals:

## Validation

- [ ] A focused unit/static/integration/regression test protects the change.
- [ ] `make quality` passes.
- [ ] `make ci-local` passes when scanner databases are available.
- [ ] Malformed and boundary inputs were considered.
- [ ] Documentation and compatibility notes are updated.

Commands and evidence:

```text
make quality
```

## Hardware safety

- [ ] Automated tests use `--noinput`, a temporary `HOME`, and an isolated display.
- [ ] This change does not require automated DRM/evdev access or elevated privileges.
- [ ] If hardware behavior changed, manual evidence and recovery steps are linked here.

## Agent disclosure

- [ ] Agent-generated changes were reviewed against `AGENTS.md`; claims are backed by commands or sources.
