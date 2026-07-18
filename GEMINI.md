# Gemini adapter

`AGENTS.md` is the canonical repository contract and must be read before work begins.

Ground X11 claims in xorgproto and canonical X.Org server source. Ground optimization
claims in measurements. Keep automated work headless and unprivileged. Do not infer that
an existing handler is safe merely because a desktop client happens to tolerate it.

Report focused validation evidence and remaining risks at handoff.


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
