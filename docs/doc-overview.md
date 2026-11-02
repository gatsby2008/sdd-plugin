# Documentation Skills

A bundle of ten skills that together form a documentation and cross-service architecture-discovery workflow. Four parallel families — for **service catalogs**, **ADRs**, **feature specs**, and **investigations** — share one shape: `doc-<artifact>` **creates + stores** it in the central registry, and **`/sdd:ask`** reads all four back with one query (`type:<artifact>` to restrict it). The old `doc-<artifact>-query` commands remain as deprecated aliases. There is no separate `publish` step — creating an artifact stores it — and nothing is written into the service repo's working tree. **`/sdd:doc-ingest`** adds an optional second knowledge layer (see *Two-layer vault* below).

## Members

| Slash command | Purpose |
|---------------|---------|
| `/sdd:doc-catalog` | Generate a service catalog for the current microservice (Java Spring Boot or frontend) — scans controllers, listeners, clients, schedulers, and config — and store it at `~/.claude/service-catalog/<service>.md`. `list` shows the registry. |
| `/sdd:doc-adr` | Capture an architectural decision as an ADR and store it at `~/.claude/adr-registry/<service>/`. Modes: free text, from a Jira ticket, or from resolved Open Questions on the current branch. `list` shows the registry. |
| `/sdd:doc-spec` | Store a hand-written or standalone `spec.md` at `~/.claude/spec-registry/<service>/`. Authoring is `/sdd:spec`; the SDD pipeline's `/sdd:mr` stores specs automatically — this is the registry side for vibe-coding / non-pipeline flows. `list` shows the registry. |
| `/sdd:doc-investigation` | Capture the current session into a fixed-shape document — `bug` (Problem → … → Fix), `exploration` (Question → … → Future Signals), or `improvements` (Goal → Gap Analysis → Plan → Out of Scope), a forward-looking remediation plan — and store it at `~/.claude/investigation-registry/<service>/`. Synthesizes from the conversation; run it in any repo, even one that isn't yours. |
| `/sdd:ask` | **One query** across all four registries. `lib/registry.py` loads only the documents that match the question, within a budget (an index of every doc is always printed). Grounds every answer in `raw/` and, when a `wiki/` layer exists, follows its `[[backlinks]]` for cross-cutting questions ("who consumes X *and* why we designed it that way"). Warns when the wiki is stale; optional `type:` / `service:` filters. |
| `/sdd:doc-catalog-query` · `/sdd:doc-adr-query` · `/sdd:doc-spec-query` · `/sdd:doc-investigation-query` | Deprecated aliases of `/sdd:ask type:<artifact>`. |
| `/sdd:doc-ingest` | Compile `raw/` → `wiki/` in a two-layer vault: extract entities + concepts, write pages with `[[backlinks]]`, update indexes + log. The *producer* that keeps `/sdd:ask` sharp. No-op on a plain registry (no `wiki/` layer). |

## Two-layer vault (optional, powers `/sdd:ask`)

