# SDD Concepts — Gates, Cache, Handoff & Artifacts

The load-bearing ideas the pipeline is built on. For the command-by-command flow
see [pipeline.md](pipeline.md); for installation see [setup.md](setup.md).

---

## Skills vs agents

The plugin is built from two execution primitives; knowing which is which explains
why the pieces are wired the way they are.

| | Skill (`/sdd:*`) | Agent (`sdd:java:*`, `sdd:ui:*`) |
|---|---|---|
| Runs in | the **main conversation** — shares your context | an **isolated** context window; sees only what it's passed |
| Returns | work inline in the thread | one consolidated result to the caller |
| Invoked | slash command / description match | Task tool or `@`-mention, usually by a skill |
| Config | `allowed-tools`, `argument-hint` | `tools`, `model` (can pin), `color` |
| Parallel | one procedure | many can fan out in parallel |

"Agent" and "subagent" are the same artifact: **subagent** is Claude Code's term for
an agent when it is invoked via the `Task` tool from another agent (the reviewers are
subagents *relative to* the main conversation that launches them).

Rule of thumb:

> Needs a sandbox + parallelism + a single consolidated verdict → **agent**.
> A procedure run in the current thread with full context → **skill**.

This is why the review commands are skills that *orchestrate*, while the stack
reviewers are agents that run isolated on just the diff and report back — keeping
their large context out of your main thread (lower per-run tokens). The review packs
stay skills, referenced by name and never loaded into the agents, for the same reason.

---

## Open Questions

**Open Questions are unresolved markdown checkboxes (`- [ ]`) in `spec.md`** (and,
optionally, in `plan.md`). They encode the pipeline's core rule:

> Never implement through ambiguity.

Unresolved Open Questions **block `/sdd:plan` and `/sdd:implement`** until answered.
`/sdd:spec` is the canonical way to draft and resolve them — feed answers back as a
file, a Jira ticket, a paste, or free text. Refine mode is **append-only** on the
Open Questions list: it can resolve existing boxes and add new ones, but never
silently drops them.

The payoff is fewer hallucinated requirements, wrong assumptions, rework, and
scope drift — most implementation errors come from unclear requirements, not weak
models.

---

## Gates

Seven gates keep the pipeline honest. The five strict ones **abort with no writes**
rather than guessing; the two marked *(advisory)* only report and never block.

