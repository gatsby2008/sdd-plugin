# ADR

Captures a technical decision as an Architecture Decision Record — a short,
immutable document that records the context, the decision, and the consequences —
and **stores it directly in the central ADR registry** (no copy is left in the
service repo).

ADRs are never edited. If a decision changes, a new ADR supersedes the old one,
preserving the full history of why the system is the way it is.

---

## Usage

```bash
# Start with a description
/sdd:doc-adr "use PostgreSQL instead of Redis for circuit breaker state"

# Extract decisions from a Jira ticket
/sdd:doc-adr PROJ-17097

# Interactive — skill asks for the decision
/sdd:doc-adr

# Show the ADRs registered for this repo's service
/sdd:doc-adr list
```

---

## What It Produces

```
~/.claude/adr-registry/<service>/PROJ-17097-ADR-001-use-postgresql-circuit-breaker.md
```

(Or under `$CLAUDE_DOC_HOME/adr-registry/` for a team-shared registry.) Query it with
`/sdd:ask`.

File name format: `<TICKET>-ADR-NNN-<slug>.md` (ticket first, then 3-digit ADR number, then slug). Use `NOTICKET` as the prefix if no ticket exists. The ADR counter is service-wide — it doesn't reset per ticket.

```markdown
# ADR-003: Use PostgreSQL Instead of Redis for Circuit Breaker State

## Status
Accepted

## Context
The DataVendor circuit breaker needs to persist its OPEN/CLOSED state across all
service replicas so that a single Access Denied event halts traffic on every
instance immediately...

## Decision
Use PostgreSQL with a singleton row and pessimistic write lock.
Redis was ruled out because it would introduce a new infrastructure dependency
for a single use case...

## Consequences
- No new infrastructure dependency — PostgreSQL is already required
- Every DataVendor call incurs one extra DB read for isOpen()
- Circuit state survives restarts and replica scaling

## Related
- Jira: [PROJ-17097](https://your-company.atlassian.net/browse/PROJ-17097)
- MR: [!127](https://gitlab.com/acme/services/creditbureau-service/-/merge_requests/127)
```

---

## Why a central ADR registry

Confluence gets stale. Jira tickets get closed. ADRs are the durable record of *why*.

Keeping them in one central registry — rather than scattered across every repo's
`docs/adr/` — means `/sdd:ask` can answer "why PostgreSQL and not Redis?"
across every service at once, without cloning each repo.

---

## Independent of the SDD pipeline

This skill has no dependency on `.specwork/` artifacts. It can be used standalone
or alongside the SDD pipeline at any point in the development cycle.
