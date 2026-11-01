# Service Catalog Query

Answers cross-service architecture questions by reading every catalog under `~/.claude/service-catalog/` and synthesizing an answer from the combined knowledge. The registry is populated by `/sdd:doc-catalog` runs from each service (which generate and store the catalog in one step).

## Usage

```bash
/sdd:doc-catalog-query who consumes the LeadCreated SNS event?
/sdd:doc-catalog-query what services call /api/v1/consent?
/sdd:doc-catalog-query which services does marketing-service depend on?
```

Pass any free-text architecture question as the argument.

## Example queries

Group your queries by intent. Each category below maps to a query type the skill knows how to answer — adapt the templates to the service, event, or field name in your own registry.

### Event flow — who publishes or consumes a message?

```bash
/sdd:doc-catalog-query who publishes the LeadCreated SNS event?
/sdd:doc-catalog-query which services consume the marketing-lead-events queue?
/sdd:doc-catalog-query trace LeadCreated from publisher to every downstream consumer
/sdd:doc-catalog-query list every SNS topic published across the registry
```

### Endpoint discovery — which service owns this URL?

```bash
/sdd:doc-catalog-query which service exposes POST /api/v1/consent?
/sdd:doc-catalog-query list every endpoint under /api/v1/leads
/sdd:doc-catalog-query are there any duplicated endpoint paths across services?
/sdd:doc-catalog-query which services expose endpoints reachable from the consumer portal?
```

### Dependency mapping — what does a service rely on?

```bash
/sdd:doc-catalog-query which services does leads-service call via Feign?
/sdd:doc-catalog-query what external APIs does creditbureau-service integrate with?
/sdd:doc-catalog-query show the full dependency graph for consumer-portal
/sdd:doc-catalog-query which services depend on package-orchestrator?
```

### Impact analysis — what breaks if X is unavailable?

```bash
/sdd:doc-catalog-query what breaks if leads-service goes down?
/sdd:doc-catalog-query which services would be affected by an outage of creditbureau-service?
/sdd:doc-catalog-query if we change the LeadCreated schema, who must update their consumers?
/sdd:doc-catalog-query which services are single points of failure for the lead-to-package flow?
```

### Data ownership — where does a field live?

```bash
/sdd:doc-catalog-query which service owns the consent_flag field?
/sdd:doc-catalog-query which DTOs include phone_number?
/sdd:doc-catalog-query where is the consumer email validated?
/sdd:doc-catalog-query which catalogs reference the LeadCreatedEvent schema?
```

### Operational — scheduled jobs, configuration, integrations

```bash
/sdd:doc-catalog-query list every scheduled job across all services
/sdd:doc-catalog-query which services run nightly batch jobs?
/sdd:doc-catalog-query which third-party SDKs are used in the registry?
/sdd:doc-catalog-query summarize the SQS queue topology — who consumes what?
```

### Discovery — what's even in the registry?

```bash
/sdd:doc-catalog-query summarize each service in one paragraph
/sdd:doc-catalog-query which services publish to SNS and which only consume from SQS?
/sdd:doc-catalog-query give me the architectural surface area of the consent flow end-to-end
```

Every answer cites the catalogs it pulled from — if a fact is wrong, refresh that service's catalog by re-running `/sdd:doc-catalog` (it re-scans the code and overwrites the registry entry).

## What it does

1. Lists every file under `~/.claude/service-catalog/`.
2. Reads each catalog.
3. Builds a topic/queue index — resolved wire topic/queue name → every publisher + every consumer — so event-flow questions resolve by the actual wire name instead of a literal-phrase grep. Different services can describe the same topic differently (a feature/ticket name in one catalog, the literal SNS/SQS name in another); indexing by the resolved name catches every publisher and consumer, not just the ones that happen to share the question's wording.
4. Synthesizes an evidence-based answer citing the services involved and the relevant catalog entries.

## Requirements

- At least one catalog must exist under `~/.claude/service-catalog/` (or `$CLAUDE_DOC_HOME/service-catalog/` if the env var is set). Populate it by running `/sdd:doc-catalog` in each service repository — it generates and stores the catalog in one step.

## Registry location

Defaults to `~/.claude/service-catalog/`. Override with `CLAUDE_DOC_HOME` to point at a different folder (e.g., a cloned GitLab repo for team sharing) — the skill reads from `$CLAUDE_DOC_HOME/service-catalog/`. See *Team-shared registry* in the plugin's `docs/doc-overview.md` for the full setup guide.

## Limitations

- Answers are only as fresh as the most recent `/sdd:doc-catalog` run per service. If a catalog reports stale information, re-run `/sdd:doc-catalog` in the affected service.
- The skill never edits catalogs — it only reads them.
- The topic/queue index is rebuilt fresh on every query (nothing is cached to disk) — it only ever reflects services that already have a catalog in the registry. A service missing from the registry entirely is still invisible, index or not.

## Related Skills

- `/sdd:doc-catalog` — generates the per-service catalog and stores it in the registry this skill reads.
- `/sdd:doc-adr-query` — same pattern for architecture decisions.