| Gate | Where | Rule |
|---|---|---|
| **Open Questions** | `/sdd:plan`, `/sdd:implement` | Any unchecked `- [ ]` in `spec.md` (or `plan.md`) blocks the step |
| **Plan required** | `/sdd:implement` | Only for pipelines triaged `high-risk` (`plan_required` in `_state/<slug>-path.json`): blocks until `plan.md` exists. Other tiers keep the plan optional |
| **Plan staleness** | `/sdd:implement` | If `plan.md` exists and is older than `spec.md` (`spec.md` mtime > `plan.md` mtime — typically after `/sdd:spec` or a manual spec edit), the step blocks. Re-run `/sdd:plan`, or `rm` the plan to fall back to inline discovery |
| **Test coverage** | `/sdd:commit` + `PreToolUse` hook | A changed production class (Java `src/main/*.java`, frontend `*.tsx/.ts`) with no matching test (`*Test`/`*IT`, `*.test`/`*.spec`) blocks the commit. DTOs, config, entities, and barrels are excluded. The only escape is a per-class waiver-with-reason in `.specwork/_test/<slug>-coverage-waivers.json` (pipeline) or `.sdd-coverage-waivers.json` (standalone) |
| **Spec conformance** *(advisory)* | `/sdd:commit` | Lists spec Behaviors (`**B1**`, `**B2**`, … in `## Behavior`) that no test tags with `spec: B<n>` in lines added on the branch. Never blocks; silent for specs without ids. Deterministic grep (`lib/conformance.py`) — no LLM review |
| **High-risk auditor** *(advisory)* | `/sdd:commit` | Only for pipelines triaged `high-risk`: runs `/sdd:code-review` (report-only) once per distinct staged diff and stamps a receipt (`_review/<slug>-audit.json`: diff fingerprint + verdict). Never blocks; other tiers pay no extra tokens |
| **Quality (`check.sh`)** | `/sdd:mr` + `PreToolUse` hook | `commands/check.sh` (the project's full validation suite) must pass before a `git push`. `/sdd:mr` runs it, then stamps the validated HEAD; the hook blocks any push whose HEAD wasn't stamped. No-ops when the repo has no `commands/check.sh` |

`/sdd:spec` also **warns** (does not block) when `plan.md` is stale or the tree has
uncommitted changes — the actual block happens later, in `/sdd:implement`.

The test-coverage gate runs in two places, on purpose. As a `/sdd:commit` step it
covers the normal flow; as a `PreToolUse(Bash)` hook (`hooks/coverage-gate.sh`) it
also intercepts a *raw* `git commit` — including `git commit --no-verify`, which a
git `pre-commit` hook could not stop, because the hook fires on the Bash tool call
before git runs. The hook is scoped to an active pipeline (it no-ops unless
`.specwork/` is present) so it never interferes with non-SDD repos, and it fails
open on any internal error so a gate bug can never wedge a commit.

The quality gate (`commands/check.sh`) follows the same two-place pattern for
`git push`, but with a twist: `check.sh` runs the full suite (minutes), too slow
to re-run inside a hook (it would blow the hook timeout and double the build
`/sdd:mr` already ran). So the work is split — `/sdd:mr` *runs* `check.sh` and, on
success, stamps the validated HEAD sha into `.specwork/_state/<slug>-validated.json`
(via `lib/validation.py`); the `PreToolUse(Bash)` hook (`hooks/push-gate.sh`)
*enforces* cheaply, blocking any `git push` whose `HEAD` doesn't match that stamp.
Like the coverage hook it is scoped to `.specwork/`, fails open, and additionally
no-ops when the repo defines no `commands/check.sh` (nothing to enforce). This is
why a raw `git push` — or `/sdd:commit`'s push offer — on an unvalidated HEAD is
blocked, while the `/sdd:mr` flow passes silently.

### Awareness hooks (non-blocking)

Not every hook is a gate — two hooks exist purely to keep the agent oriented.

The `SessionStart` hook `hooks/pipeline-status.sh` prints a compact status block
when the current branch has an active pipeline — branch, slug, spec/plan state,
open-question count, and the next step (its next-step logic mirrors the early
gates so it never contradicts `/sdd:state`). `SessionStart` stdout is added to
the session context, so this re-orients the model at startup/resume/clear at zero
per-prompt cost (the reason it's a `SessionStart` hook, not a `UserPromptSubmit`
one that would tax every turn). It is silent outside a pipeline and omits jira/mr
config checks on purpose — both have sane defaults, so warning would be noise.

The `PostToolUse(Bash)` hook `hooks/resync-reminder.sh`
catches a **footgun, not a violation**: `.specwork/` is branch-keyed but
gitignored, so it does *not* move when you change branches. After a `git branch -m`
(rename) or a `git checkout`/`git switch` to another branch, the on-disk pipeline
still belongs to the old branch. The hook detects this *accurately* — it fires only
when **no** `state.json` records the *current* branch (so `git checkout -- file`
and switching back stay silent) — and surfaces a `systemMessage` (never blocks; the
branch change already happened). The wording leads with the right fix for the verb:
**rename → `/sdd:resync`**, **switch → `/sdd:pause` + `/sdd:restore`**. Because it
runs after every Bash call, the shell entrypoint pre-filters on the raw payload and
only starts Python when the command mentions `checkout`/`switch`/`branch`.

The `PreToolUse(Edit|Write)` hook `hooks/branch-mismatch-warn.sh` closes the same
footgun on the path the others don't cover: plain file edits. The `/sdd:*` skills
each check pipeline ownership before acting, and the `SessionStart` banner reports
a mismatch when the session opens — but code changed through `Edit`/`Write` alone
passes neither. The first time a file is edited on a branch whose `.specwork/`
belongs to *another* branch, it surfaces a `systemMessage` naming that pipeline and
the two ways out (`/sdd:pause`, `/sdd:close`). It **never blocks** — editing on such
a branch is legitimate work (a hotfix, an unrelated issue); what needs a decision is
the leftover pipeline, not the edit. It fires at most once per (session, branch,
pipeline) because the trigger is a *state you sit in*, not a repeatable event;
switching branches or a different pipeline landing on disk re-arms it. The marker
lives under `$CLAUDE_PLUGIN_DATA` (plugin-private state — never `~/.claude`), and
the shell entrypoint exits before starting Python when there is no `.specwork/_state`
at all, so non-SDD repos pay nothing.

Ownership itself is never decided by comparing branch names: every one of these
paths calls `gates.pipeline_branch_status()`, which distinguishes *owns it*,
*nothing on disk*, *sitting on the pipeline's own `base_branch`* (the post-merge
`/sdd:close` spot — not a mismatch), and *someone else's pipeline*.

