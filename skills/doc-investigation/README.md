# Investigation Capture

Freeze the current session's code investigation into a structured findings document and file it in the central investigation registry.

When you dig into code — frequently in a repo that isn't yours — you figure out *why* something behaves the way it does. That insight usually disappears when the session closes. `/sdd:doc-investigation` captures it in a fixed template and stores it where you (and your team) can search it later, without touching the investigated repo.

---

## Prerequisites

- A session where an actual investigation happened (the conversation is the source).
- Write access to `~/.claude/investigation-registry/` (or your `$CLAUDE_DOC_HOME` override).
- Optional: being inside the investigated git repo, so the service name is auto-detected.

---

## Usage

```bash
/sdd:doc-investigation                                       # asks which template (bug / exploration / improvements), inferred one recommended
/sdd:doc-investigation "Vehicle lookup returns stale rows"   # seed the title; still asks which template
/sdd:doc-investigation explore "How a lead reaches the cache"  # force exploration
/sdd:doc-investigation bug                                   # force bug
/sdd:doc-investigation improvements "Meet the CLAUDE.md gist"  # force improvement plan
/sdd:doc-investigation list                                  # list investigations already registered for this repo's service
```

Run it at any point — the moment things "click." You can run it again later in the same session to capture a fuller version; each run writes a new dated file.

`list` is read-only and **scoped to the current repo's service** — it shows what's already captured for this service (filename, type, title), newest first. To search *across* services or by content, use `/sdd:ask`.

---

## What It Does

Reads what has been discussed so far in the session, **infers a recommended type — bug hunt, exploration, or improvement plan — and asks you to pick it** (unless you forced one via args), then synthesizes the session into the matching fixed template:

```
bug                  exploration           improvements
# Problem            # Question            # Goal
# Symptoms           # Context             # Current State
# Reproduction       # Map                 # Gap Analysis
# Investigation      # How It Works        # Plan
# Findings           # Key Findings        # Out of Scope
# Root Cause         # Caveats & Gotchas   # Open Decisions
# Fix *              # Open Questions      # Future Signals
# Related Classes    # Future Signals
# Future Signals

* Fix is actionable: Status (applied/proposed/none-yet) · Where (file → symbol) ·
  Change (the concrete edit) · Verify (how to confirm) — so any agent can act on it.
```

`bug` and `exploration` are backward-looking (what broke / how it works); `improvements` is forward-looking (what to change — a remediation plan with ADOPT/PARTIAL/REJECT verdicts and an Out of Scope section). The type is chosen up front — inferred from the session and offered for you to pick, or forced with `/sdd:doc-investigation bug`, `… explore`, or `… improvements`. All three shapes end in **Future Signals** — the reusable "next time, check/start here" pointer. The chosen type is saved in the file's frontmatter so `/sdd:ask` can filter on it.

It pulls only from the conversation — it does not re-scan the code or invent class names. Anything not actually discussed is marked `[TBD]`; anything deduced is marked `[INFERRED]`. You see the full draft (including those markers) and the destination path, then it writes — there's no yes/no write gate, since you already chose the type up front.

The document is keyed by service (the repo under investigation) the same way ADRs, specs, and catalogs are, so all of a service's knowledge lines up under one name. Files are dated, e.g. `investigation-registry/lead-service/2026-06-10-vehicle-lookup-stale-rows.md`.

---

## When to Use

- After tracing a bug to its root cause in any codebase.
- After reverse-engineering an unfamiliar service and learning something non-obvious.
- When you want a "if you see this again, check that first" note for your future self or teammates.

Use `/sdd:doc-adr` instead when you're recording a *decision* (immutable, supersede-only). Use `/sdd:doc-investigation` for *findings* about how the system actually behaves.

---

## Output / Next Step

A Markdown file in `~/.claude/investigation-registry/<service>/<date>-<slug>.md`. Search across everything you've captured with `/sdd:ask`.

---

## Troubleshooting

**It marked everything `[TBD]`**
The session didn't contain enough investigation to synthesize. Discuss the findings first, then re-run.

**Wrong service name**
Auto-detection uses `spring.application.name` then the git repo basename. Run it from inside the investigated repo, or provide a name when asked.

**I want findings shared with my team**
Point `$CLAUDE_DOC_HOME` at a cloned shared repo: `export CLAUDE_DOC_HOME=/path/to/registry-root`. The same variable moves every SDD registry together.

---

## Related Skills

- `/sdd:ask` — ask questions across all captured investigations
- `/sdd:doc-adr` — record an immutable architecture decision instead of a finding
- `/sdd:spec` — author a forward-looking feature spec
