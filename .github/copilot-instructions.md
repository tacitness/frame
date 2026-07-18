# Copilot repository instructions

Follow `/AGENTS.md` as the authoritative contract.

For every assembly suggestion, preserve NASM syntax, `DEFAULT REL`, register/stack balance,
request-size validation, per-client ownership, protocol sequence behavior, and disconnect
cleanup. Prefer existing helpers and local-label conventions. Suggestions must not introduce
root, hardware access, mutable Actions, secrets, or unbounded test inputs.

Bug fixes need regression tests. Optimizations need representative before/after measurements.


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
