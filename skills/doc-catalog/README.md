# Service Catalog

Scans the current service, generates a single-page catalog entry documenting what the
service does, what it exposes, what it publishes, what it consumes, and who it calls,
and **stores it directly in the central service-catalog registry** (no copy is left in
the service repo). Supports Java Spring Boot and frontend (React / Next.js / Vue).

Generated from the code, not written by hand. Accurate by default.

---

## Usage

```bash
# Scan the codebase, generate the catalog, and store it in the registry
/sdd:doc-catalog

# Show the catalogs already in the registry
/sdd:doc-catalog list
```

The catalog is written to `service-catalog/<service-name>.md` under
`~/.claude/` (or `$CLAUDE_DOC_HOME` for a team-shared registry). On completion the
command prints the stored path. Query the registry with `/sdd:ask`.

**Freshness.** The catalog header records the commit it was generated from
(`Verified at: <commit>`). `/sdd:doc-catalog list` reports how many commits and code
files changed since then in this repo; `/sdd:ask` shows the commit next to every
catalog it loads and warns when one was regenerated more than 90 days ago
(`SDD_CATALOG_MAX_AGE_DAYS`).

---

## What It Produces

```markdown
# Service: creditbureau-service

## Overview
Queries DataVendor for credit and vehicle data on behalf of leads-service...

## Endpoints
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | /api/v1/datavendor/search-person | ... | Cognito JWT |
| GET | /internal/datavendor/circuit/status | ... | Cognito JWT |

## Publishes (SNS)
| Topic | Event type | Trigger |
|-------|-----------|---------|
| `credit-results-topic` | `CreditReportReady` | DataVendor returns a result |

## Consumes (SQS)
| Queue | Source topic | Event type | Published by |
|-------|-------------|-----------|-------------|
| `creditbureau-requests-queue` | `credit-requests-topic` | `CreditCheckRequested` | leads-service |

## Calls (Feign)
| Service | Base URL property | Auth | Resilience | Purpose |
|---------|------------------|------|-----------|---------|
| leads-service | `${feign.leads-service.url}` | Bearer (`ServiceUserPoolCredentials`) | 3× retry, 20s/60s | Fetch lead data |

## Webhooks & Callbacks
| Direction | Method | Path / Property | Auth | Payload |
|-----------|--------|-----------------|------|---------|
| Incoming | POST | `/api/v1/stipulation/callback` | public | `MoxoCallbackRequestDto` |

## Key Configuration
| Property | Purpose |
|----------|---------|
| `aws.sqs.creditbureau-requests-queue` | Inbound request queue |
```

---

## Why this matters

In a microservices architecture, knowing who publishes and who consumes a given
SNS event is critical for debugging and impact analysis. Without a catalog, the
answer requires searching across every repo.

With every service's catalog in one central registry, you can:
- Answer "who consumes `CreditCheckRequested`?" with `/sdd:ask`
- See the full dependency chain of a service at a glance
- Onboard new developers without a live walkthrough

---

## Independent of the SDD pipeline

This skill has no dependency on `.specwork/` artifacts. It can be run on any
existing Spring Boot service at any time.
