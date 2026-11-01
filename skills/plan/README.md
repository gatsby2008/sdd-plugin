# Plan

Discover target files and write an implementation plan from the spec, rules, and implementation cache.

`/sdd:plan` runs **after** `/sdd:start` and **before** `/sdd:implement`. It's optional: if you skip it, `/sdd:implement` falls back to in-line discovery (the original behavior).

---

## Why use it

`/sdd:implement` Step 4 ("Identify Target Files") is typically the most token-expensive part of an implementation run — it scans the repo every time. `/sdd:plan` does that work **once** and writes the result to a reviewable artifact. Subsequent `/sdd:implement` runs read the plan instead of re-discovering.

Concrete benefits:

- **Token savings on multi-pass features** — discovery happens once
- **Review checkpoint** — you can edit the plan before any code is written
- **`implementation-cache.json` pre-seeded** — gets populated proactively, not reactively

---

## When to use

- Medium-to-large features (3+ files touched)
- Features where you want to review the plan before code is generated
- Before any multi-pass `/sdd:implement` run

**Skip when:**
- One-file changes
- Quick bugfixes
- The spec's Implementation Context is already very explicit

---

## Prerequisites

Required artifacts (created by `/sdd:start`):

- `.specwork/_state/<slug>-state.json`
- `.specwork/_state/<slug>-rules.json`
- `.specwork/_state/<slug>-implementation-cache.json`
- `.specwork/_spec/<slug>-spec.md`

All `## Open Questions` in the spec must be resolved (`- [x]`). Same gate as `/sdd:handoff`.

When the gate fires, `/sdd:plan` aborts with no writes and points at the spec using an **absolute path with a line number**, wrapped in single backticks so Claude Code's renderer colors it as a clickable token:

```text
✗ Cannot plan.

The spec contains unresolved Open Questions.
Resolve them first:
  `/abs/path/repo/.specwork/_spec/proj-15535-spec.md:42`
```

If anything is missing, `/sdd:plan` exits cleanly with no writes.

---

## Usage

```bash
# Auto-detect slug from current branch
/sdd:plan

# Explicit slug (if needed)
/sdd:plan my-feature-123
```

---

## What it produces

```text
.specwork/_plan/<slug>-plan.md
```

Structure:

- **Target Files** — table mapping file paths to the change each one needs. Some rows are tagged (see *Heuristic discovery* below)
- **Approach** — ordered, plain-language steps (derived from spec's `## Behavior`). High-risk steps are prefixed `⚠ HIGH RISK (<signal>)`
- **Out-of-Plan Files** — explicit exclusions from spec's `## Out of scope` / `## Expected Change Scope > Avoid touching`
- **Open Questions** — planning-level ambiguities the discovery couldn't resolve (e.g. "two candidate classes match — which one is the target?"). `/sdd:implement` blocks on these the same way it blocks on spec Open Questions
- **Risk Assessment** — present only when Step 6 detected high-risk signals. Lists the signals, the affected Approach steps, and recommends isolated commits + local validation
- **Risks / Constraints** — free-form notes for misc concerns the structured signals didn't capture

The plan is **living**: `/sdd:implement` may append target files or update steps if it detects drift during implementation (e.g. an additional file needs to change).

### Heuristic discovery

`/sdd:plan` runs six discovery heuristics during Step 5 (Targeted Discovery) to catch files the spec doesn't mention explicitly but that the implementation will need (the sixth, risk assessment, is described last):

> **Stack scope — currently Java-focused.** `lib/plan.py` detects the stack and several heuristics no-op on non-Java repos. On a TS/React/Node project the Java-only ones simply add nothing:
> - `[infra]` — **Java/Spring only** (`@ControllerAdvice` / `*ExceptionHandler.java`; no portable analog).
> - `[mock-consumer]` — **Java only** (skipped entirely when the stack isn't Java).
> - `[reference-update]` — **stack-agnostic** literal grep.
> - **Naming guard** — **stack-aware** (separate Java and Node/frontend branches).
> - **Spec consistency** — **stack-agnostic** (pure text analysis).
> - **Risk assessment** — **mixed** (DB-migration and concurrency signals lean Java; frontend signals are included).

**Cross-cutting infrastructure (`[infra]`)** — if the spec mentions a specific non-2xx HTTP status (`404`, `401`, `403`, etc.) or response language ("not found", "forbidden", "unauthorized"), `/sdd:plan` searches for global exception handlers (`*ExceptionHandler.java`, `*ControllerAdvice.java`) and adds them to Target Files tagged `[infra]`. Reason: Spring projects typically catch broad `Exception` types and return `500`; making a route return a specific code usually requires editing the handler.

**Blast radius (`[mock-consumer]`)** — for each `*Service.java` / `*Repository.java` / `*Client.java` in Target Files, `/sdd:plan` runs a two-pass scan over `src/test` and `src/intTest`: first finds files that reference the class name, then keeps only those that use any Mockito-style idiom — `mock(...)`, `spy(...)`, `verify(...)`, `when(...)`, `given(...)`, `doReturn/doThrow/doNothing/doAnswer(...)`, or any of `@Mock`, `@Spy`, `@MockBean`, `@SpyBean`, `@MockitoBean`, `@MockitoSpyBean`, `@InjectMocks`. Matches are added as Target Files tagged `[mock-consumer]`. Reason: changing a method signature on a mocked or spied class breaks the compile of `verify`, `when`, `given` chains even when the mock itself is declared in a parent class or `@BeforeEach` helper.

**Reference grep (`[reference-update]`)** — when the spec implies renaming or removing an endpoint, path, constant, method, or column, `/sdd:plan` runs a literal `grep -rF` for the old token across source files (`*.java`, `*.kt`, `*.ts`, `*.tsx` — the extensions `lib/plan.py` actually scans). Every hit is added to Target Files tagged `[reference-update]`. Reason: log strings, retry hints, documentation, and integration tests that hard-code the old value are easy to miss with class-level discovery and leave the codebase pointing at a dead endpoint.

**Existing test file detection (naming guard)** — before proposing a new test file for any production class, `/sdd:plan` searches `src/test/`, `src/intTest/`, `src/integrationTest/` for an existing test with any common suffix (`Test`, `IT`, `Tests`, `Spec`). If a match exists, the plan modifies that file instead of creating a duplicate. If no match exists, the plan derives the project's dominant suffix and uses it for the new file. This is a path guard rather than a file-adder, so it does not add a new tag — it adjusts existing test rows in place.

**Spec consistency check** — scans the spec body for pairs of requirements that are typically logically incompatible without explicit reconciliation: `idempotent + per-call side effect`, `remove + still-referenced`, `atomic + multi-step` without coordinator, `cache + always fresh` without invalidation. When a pair is detected in separate paragraphs (with no resolver pattern present), `/sdd:plan` appends a plan-level Open Question forcing the user to resolve the tension in the spec before `/sdd:implement` can run. Unlike the other four, this heuristic does not add files — it adds OQs. The pair list is intentionally conservative to minimize false positives.

These heuristics were added to close real gaps surfaced by external-executor validation: the first two by Gemini's 2026-05-18 handoff review; `[reference-update]` and the naming guard by independent reviews of the same execution pack by Codex (2026-05-18) and Gemini (2026-05-19); and the consistency check by Gemini's 2026-05-19 review (single-AI signal, conservative pair list). They run aggressively — false positives on file-discovery heuristics are cheap (the executor verifies the file is already correct), but missing them caused mid-implementation compile failures and out-of-plan repairs in the validation runs.

**Risk assessment (`[⚠ risk:<signal>]`)** — Step 6 scans the spec body and the discovered target file paths for high-risk signals: `db-migration`, `auth-security`, `breaking-api`, `data-destructive`, `concurrency`. When any fire, matching Target Files get the `[⚠ risk:<signal>]` tag and the corresponding Approach steps are prefixed `⚠ HIGH RISK (<signal>)`. A new `## Risk Assessment` section in the plan summarizes the signals and recommends a safer workflow: commit risky steps in isolation and run the test suite locally after each, not only at `/sdd:mr`. The detection runs aggressively but never invents risk — if Step 6 produces no signals, the entire Risk Assessment section is omitted.

`/sdd:implement` reads file paths from Target Files normally; tags are advisory annotations for human reviewers and for `/sdd:handoff` to surface in the execution pack.

### Two layers of Open Questions

| Layer | Where | Examples |
|---|---|---|
| Spec | `.specwork/_spec/<slug>-spec.md` `## Open Questions` | "Should auto-reset clear `openedReason`?" — business behavior |
| Plan | `.specwork/_plan/<slug>-plan.md` `## Open Questions` | "Two candidate classes match — which is the target?" — implementation path |

`/sdd:implement` Step 3 checks **both** files. A single unresolved item in either blocks the run.

---

## How `/sdd:implement` uses the plan

If `.specwork/_plan/<slug>-plan.md` exists, `/sdd:implement` reads the **Target Files** table as the source of truth instead of re-discovering. The `implementation-cache.json` (also populated by `/sdd:plan`) gives the cache-first targeting guidance an additional head start.

If the plan is missing, `/sdd:implement` falls back to its current in-line discovery. No regression for users who skip `/sdd:plan`.

---

## Re-running `/sdd:plan`

`/sdd:plan` is **idempotent**:

- The plan file is overwritten with a fresh draft
- `implementation-cache.json` remains append-only — re-running does **not** erase prior cache entries

Re-run after:
- Significant spec edits
- A new Open Question was added and resolved
- `/sdd:implement` reported drift you want consolidated into a fresh plan

---

## Hard Rules

- Does not edit source code — `/sdd:plan` is read-only against the codebase
- No repo-wide scans — every `find` / `grep` is path-scoped
- No invented file paths — unconfirmed candidates are marked `[UNVERIFIED]`
- No new business decisions — the Approach must be derivable from the spec

---

## Pipeline Position

```
/sdd:start
/sdd:plan        ← you are here (optional)
/sdd:implement → /sdd:commit   (repeat per pass)
/sdd:test-design   (optional)
/sdd:test-impl     (optional)
/sdd:code-review   (optional)
/sdd:mr → /sdd:mr-address → /sdd:close
```

---

## Related Skills

- `start` — writes the state that `/sdd:plan` consumes
- `spec` — drafts and refines the spec `/sdd:plan` reads
- `implement` — reads the plan and implements (falls back to in-line discovery if no plan)
- `handoff` — packages artifacts for an external executor; benefits from the pre-populated cache
