# Ask — unified knowledge query

One query for the whole docs-registry. `/sdd:ask` answers any cross-service knowledge
question — services, decisions, specs, investigations — with one command.

## The design in one line

**Navigate the `wiki/` index, land on `raw/` (the source of truth).**

- `raw/` (`$CLAUDE_DOC_HOME`) is written directly by the `doc-*` commands → always current
  → every answer is grounded there.
- `wiki/` (when the vault has a compiled layer) is an explainable-RAG index of
  `[[backlinks]]` → makes cross-cutting questions cheap. It can lag; `ask` warns and falls
  back to `raw/` when it does.

So `ask` is **reliable even if `/sdd:doc-ingest` hasn't run** — a stale or absent wiki
degrades it gracefully to "the four typed queries, merged" rather than a wrong answer.

## Usage

```bash
/sdd:ask who consumes the LeadCreated event and why did we design it that way?
/sdd:ask what breaks if leads-service goes down?
/sdd:ask have we seen ReportToken reuse before?
/sdd:ask which services depend on package-orchestrator?  type:catalog
```

Add `type:catalog` / `type:adr` / `type:spec` / `type:investigation` to scope to one
registry (reproducing a single-registry query); omit it to search across all four.

## What it does

1. Runs `lib/registry.py ask` with your question verbatim. It prints an **index** of
   every doc, the **best-matching docs** (large ones trimmed to the matching sections)
   within a budget (`SDD_ASK_BUDGET`, default 60 000 characters), other matches by path,
   and reading hints. Only what matters is loaded — not the whole registry.
2. When a `wiki/` layer exists, reports its last ingest and warns when `raw/` docs
   changed after it; the skill then navigates the wiki's `[[backlinks]]` for
   cross-cutting questions.
3. Reads anything relevant that was not loaded, then answers citing `raw/` files.

`type:` / `service:` are optional: without them `ask` searches everything and ranks by
relevance. A service named in the question boosts its docs but does not filter —
"who consumes X from leads-service?" still needs the other services' catalogs.

## Related Skills

- `/sdd:doc-ingest` — builds/refreshes the `wiki/` layer `ask` navigates.
- The `doc-*` create commands — populate the `raw/` registries `ask` grounds answers in.
