# SDD Pipeline — Flow, Commands & Cadence

The full spec-driven flow, the per-command reference, and how to feed it well.
For setup see [setup.md](setup.md); for the gates and artifacts it relies on see
[concepts.md](concepts.md).

---

## Pipeline Flow

The main flow is `/sdd:start → /sdd:spec → /sdd:plan → /sdd:implement` (with the
low/medium vs. high-risk test branch) `→ /sdd:commit → /sdd:code-review →
/sdd:mr → /sdd:mr-address → /sdd:close`; each step is described under
[Pipeline Commands](#pipeline-commands). The commands below run **independently** of
that flow, on any branch, any time:

```
INDEPENDENT: Documentation & Knowledge (any branch, any time)
  (standalone quality commands — /sdd:commit, /sdd:mr, /sdd:code-review, /sdd:mr-review,
   /sdd:undo — are listed in the "Just want to code?" section of sdd-overview.md)
  (the doc commands below ship in the same plugin — see doc-overview.md)
  /sdd:doc-catalog       — generate service catalog + store in central registry (or `list`)
  /sdd:doc-adr           — capture an architectural decision + store in central registry (or `list`)
  /sdd:doc-spec          — store a feature spec.md in the central spec registry (or `list`)
  /sdd:doc-investigation       — capture a session investigation + store in central registry
  /sdd:ask               — one query across all four registries (+ wiki layer when present);
                           the /sdd:doc-*-query commands are deprecated aliases
  /sdd:doc-ingest        — compile raw/ registries into the wiki/ layer (two-layer vault only)

INDEPENDENT: Java Review Packs (deep-dive reviewers, any branch, any time)
  /sdd:jpa-patterns       — JPA/Hibernate review (N+1, lazy loading, transactions, fetching)
  /sdd:concurrency-review — thread-safety review (races, deadlocks, Virtual Threads, @Async)
  /sdd:api-contract-review — REST contract review (HTTP semantics, versioning, back-compat)
  /sdd:logging-patterns   — SLF4J / structured-logging / MDC review

UTILITIES: Navigation & Context Switching
  /sdd:whatnext        — where am I, what's next
  /sdd:state      — detailed pipeline progress
  /sdd:pause       — stash work without switching branches
  /sdd:restore      — restore paused work
  /sdd:undo        — discard a failed implementation, keep .specwork/ (reversible; --hard to force)
  /sdd:resync      — sync .specwork/ artifacts with current branch (`--rename-branch` to rename + sync)
  /sdd:handoff     — package spec + rules for handoff to other agents
```

> `/sdd:auto` runs (`/sdd:start` or skip if already initialized → `/sdd:spec` → `/sdd:plan` →
> `/sdd:implement` → `/sdd:commit` → `/sdd:mr`) **straight through to the open MR**.
> The only hard stop along the way is unresolved Open Questions (after `/sdd:spec`).
> It never auto-runs `/sdd:close` or `/sdd:mr-address`.
>
> **Open Questions** are unresolved markdown checkboxes (`- [ ]`) in `spec.md`
> (and optionally `plan.md`) that block `/sdd:implement` until answered.
> `/sdd:spec` is the canonical way to draft and resolve them. See [concepts.md](concepts.md).

---

## Giving Good Input

The spec is only as good as what you feed the pipeline. `/sdd:start` doesn't write
the spec — it captures a **source** (`source.md`) that `/sdd:spec` turns into one.
Both entry points persist that source on disk, so context you provide up front
survives the whole run (including a `/sdd:auto` run that later stops at a gate):

- **Jira** (`/sdd:start PROJ-1234`) — the full issue (summary, description, etc.)
  is fetched into `source.md`.
- **Free text** (`/sdd:start "summary: … behaviour: …"`) — your description is
  written verbatim into `source.md` (via `--source-body`, inline — no temp file).
  The richer the text, the better the first draft; a bare one-liner leans mostly
  on what can be inferred from the codebase.

Because free text is preserved, a **structured block maps straight onto the
spec's canonical sections** — give it to `/sdd:start` or `/sdd:auto` and `/sdd:spec`
drafts from it:

```
/sdd:auto "summary: dedupe leads when applicationId is null
behaviour: 1) given a null applicationId, skip dedupe instead of throwing
scope: only LeadProcessor; do not touch the SNS publisher
implementation context: LeadProcessor, LeadRepository
safe constraints: idempotent per applicationId; no schema change"
```

### Where deeper context belongs

The `/sdd:start` source seeds the spec, but two kinds of detail are better added
where the pipeline can act on them:

- **Target classes / files** also land in `## Implementation Context` and
  `## Expected Change Scope` (`Expected files touched`, `Expected layers`,
  `Avoid touching`). You can name them in the source block, but you can also:
  1. Pass files to `/sdd:spec` directly — `/sdd:spec src/.../LeadProcessor.java
     src/.../LeadRepository.java` — which also seeds `implementation-cache.json`.
  2. Run `/sdd:plan`, which discovers targets automatically (mock-consumer tests,
     exception handlers, reference grep). For 3+ file features, prefer discovery
     over hand-listing.
- **Answers to Open Questions** that surface after drafting → feed them back with
  `/sdd:spec` (a file, a Jira ticket, a paste, or free text). That's the canonical
  way to clear the gate that blocks `/sdd:implement`.

### What makes a good source (ticket or free-text block)

Aim to give material for each canonical spec section:

| Spec section | What the ticket should provide |
|---|---|
| **Summary** | What and **why** — the problem, not just the task |
| **Behavior** | Acceptance criteria as numbered, observable behaviors ("given X, when Y, then Z") |
| **Scope (in/out)** | Explicit boundaries — what **not** to touch keeps the draft from sprawling |
| **Implementation Context / Expected Change Scope** | Affected services, classes, endpoints if known |
| **Safe Constraints** | Invariants: PII, idempotency, API backward-compat, SLA/retry, DB migration |
| **Open Questions** | Known unknowns — state them; the pipeline turns each into a gate that blocks `/sdd:implement` until resolved |

A vague ticket ("fix the leads bug") with no expected behavior or boundaries
makes `/sdd:spec` emit mostly Open Questions and stall the run. Spend the context
up front and the rest of the pipeline flows.

---

## Pipeline Commands

### `/sdd:auto <ticket-or-text>` *(orchestrator)*
- Drives the pipeline in one call: `/sdd:start → /sdd:spec → /sdd:plan → /sdd:implement → /sdd:commit → /sdd:mr`
- If no pipeline exists, confirms the branch at `/sdd:start` (suggested branch / keep current / custom name); if a pipeline already exists, skips `/sdd:start` and continues on the current branch
- **Hard stop** if the drafted spec has unresolved Open Questions (won't guess past them) — resolve them with `/sdd:spec` and, in non-interactive mode, the pipeline continues automatically through plan, implement, commit, and the MR
- Runs `/sdd:commit` (coverage gate + semantic commit) → `/sdd:mr` automatically, then **stops at the open MR** (never `/sdd:close` or `/sdd:mr-address`). Run `/sdd:test-design` + `/sdd:test-impl` by hand beforehand if the change warrants tests
- On a red `check.sh` it runs `/sdd:mr`'s Repair Loop without asking (max 3 guarded attempts); still red → stops without pushing
- Best for trivial/focused tickets; drive the steps by hand for large or ambiguous work

### `/sdd:start <ticket-or-text>`
- Can start from any branch
- Runs `/init` to bootstrap `CLAUDE.md` **only when the project has none** (checks repo root and `.claude/`) before branching — purely model-context, no artifact depends on it
- Offers a new working branch based on the current branch context and current HEAD (`AskUserQuestion`: suggested branch / keep current / custom name)
- Can also initialize on the current branch when that is the better choice
- Writes `.specwork/_state/...` plus `.specwork/_spec/<slug>-source.md`; gitignores `.specwork/`
- Does **not** write the spec — run `/sdd:spec` next to draft it
- **Refuses to re-initialize over an active pipeline**: if `.specwork/` is already live here, it stops and points you to `/sdd:spec`, `/sdd:state`, `/sdd:pause`, or `/sdd:close` instead of wiping or reusing state
- **Requires input**: with no ticket or description and no active pipeline, it stops with no writes
- Next: `/sdd:spec`

### `/sdd:spec [files | jira <ticket> | paste | free text]`
- Owns `spec.md`. **Draft mode** (no spec yet): generates the spec from `source.md` + a stack-aware template, then runs triage. **Refine mode** (spec exists): integrates new context in place
- **Stack-aware template**: frontend projects (detected via `detect-stack`) draft from `templates/spec-frontend.md`, which adds `## Components`, `## Props & State`, `## Routes`, `## Design Reference`, and `## Accessibility Requirements`; java/node/unknown use the default `templates/spec.md`. The seven canonical headings are identical across both, so downstream parsing is unaffected
- Refine resolves Open Questions, expands `## Implementation Context`, appends to `## Safe Constraints`, adjusts `## Expected Change Scope`
- Mixed input in a single call: files + Jira ticket + free text together
- Refine with **no arguments** is a strict no-op (no write, no mtime bump)
- `--tier <trivial|focused|standard|high-risk|auto> "<reason>"` forces the triage tier (reason mandatory) without touching the spec; the plan-required gate and the high-risk auditor follow the forced tier. `auto` drops the override
- **Warns** when `plan.md` is older than the new spec or when the working tree has uncommitted changes (the actual block comes later, in `/sdd:implement`)
- Never deletes user content, never touches `source.md` / `rules.json`, never modifies git state
- Use any time after `/sdd:start` — first to draft, then between planning and implementation, mid-implementation, during review

### `/sdd:plan` *(optional)*
- Discovers target files from spec + rules + repo state
- Applies six discovery heuristics (currently Java-focused): mock-consumer tests, `[infra]` exception handlers, test-naming guard, reference-update grep, risk surface, and spec-consistency check
- Drafts `.specwork/_plan/<slug>-plan.md` with Target Files, Approach, Risks, and Open Questions
- Seeds `.specwork/_state/<slug>-implementation-cache.json` for downstream reuse
- **Strict gate**: blocks if `spec.md` still has unresolved `## Open Questions`
- **Re-run trigger**: after `/sdd:spec` (or any manual spec edit), the plan goes stale (`spec.md` mtime > `plan.md` mtime). `/sdd:implement` will block — re-run `/sdd:plan` to regenerate, or delete `plan.md` to fall back to inline discovery
- **When to use**: medium-to-large features (3+ files), refactors with broad blast radius, or any time you want an explicit target-file contract before implementing
- **When to skip**: small/obvious changes (1-2 files) — `/sdd:implement` falls back to inline discovery from the spec
- Next: `/sdd:implement`

### `/sdd:implement` (repeat N times)
- Implement one focused step at a time
- Inline tests validate each step immediately
- Changes accumulate in working tree (no commits between steps)
- **Strict gates** (abort with no writes):
  - Unresolved `## Open Questions` in spec.md or plan.md
  - Triage tier `high-risk` and no `plan.md` yet — run `/sdd:plan` first (or correct a misclassification with `/sdd:spec --tier`)
  - `plan.md` exists and is older than `spec.md` (typically after `/sdd:spec` or a manual spec edit) — re-run `/sdd:plan` to regenerate, or `rm` the plan to fall back to discovery from the spec
- Ends with a complexity assessment and recommended next phase:
  - Low/isolated → `/sdd:commit`
  - High/multi-layer, async, business-critical → `/sdd:test-design`

### `/sdd:test-design` *(optional — high-risk flow)*
- Analyzes the diff, designs test cases, and writes `.specwork/_test/<slug>-test-design.md`
- Runs **inside an active pipeline** (after `/sdd:implement`) — not a standalone tool
- Tracked only in the `high-risk` flow; **skippable** — you may go straight to `/sdd:commit`
- Next: `/sdd:test-impl`, or skip to `/sdd:commit`

### `/sdd:test-impl` *(optional — high-risk flow)*
- Implements the test files, following the cases from the test-design artifact
- **Depends on `/sdd:test-design`**: reads `.specwork/_test/<slug>-test-design.md` and refuses to run if it is missing
- Runs **inside an active pipeline**; **skippable** — you may go straight to `/sdd:commit`
- Next: `/sdd:commit`

### `/sdd:commit` (one commit at the end)
- Creates a single commit for all accumulated changes
- Auto-stages modified/new files from `git status` when nothing is staged
- **Test-coverage gate (strict)**: blocks the commit if a changed production class has no matching test (Java `*Test`/`*IT`, frontend `*.test`/`*.spec`). Pure data/wiring types (DTOs, config, entities, barrels) are not flagged. Waive a genuinely untestable class — with a written reason — in `.specwork/_test/<slug>-coverage-waivers.json` (or `.sdd-coverage-waivers.json` at the repo root when standalone)
- **Spec-conformance check (advisory)**: reports spec Behaviors (`B1`, `B2`, …) with no test tagged `spec: B<n>` in lines added on the branch — never blocks
- **High-risk auditor (advisory)**: on `high-risk` pipelines only, runs `/sdd:code-review` automatically once per distinct staged diff (receipt in `_review/<slug>-audit.json`) — never blocks
- Generates a semantic commit message; user approves before commit

### `/sdd:code-review` (optional)
- Stack-aware quality/security review of current diff

### `/sdd:mr-review <branch | mr-url | mr-iid>` (standalone)
- Reviews **someone else's** committed work — an MR or a branch — using the same engine as `/sdd:code-review`
- Resolves the input to a diff (`glab mr diff` for MRs, `git diff origin/<target>...origin/<branch>` for branches)
- **Read-only**: never checks out, switches branch, commits, pushes, or comments on the MR
- Writes the report to `.specwork/_review/` if present, else `~/.claude/peer-reviews/`
- MR mode needs an authenticated `glab`; branch mode needs only `git`

### `/sdd:mr`
- **Pre-push validation**: runs test suite before push
  - If tests fail → offers the **Repair Loop** (asks first): fixes the code and re-runs `check.sh`, max 3 attempts. `lib/repair.py` counts the attempts and guards each one: no edits to `check.sh` or test configs, no changes to existing tests, no skips. A green repair is committed with `/sdd:commit`. Still red, declined, or rejected → stops, does not push; the push hook stays closed until the loop ends
  - If tests pass → continues
- Builds concise MR title/description from spec + commits
- Optional publish: `.specwork/_spec/...` -> `docs/specs/...`
- Pushes branch and creates MR (auto with `glab`, manual otherwise)
- Optional: `--skip-validation` for emergencies

### `/sdd:handoff` (optional)
- Package spec + rules + context into model-agnostic execution contract
- Use when handing off to another agent (Gemini, Copilot, Codex, Claude)
- Creates `.specwork/_handoff/<slug>-execution-pack.md`

### `/sdd:mr-address`
- Address unresolved MR comments thread by thread
- Track progress in `.specwork/_review/<id>-mr-address.md`

### `/sdd:close`
- Wipes `.specwork/` after merge (or reset)
- Before wiping (interactive only), proposes up to 4 durable rules from the closed spec for `.claude/service-rules.md` or the matching `.claude/rules/*.md`; writes only the ones you approve, as new bullets tagged `_(from spec <slug>, <date>)_`. Existing hand-written rules are never edited — `lib/promote.py` refuses any write that would change an existing line
- On a feature branch, offers to delete the local branch and switch back to the parent (never touches the remote branch)
- Never reverts or deletes source-tree changes outside `.specwork/`

---

## Implementation Cadence

The pipeline supports repeated implementation steps before you commit:

```bash
/sdd:implement    # code + inline tests — low complexity
/sdd:implement    # code + inline tests — low complexity
/sdd:implement    # code + inline tests — HIGH → recommends /sdd:test-design

/sdd:test-design  # (high-risk, optional) design test cases → writes artifact
/sdd:test-impl    # (high-risk, optional) implement them — requires test-design first

/sdd:commit       # one commit for all accumulated changes

/sdd:mr           # validates tests, pushes, creates MR
```

> `/sdd:test-design` and `/sdd:test-impl` are optional steps tracked only in the
> `high-risk` flow. `/sdd:test-impl` depends on `/sdd:test-design`'s artifact, so run
> them in order — or skip both and go straight to `/sdd:commit`.

**Advantages:**
- Fast iteration: run `/sdd:implement` N times without commit overhead
- Immediate feedback: each step validates its own tests
- Clean history: one logical commit per coherent set of changes
- Single validation gate: tests validated once in `/sdd:mr` before push

---

## Context Switching

```text
/sdd:pause  -> stash work (including .specwork/) without switching branches
/sdd:restore -> switch back to the recorded branch and restore paused feature work
```

If you need to **discard a failed implementation** but keep the pipeline state to
re-spec, use **`/sdd:undo`** (reversible by default; `--restore` to recover, `--hard`
to force). See the runbook in [concepts.md](concepts.md#reverting-a-failed-implementation).

---

## Recurring Tasks (`/loop`, `/schedule`)

The pipeline itself never repeats on a timer, but Claude Code's own `/loop`
(in-session, on an interval) and `/schedule` (cloud, on a cron) work well around it:

```bash
/loop 10m check the CI pipeline of this branch's MR and tell me when it finishes
/schedule every weekday at 9:00 run /sdd:doc-ingest
```

- Good fits: read-only watching (CI, MR status) and keeping the knowledge base fresh
  (`/sdd:doc-ingest`, so `/sdd:ask` does not answer from a stale wiki).
- Do not put `/sdd:mr-address`, `/sdd:auto`, or `/sdd:close` on a loop: they push,
  open MRs, or delete state, and each run needs a human decision.
- An open-ended loop ("improve the project" until an iteration cap) has no stop
  condition except the cap. Write a spec instead; the only loop the pipeline runs is
  `/sdd:mr`'s Repair Loop, which stops on a green `check.sh` it cannot edit.

