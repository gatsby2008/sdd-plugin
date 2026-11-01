# State

Shows a compact snapshot of the active pipeline branch:
- current state
- blockers
- next best step

Use it any time you need quick orientation.

---

## Usage

```bash
/sdd:state
/sdd:state PROJ-15535
```

---

## What It Checks

- current branch and ticket/slug
- `.specwork/` artifacts
- open question counts
- review verdicts (if present)
- `git status` and recent commits
- orphan pipelines left in `.specwork/` whose work already landed

---

## Default Output

```text
Branch: feature/PROJ-15535
Spec:   ✓ proj-15535-spec.md (2 open / 1 resolved OQs)
        `/abs/path/repo/.specwork/_spec/proj-15535-spec.md:42`  ← Open Questions
Plan:   ✓ proj-15535-plan.md (1 open OQ)
        `/abs/path/repo/.specwork/_plan/proj-15535-plan.md:88`  ← Open Questions
Tree:   clean
Next:   /sdd:plan (recommended, can skip)
        /sdd:implement
```

When the spec or plan has **one or more open** questions, the next line shows the **absolute path to the `## Open Questions` heading with a line number**, wrapped in single backticks so Claude Code's renderer colors it as a clickable token. The line is omitted when the artifact has no `## Open Questions` section, when all items are resolved, or when the artifact itself doesn't exist.

`Next:` uses the dual form (recommended + skip target) when the recommended next step is optional (`/sdd:plan`, `/sdd:test-design`, `/sdd:test-impl`) and the user could reasonably jump straight to the next non-optional step. Otherwise it prints a single command. See `SKILL.md` for the full rendering rules.

Detailed output is only needed when the user asks for it or when a blocker needs context.

---

## Stale Leftovers

`.specwork/` is gitignored, so it survives `git checkout` and outlives the branch it belongs to. Merge a feature without running `/sdd:close` and its state stays on disk — where it later blocks `/sdd:start` from beginning anything new. `/sdd:state` surfaces those leftovers so you find them while orienting, not as a refusal later:

```text
Tree:   clean
Stale:  2 orphan pipelines in .specwork/ — their work already landed
        • PROJ-15500 (feature/PROJ-15500) — merged into development
        • PROJ-15490 (feature/PROJ-15490) — branch no longer exists locally
        Clear each from its own branch, or from its base, with /sdd:close.
Next:   /sdd:implement
```

The block appears **only** when there is something to report, and never as a blocker — leftovers belong to other branches, so `Next:` is unaffected. It is a warning, not a verdict: the merge state is inferred from git alone, and a branch renamed without `/sdd:resync` looks the same as one merged and deleted. `/sdd:close` re-checks the real MR state via `glab` before deleting anything.

---

## Rules

- Prefer counts and symbols over long tables
- Show review verdicts as `PASS`, `PASS WITH WARNINGS`, or `FAIL`
- Show ADR warnings only when uncommitted files exist in `docs/adr/`
- Use the dual `Next:` form only when the recommended step is optional and a distinct fallback exists
- Show the `Stale:` block only when there are orphan pipelines whose work already landed

---

## Troubleshooting

**No pipeline context detected**
Switch to the branch that owns the active `.specwork` state and rerun. If the `Stale:` block names that branch as already merged, run `/sdd:close` from it instead — there is nothing left to resume.

**Working tree is always dirty**
Stage or stash local changes, then rerun.

---

## Related Skills

- `/sdd:start` — bootstraps pipeline state
- `/sdd:spec` — drafts and refines the spec
- `/sdd:implement` — applies changes
- `/sdd:commit` — records commits on the branch
- `/sdd:close` — clears `.specwork/`; the fix for anything reported under `Stale:`
- `/sdd:whatnext` — quick next-step guidance