When `$CLAUDE_DOC_HOME` is a **two-layer knowledge vault** (Karpathy's "LLM Knowledge Bases" model) — a `wiki/` directory beside `raw/` — the registries above live under `raw/` (the source of truth), and a compiled `wiki/` layer (`entities/`, `concepts/`, `sources/` with `[[backlinks]]`) sits next to it:

```
$CLAUDE_DOC_HOME (raw/)  ──/sdd:doc-ingest──►  ../wiki/  ──/sdd:ask navigates──►  answer (grounded in raw/)
  service-catalog/ adr-registry/                entities/ concepts/ sources/
  spec-registry/ investigation-registry/        + indexes + log.md
```

- `raw/` is always current (the `doc-*` commands write it directly).
- `wiki/` is an **explainable-RAG index** — explicit backlinks you can audit — refreshed by `/sdd:doc-ingest`.
- `/sdd:ask` **navigates the wiki but grounds answers in raw/**, so it stays correct even if the wiki is stale (it warns and answers from `raw/`).

On a plain registry (the default `~/.claude`, no `wiki/`), `/sdd:doc-ingest` is a no-op and `/sdd:ask` just reads the `raw/` registries directly.

## Workflow

```
Catalogs (one per service):
  /sdd:doc-catalog        →  generate + store  ~/.claude/service-catalog/<service>.md
       │
       ▼
  /sdd:ask type:catalog   →  cross-service architecture questions

ADRs (many per service):
  /sdd:doc-adr            →  create + store  ~/.claude/adr-registry/<service>/<TICKET>-ADR-NNN-*.md
       │
       ▼
  /sdd:ask type:adr       →  cross-service decision-history questions

Specs (one per feature):
  /sdd:doc-spec           →  store  ~/.claude/spec-registry/<service>/<slug>-spec.md
  /sdd:mr (sdd)         →  (same destination, automatically, inside the SDD pipeline)
       │
       ▼
  /sdd:ask type:spec      →  cross-service feature/spec questions

Investigations (many per service):
  /sdd:doc-investigation        →  ~/.claude/investigation-registry/<service>/<date>-<slug>.md
       │                            (capture + write happen in one step, from the session)
       ▼
  /sdd:ask type:investigation  →  recall / recurrence questions across findings
```

All four families follow the same shape: `doc-<artifact>` is run inside each service repo and writes straight to the registry (no in-repo copy); `/sdd:ask` reads every registry from anywhere (the `type:` filter is optional). For specs there are two ways to store: `/sdd:doc-spec` for hand-written or standalone specs, and the SDD bundle's `/sdd:mr`, which stores automatically when a `.specwork/` spec exists.

## Registry location

All doc skills resolve their registry path from a single environment variable:

```bash
REGISTRY_HOME="${CLAUDE_DOC_HOME:-$HOME/.claude}"
# service-catalog       → $REGISTRY_HOME/service-catalog/
# adr-registry          → $REGISTRY_HOME/adr-registry/
# spec-registry         → $REGISTRY_HOME/spec-registry/
# investigation-registry → $REGISTRY_HOME/investigation-registry/
```

| `CLAUDE_DOC_HOME` | Resolves to | Use case |
|-------------------|-------------|----------|
| not set (default) | `~/.claude/service-catalog/`, `~/.claude/adr-registry/` | Solo developer, local only — identical to the original behavior. No migration needed. |
| `~/repos/docs-registry` (any path) | `~/repos/docs-registry/service-catalog/`, `~/repos/docs-registry/adr-registry/` | Team-shared registry — e.g., a cloned GitLab repo committed and pulled by the whole team. |

All registries always move together — there is no per-skill override. This keeps the configuration story to one variable.

## Team-shared registry (optional)

To share catalogs, ADRs, specs, and investigations across a team via a GitLab project:

### One-time setup (per developer)

```bash
# 1. Clone the team's docs registry into any path you prefer
git clone git@gitlab.com:<group>/docs-registry.git ~/repos/docs-registry

# 2. Point the skills at it (add to ~/.zshenv on macOS so non-interactive shells see it too)
echo 'export CLAUDE_DOC_HOME=~/repos/docs-registry' >> ~/.zshenv
source ~/.zshenv

# 3. Verify
/sdd:doc-catalog list      # should list catalogs from the GitLab repo
/sdd:doc-adr list          # should list ADRs from the GitLab repo
```

### Migrating existing local data (one-time)

If you already have registries under `~/.claude/` (catalogs, ADRs, specs, or investigations), copy them into the new registry (the skills do not auto-migrate):

```bash
# Copy (safer than mv until you confirm the new flow works)
for r in service-catalog adr-registry spec-registry investigation-registry; do
  mkdir -p "$CLAUDE_DOC_HOME/$r"
  cp -r ~/.claude/"$r"/. "$CLAUDE_DOC_HOME/$r/" 2>/dev/null
done

# Commit + push the seed data
cd "$CLAUDE_DOC_HOME"
git add service-catalog adr-registry spec-registry investigation-registry
git commit -m "seed: initial registries from <your-machine>"
git push

# Once you're confident the new flow works, clean up the originals
rm -rf ~/.claude/service-catalog ~/.claude/adr-registry \
       ~/.claude/spec-registry ~/.claude/investigation-registry
```

### Day-to-day flow

```bash
# In any service repo:
/sdd:doc-catalog        # generate catalog + store in registry (one step)
/sdd:doc-adr "..."      # capture ADR + store in registry (one step)

# Share with the team:
cd "$CLAUDE_DOC_HOME"
git add -A && git commit -m "publish: <what changed>" && git push

# Pull other people's updates:
cd "$CLAUDE_DOC_HOME" && git pull
```

### Suggested GitLab repo layout

```
docs-registry/                  ← repo root
├── README.md                   ← onboarding for the team
├── service-catalog/            ← one flat file per service
│   ├── consent-service.md
│   ├── leads-service.md
│   └── ...
├── adr-registry/               ← per-service subdir, many ADRs each
│   ├── consumer-portal-service/
│   │   ├── PROJ-17499-ADR-001-…md
│   │   └── …
│   └── leads-service/
│       └── IR-96-ADR-001-…md
├── spec-registry/              ← per-service subdir, one file per feature
│   ├── consumer-portal-service/
│   │   └── proj-17499-spec.md
│   └── leads-service/
│       ├── ir-96-spec.md
│       └── proj-17150-spec.md
└── investigation-registry/     ← per-service subdir, date-prefixed findings
    ├── consumer-portal-service/
    │   └── 2026-06-10-consumer-login-stuck-…md
    └── sdd-plugin/
        └── 2026-06-13-where-hooks-fit-and-adr-auto-capture.md
```

The repo may also hold other team docs (e.g. `architecture/`, `product/`, `templates/`) outside the four registries — the doc skills only read and write the four registry folders above.

Conflicts are rare because catalogs are one file per service and ADRs, specs, and investigations each have their own file under a per-service subdir. When two devs publish the same file on the same day, git's normal merge resolution applies — the files are plain markdown.

## Install

These commands ship inside the **sdd** plugin and install with the rest of the
pipeline via `/plugin`:

```text
/plugin marketplace add https://github.com/gatsby2008/sdd-plugin
/plugin install sdd@gatsby
```

## Integration with the SDD pipeline

`/sdd:mr` (in the `sdd` bundle) prints a hint suggesting `/sdd:doc-adr open-questions` when the current spec has any resolved Open Questions — those resolutions are the most common form of architectural decision worth preserving as an ADR. The other doc skills are independent of the SDD pipeline and can be run on any branch at any time.