---

## Implementation Cache

Repository memory that avoids re-discovering structure on every run.

- Initialized by `/sdd:start`; seeded by `/sdd:plan` and by `/sdd:spec` (when files are passed).
- Path: `.specwork/_state/<slug>-implementation-cache.json`.
- Stores: repositories, common patterns, related tests, similar classes.
- Benefit: less repo scanning, lower token consumption, faster context loading.

---

## Handoff & the Execution Pack

`/sdd:handoff` packages spec + rules + context into a **model-agnostic execution
contract** at `.specwork/_handoff/<slug>-execution-pack.md` (plus `.json`
metadata). It exits without changes if required artifacts are missing.

Use it when handing work to another agent (Gemini, Copilot, Codex, Claude). The
pack contains: Feature Summary · Implementation Scope · Files · Dependencies ·
Rules · Acceptance Criteria · Risks · **Known Blockers / Escalations**.

The *Known Blockers / Escalations* section is sourced from
`_progress/escalations.md`, so an external executor doesn't repeat failed
attempts. This is what makes `AI → Execution Pack → AI` deterministic instead of
lossy.

---

## Artifacts

### Transient (`.specwork/`, gitignored — lives in the *target* repo)

- `_state/<slug>-state.json` — branch metadata (and the `non_interactive` flag)
- `_state/<slug>-rules.json` — compiled service rules
- `_state/<slug>-implementation-cache.json` — implementation memory (repositories, patterns, related tests, similar classes)
- `_state/<slug>-path.json` — triage tier + recommended path, written by `/sdd:spec` (draft); `plan_required` drives the plan-required gate
- `_state/<slug>-validated.json` — HEAD sha stamped by `/sdd:mr` after a green `check.sh`; read by the push-gate hook
- `_spec/<slug>-spec.md` — implementation specification
- `_spec/<slug>-source.md` — raw input from Jira or free text
- `_plan/<slug>-plan.md` — implementation plan from `/sdd:plan` (Target Files, Approach, Risks)
- `_test/<slug>-test-design.md` — designed test cases from `/sdd:test-design`; consumed by `/sdd:test-impl` (high-risk flow)
- `_test/<slug>-coverage-waivers.json` — per-class waivers (path → reason) for the `/sdd:commit` test-coverage gate
- `_progress/<slug>-context.md` — optional human-authored execution context
- `_progress/escalations.md` — append-only log of `/sdd:implement` escalations (auto-written when retries are exhausted; consumed by `/sdd:handoff` as *Known Blockers*)
- `_review/<slug>-code-review.md` — code review output (optional)
- `_review/<slug>-audit.json` — high-risk auditor receipt (diff fingerprint + verdict) from `/sdd:commit`
- `_review/<slug>-mr-address.md` — review comment resolution
- `_handoff/<slug>-execution-pack.md` / `.json` — handoff contract + metadata (optional)

### Permanent

