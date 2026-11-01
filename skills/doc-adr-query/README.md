# ADR Query

Answers architecture-decision questions by reading every ADR under `~/.claude/adr-registry/*/` and synthesizing an answer from the combined knowledge. The registry is populated by `/sdd:doc-adr` runs from each service (which create and store each ADR in one step).

## Usage

```bash
/sdd:doc-adr-query why did consumer-portal pick PostgreSQL for circuit-breaker state?
/sdd:doc-adr-query which services have superseded ADRs?
/sdd:doc-adr-query show every ADR that references Cognito
```

Pass any free-text decision question as the argument.

## Example queries

Group your queries by intent. Each category below maps to a query type the skill knows how to answer — adapt the templates to the service, technology, or pattern in your own registry.

### Decision lookup — why did we pick X over Y?

```bash
/sdd:doc-adr-query why did consumer-portal pick PostgreSQL for circuit-breaker state?
/sdd:doc-adr-query why did leads-service adopt shlink for URL shortening?
/sdd:doc-adr-query which ADRs explain why we chose Feign over WebClient?
```

### Topic scan — which ADRs touch a technology or concept?

```bash
/sdd:doc-adr-query show me every ADR about retries
/sdd:doc-adr-query which ADRs reference Cognito?
/sdd:doc-adr-query find decisions involving SQS dead-letter queues
/sdd:doc-adr-query which ADRs mention PII handling?
```

### Status filter — which decisions are still active?

```bash
/sdd:doc-adr-query which ADRs have been superseded?
/sdd:doc-adr-query list every deprecated decision and its replacement
/sdd:doc-adr-query show the supersedes chain for circuit-breaker decisions
```

### Cross-service patterns — do multiple services agree?

```bash
/sdd:doc-adr-query do multiple services persist state in Postgres?
/sdd:doc-adr-query which services have adopted optimistic locking?
/sdd:doc-adr-query are retry policies consistent across the registry?
```

### Consequence search — which decisions traded off X?

```bash
/sdd:doc-adr-query which decisions added a DB read on the hot path?
/sdd:doc-adr-query which ADRs accepted increased latency in exchange for durability?
/sdd:doc-adr-query find decisions that expanded our ops footprint
```

### Discovery — what's in the registry?

```bash
/sdd:doc-adr-query summarize the architectural decisions per service
/sdd:doc-adr-query list every ADR title across the registry
/sdd:doc-adr-query which Jira tickets are referenced in ADRs?
```

Every answer cites the source as `<service>/<ADR-file>` — ADRs are immutable, so a stale answer means a new ADR should supersede the old one (run `/sdd:doc-adr` in that service).

## What it does

1. Lists every service subdir under `~/.claude/adr-registry/`.
2. **Detects whether the question targets a specific service** — looks for kebab-case tokens in the query (e.g., `creditbureau-service`, `consumer-portal`) and matches them against the registry's subdir names. When a match is found, narrows the read scope to that subdir; otherwise reads the full registry. Aggregate questions ("which services…", "compare", "across services") always trigger a full read.
3. Reads the ADRs in scope.
4. Synthesizes an evidence-based answer, citing each claim with `<service>/<ADR-file>`.

### Scoping examples

| Query | Scope |
|-------|-------|
| `/sdd:doc-adr-query why are we not using Redis in creditbureau-service?` | `creditbureau-service/` only |
| `/sdd:doc-adr-query show every ADR about retries` | All services (topic scan, no service name) |
| `/sdd:doc-adr-query do multiple services persist state in Postgres?` | All services (aggregate keyword) |
| `/sdd:doc-adr-query compare consumer-portal and creditbureau-service on locking` | Both subdirs (multi-match, no aggregate) |

The narrowing keeps responses faster and avoids spending tokens on unrelated ADRs.

## Requirements

- At least one ADR must exist under `~/.claude/adr-registry/*/` (or `$CLAUDE_DOC_HOME/adr-registry/*/` if the env var is set). Populate it by running `/sdd:doc-adr` in each service repository — it creates and stores each ADR in one step.

## Registry location

Defaults to `~/.claude/adr-registry/`. Override with `CLAUDE_DOC_HOME` to point at a different folder (e.g., a cloned GitLab repo for team sharing) — the skill reads from `$CLAUDE_DOC_HOME/adr-registry/`. See *Team-shared registry* in the plugin's `docs/doc-overview.md` for the full setup guide.

## Limitations

- Answers are only as fresh as the most recent `/sdd:doc-adr` run per service. ADRs are immutable; a changed decision is captured by a new superseding ADR.
- The skill never edits ADRs — it only reads them.

## Related Skills

- `/sdd:doc-adr` — creates an ADR and stores it in the registry this skill reads.
- `/sdd:doc-catalog-query` — same create-and-query pattern, but for service catalogs.
