# SDD Pipeline (Claude Code plugin)

The Spec-Driven Development (SDD) pipeline, packaged as a **Claude Code plugin**:
a gated chain of `/sdd:*` commands that take a feature from idea to merged MR,
plus doc/ADR/spec registry commands and stack-aware reviewer agents.

Everything is namespaced under `sdd:` and installed through `/plugin` — it
touches only your own Claude Code config, nothing shared, and nobody gets it
unless they opt in.

## Install

```text
/plugin marketplace add https://github.com/gatsby2008/sdd-plugin
/plugin install sdd@gatsby
```

Commands then appear as `/sdd:start`, `/sdd:spec`, `/sdd:commit`, … and the
reviewer agents as `sdd:java:quality-reviewer`, `sdd:ui:a11y-reviewer`, ….

> **Install it as a plugin — do not copy or symlink `skills/` into `~/.claude/skills/`.**
> Claude Code *always* namespaces a plugin's skills under its `plugin.json` name, so
> installed-as-a-plugin you get `/sdd:plan`, `/sdd:spec`, `/sdd:doc-investigation`, and they
> never clash with built-ins. The moment you drop the `skills/` folders into
> `~/.claude/skills/` (or symlink them there) they load **standalone** and lose the
> prefix — `/plan` then collides with the native `/plan`, `/spec` with any other `/spec`,
> and so on. There is no per-skill prefix in this repo on purpose: the `sdd:` namespace
> is what the plugin install gives you for free. If you see bare names, you loaded it
> standalone — uninstall the standalone copy and install via `/plugin` instead.

To try it locally before publishing a marketplace (this still namespaces as `/sdd:*`):

```bash
claude --plugin-dir ~/team/sdd-plugin
```

**Requirement:** Python 3 (the pipeline shells out to it). A `SessionStart` hook
checks for it and, on Windows + Git Bash, drops a `python3` shim when only
`python`/`py` exist.

## The pipeline

```text
/sdd:start → /sdd:spec → /sdd:plan → /sdd:implement → /sdd:commit → /sdd:mr → /sdd:close
```

Plus `/sdd:auto` (non-interactive driver that runs straight through to the open MR) and the standalone
helpers (`/sdd:commit`, `/sdd:mr`, `/sdd:code-review`, `/sdd:mr-review`, `/sdd:undo`) that work on
any branch with no spec or setup.

## Layout

```
sdd-plugin/
├── .claude-plugin/
│   ├── plugin.json        Plugin manifest (name: sdd)
│   └── marketplace.json   Marketplace entry (gatsby)
├── skills/                34 flat skills → /sdd:<name>
│   ├── start, spec, plan, implement, commit, mr, close, auto,
│   │   code-review, mr-review, mr-address, state, whatnext, handoff,
│   │   pause, restore, resync, undo, test-design, test-impl
│   ├── doc-catalog, doc-catalog-query, doc-adr, doc-adr-query,
│   │   doc-spec, doc-spec-query,
│   │   doc-investigation, doc-investigation-query,
│   │   doc-ingest, ask       (two-layer wiki: compile raw→wiki, unified query)
│   └── api-contract-review, concurrency-review, jpa-patterns, logging-patterns
├── agents/
│   ├── java/  → sdd:java:quality-reviewer, sdd:java:security-reviewer
│   └── ui/    → sdd:ui:quality-reviewer, sdd:ui:a11y-reviewer
├── hooks/                python3 check + pipeline status (SessionStart),
│                        coverage/push gates + branch-mismatch warning (PreToolUse),
│                        resync reminder (PostToolUse)
├── lib/  templates/  docs/   shared assets
└── AGENTS.md
```

Skills are flat (plugin skill discovery is one level deep) and invoke shared
helpers via `${CLAUDE_PLUGIN_ROOT}/lib/…`.

## Docs & tests

- `docs/sdd-overview.md` — entry point; `docs/pipeline.md`, `docs/concepts.md`,
  `docs/setup.md`, `docs/doc-overview.md` — full reference.
- `skills/<name>/SKILL.md` — per-command instructions.

```bash
cd lib && python3 -m unittest discover -s tests
```