- `docs/specs/<slug>-spec.md` — committed in the target repo, published by `/sdd:mr` when a pipeline spec exists
- ADRs, catalogs, specs and investigations from the `/sdd:doc-*` commands live in the central registry (`$CLAUDE_DOC_HOME`), not in the repo — see [Documentation & Knowledge Registry](#documentation--knowledge-registry)

### `_progress/` — working execution memory

`_progress/` is **mutable runtime memory**, distinct from the deterministic state
in `_state/` and the contract in `_spec/`. It captures what happened during
execution: blockers, decisions, hints. `/sdd:close` wipes it together with the rest
of `.specwork/` when the feature merges.

Today only one file is auto-populated:

- `escalations.md` — `/sdd:implement` appends a dated entry whenever its Escalation
  Policy triggers (test loops, infrastructure failures, persistent retries).
  `/sdd:handoff` reads it and surfaces a *Known Blockers / Escalations* section in
  the execution capsule. The file is append-only within a feature; never overwrite
  or summarize prior entries.

---

## Documentation & Knowledge Registry

`/sdd:doc-catalog`, `/sdd:doc-catalog-query`, `/sdd:doc-adr`, `/sdd:doc-adr-query`,
`/sdd:doc-spec`, `/sdd:doc-spec-query`, `/sdd:doc-investigation`, and
`/sdd:doc-investigation-query` form the documentation family. Each artifact has two
commands following one shape: `doc-<artifact>` creates and stores it in the central
registry (with `list` as a subcommand), and `doc-<artifact>-query` reads the registry
back. There is no separate `publish` step — creating an artifact stores it.

They operate on a shared registry (not `.specwork/` and **not** the service repo's
working tree — nothing is committed alongside the code), so they work on any branch at
any time. The registry root is `$CLAUDE_DOC_HOME` (defaults to `~/.claude`): service
catalogs land in `$CLAUDE_DOC_HOME/service-catalog`, ADRs in
`$CLAUDE_DOC_HOME/adr-registry`, specs in `$CLAUDE_DOC_HOME/spec-registry`,
investigations in `$CLAUDE_DOC_HOME/investigation-registry`. Set `CLAUDE_DOC_HOME` to a
shared/synced path to share across the team. They install with the rest of the plugin
via `/plugin install`.

---

## Reverting a Failed Implementation

You reach the pre-`/sdd:commit` review, see the implementation is wrong, and want to
**discard the code changes but keep the pipeline state** (`.specwork/`) so you can
re-spec and re-implement.

Use **`/sdd:undo`** — it previews what will be discarded, confirms, and discards it
while preserving `.specwork/`:

```bash
/sdd:undo            # reversible: stash the implementation
/sdd:undo --restore  # changed your mind — bring it back (redo)
/sdd:undo --hard     # irreversible discard
```

`/sdd:close` does the *opposite* (wipes `.specwork/`, leaves the code), so it is not
the tool here.

### What `/sdd:undo` does under the hood (manual fallback)

The safety net is that **`.specwork/` is gitignored** (`start.py` guarantees it),
so it never enters a stash and `git clean -fd` skips it — only `git clean -fdx`
would remove ignored files. At this point all changes are uncommitted: modified
classes are *tracked*, new classes/tests from `/sdd:implement` are *untracked but
not ignored*. The reversible default is a stash; the equivalent by hand:

```bash
git clean -fdn                       # DRY RUN — list what would be deleted; nothing removed
git stash push --include-untracked   # reversible: stash code changes (.specwork/ stays)
# …or, to discard irreversibly:
git restore . && git clean -fd       # revert tracked edits + delete new files
git status --ignored --short         # confirm only .specwork/ remains
```

Then re-spec from the preserved state:

```bash
/sdd:spec <correction / new context>   # refine the spec (resolve/append Open Questions)
/sdd:plan                              # re-run: spec is now newer than plan (stale gate)
/sdd:implement
```

`state.json`, `rules.json`, `implementation-cache.json`, and `source.md` are
untouched, so only the failed implementation is discarded. Remember the **plan
staleness gate**: after `/sdd:spec`, an existing `plan.md` blocks `/sdd:implement`
until `/sdd:plan` is re-run (or the plan is deleted).
