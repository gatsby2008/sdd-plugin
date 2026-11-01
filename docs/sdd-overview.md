# Spec-Driven Development (SDD)

**SDD makes AI coding agents safer** — by forcing them to work from specs,
respect unresolved questions, validate changes, and preserve execution context
across handoffs.

> A portable Spec-Driven Development pipeline that turns Jira tickets or
> free-text requirements into gated, repeatable implementation workflows for AI
> coding agents.

A single feature pipeline from ticket to merged MR, built as a chain of `/sdd:*`
commands.

---

## Install

This pipeline ships as the **sdd** Claude Code plugin; installing it brings
everything at once — there is no per-tool selection:

```text
/plugin marketplace add https://github.com/gatsby2008/sdd-plugin
/plugin install sdd@gatsby
```

That pulls in everything the pipeline relies on:

- the **Java reviewers** → `sdd:java:quality-reviewer`, `sdd:java:security-reviewer`, plus the Java review packs (`jpa-patterns`, `concurrency-review`, `api-contract-review`, `logging-patterns`)
- the **UI reviewers** → `sdd:ui:quality-reviewer`, `sdd:ui:a11y-reviewer`
- the **documentation registry** → the `/sdd:doc-*` commands and `/sdd:ask` (see [doc-overview.md](doc-overview.md))

Update or remove it with Claude Code's own `/plugin` command (`/plugin update sdd`,
`/plugin uninstall sdd`); the plugin ships no installer of its own.

First-time credential and project setup (Python, Jira, MR config, `glab`,
`check.sh`) lives in **[setup.md](setup.md)**.

---

## Quickstart

### Just want to code? (vibe coding)

Not every change needs the full spec-driven pipeline. Five commands are
**standalone** — they need no `.specwork/` state, no spec, no plan, and work on
any branch in any repo:

| Command | What it does standalone |
|---------|-------------------------|
| **`/sdd:commit`** | Stage + run the test-coverage gate + semantic commit message |
| **`/sdd:mr`** | Validate + push + create the MR |
| **`/sdd:code-review`** | Stack-aware quality + security review of your own diff |
| **`/sdd:mr-review`** | Same review engine, on a peer's branch or MR (read-only) |
| **`/sdd:undo`** | Discard uncommitted changes — reversible (`--restore` to recover, `--hard` to force) |

The vibe loop: code freely → `/sdd:code-review` (optional) → `/sdd:commit` → `/sdd:mr`
(and `/sdd:undo` to roll back uncommitted changes at any point).

### Full pipeline

Reach for the spec-driven pipeline when the change is multi-file, high-risk, or
worth a durable spec:

```bash
/sdd:start PROJ-123     # or: /sdd:start "fix duplicate leads when applicationId is null"
/sdd:spec                # draft the spec from the captured source, then run triage
/sdd:plan                # (optional) discover target files + draft a plan
/sdd:implement           # implement one focused step (repeat N times)
/sdd:commit              # one commit for all accumulated changes
/sdd:mr                  # validate, push, create the MR
```

Or drive it non-interactively through to the MR in one call:

```bash
/sdd:auto "summary: … behaviour: … scope: … safe constraints: …"
```

---

## Documentation

| Doc | Contents |
|-----|----------|
| **[pipeline.md](pipeline.md)** | Full flow diagram, per-command reference, implementation cadence, context switching, and how to give good input |
| **[concepts.md](concepts.md)** | Open Questions, gates, implementation cache, handoff, and artifacts (`.specwork/`) |
| **[doc-overview.md](doc-overview.md)** | The documentation registry: `/sdd:doc-*`, `/sdd:ask`, team-shared registry |
| **[setup.md](setup.md)** | Prerequisites and one-time setup: Jira, MR config, `glab`, doc registry, `check.sh` |

---

## Notes

- `/sdd:whatnext` — where am I, what's next.
- `/sdd:state` — compact pipeline status.
- For requirements changes, run `/sdd:spec` instead of editing the spec by hand —
  it resolves Open Questions, expands scope sections, and warns about downstream
  staleness.
