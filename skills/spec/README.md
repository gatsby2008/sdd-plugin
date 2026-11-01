# Spec

Own `.specwork/_spec/<slug>-spec.md`. `/sdd:start` captures the raw source; `/sdd:spec` drafts the canonical spec from it and keeps it current. Two modes, chosen automatically by whether the spec file exists yet:

- **Draft** (no spec.md): generate the first spec from `source.md` + the template, fold in any context, then run triage.
- **Refine** (spec.md exists): integrate new context in place — append-only on Open Questions. Refine with no arguments is a strict no-op.

## Usage

```bash
/sdd:spec                                          # draft from source.md, or no-op if already drafted
/sdd:spec src/.../OrderController.java             # add a Java file as scope context
/sdd:spec src/components/UserProfile.tsx           # or a frontend file — detection is stack-neutral
/sdd:spec jira IR-122                              # pull in a Jira ticket
/sdd:spec paste                                    # paste free text
/sdd:spec "PII must be masked in logs"             # inline free text
/sdd:spec OrderController.java jira IR-122 "use UUID for personId"   # mix inputs
/sdd:spec --tier standard "Behavior only says it does NOT publish to Kafka"   # force the triage tier
/sdd:spec --tier auto                              # back to the automatic tier
```

## When to use

- **Right after `/sdd:start`** — draft the spec from the captured source.
- The spec has unresolved Open Questions you can now answer.
- The work touches a class/endpoint/service that wasn't in `## Implementation Context`.
- A reviewer raises a constraint that should land in `## Safe Constraints`.
- `/sdd:plan` or `/sdd:implement` surfaced drift to reconcile into the spec.

When **not** to use:
- The pipeline hasn't started — run `/sdd:start` first.
- You just want a fresh plan — re-run `/sdd:plan` directly (it is idempotent).
- You need to change branch / ticket / rules — those belong to `/sdd:start` / `/sdd:resync`.

## What it does

1. Detects draft vs refine mode by the presence of `spec.md`.
2. **Draft:** writes the first spec from `source.md` + a stack-aware template + any context, then runs triage (`triage.py`) to classify complexity and recommend a path. Frontend projects use `templates/spec-frontend.md` (adds Components, Props & State, Routes, Design Reference, Accessibility Requirements); java/node/unknown use `templates/spec.md`.
3. **Refine:** integrates the input — resolves Open Questions, expands `## Implementation Context`, appends to `## Safe Constraints`, adjusts `## Expected Change Scope`.
4. Appends newly confirmed classes / repos / tests to `implementation-cache.json` via `gates.py merge-cache` (append-only).
5. **Refine:** detects downstream staleness via `gates.py check-staleness` — warns if `plan.md` is older than the spec, or the working tree is dirty.
6. Prints a draft summary (with triage) or a categorized refine diff.

Staleness is **mtime-based**: writing the spec bumps its mtime, which is the only signal downstream gates need. There is no separate timestamp bump.

## What it never does

- Never deletes user-authored content. Resolutions append; they don't remove.
- Never modifies `source.md` or `rules.json` (those belong to `/sdd:start`).
- Never deletes or renames `plan.md`. Only warns the user to re-run `/sdd:plan`.
- Never touches git state. No commits, no branches, no merges.
- Refine + zero args never writes and never bumps the mtime.

## Requirements

The pipeline must be initialized — `state.json`, `rules.json`, `implementation-cache.json`, and `source.md` must exist (all written by `/sdd:start`). `spec.md` is **not** required; its absence selects draft mode. If the bootstrap artifacts are missing, run `/sdd:start` first.

## Related Skills

- `/sdd:start` — captures the source and state; does **not** create spec.md
- `/sdd:plan` — idempotent re-run, recommended after a refine that changed scope
- `/sdd:implement` — blocks on unresolved Open Questions; closing them unblocks it
- `/sdd:handoff` — packages the latest spec; run `/sdd:spec` before handoff to keep the pack fresh
- the old `spec-refine` alias has been removed — use `/sdd:spec` (refine mode) instead
