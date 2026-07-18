# Claude adapter

Read and follow `AGENTS.md` in full. It is authoritative.

Before editing, summarize the issue contract, the source labels/routines involved, and the
lowest-layer test that will prove the change. Use focused edits; do not reorganize the
monolithic assembly file unless the issue explicitly approves that architecture change.

Never invoke hardware-affecting frame modes. End the task with exact commands run,
results, unrun/manual checks, and any protocol or security uncertainty.


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
