# Agent role map

`AGENTS.md` is authoritative. The profiles in `.github/agents/` specialize one stage of the same workflow:

| Role | May edit | Required output |
|---|---:|---|
| Auditor | No | Evidence-backed findings and missing tests |
| Orchestrator | No | Ordered epic/milestone/dependency plan |
| Implementer | Yes | Scoped code, tests, and exact validation |
| Reviewer | No | Independent findings or explicit clean review |
| Optimizer | Yes, with approved scope | Baseline, hypothesis, measurements, and semantic proof |

Never use the same agent role to both implement and provide the only approval for security, release, or hardware work.
