# What Next

Shows where you are in the feature development pipeline and what to do next.
Detects your current state from `.specwork/` artifacts and tells you the single
most important next action with a short explanation.

Run at any point — especially when you're not sure what comes next.

---

## Usage

```bash
/sdd:whatnext           # contextual next step
/sdd:whatnext overview  # full pipeline reference, all commands explained
```

---

## What It Detects

Reads `.specwork/` artifacts to determine pipeline state:

- Whether pipeline state has been initialized
- Whether the spec exists yet
- Whether open questions are unresolved
- Whether the branch has uncommitted changes
- Whether the branch has committed work ahead of its recorded base branch
- Whether `.specwork/` holds a pipeline from another branch, and if so whether that work already landed

Prints a pipeline diagram with checkmarks and a focused "Next step" block.
Mentions `/sdd:mr-address` only after `/sdd:mr`, when teammate feedback arrives.

### Blocked-state output

When `/sdd:whatnext` reports that `/sdd:implement` is blocked by unresolved Open Questions, the **Next step** points at the spec with an **absolute path and a line number**, wrapped in single backticks so Claude Code's renderer colors it as a clickable token:

```text
Next step:
  Resolve open questions in `/abs/path/repo/.specwork/_spec/proj-15535-spec.md:42`

  Unresolved:
    - [ ] #1 Should lookup use personUuid only, or personUuid + collateral?
    - [ ] #2 ...
```

The path is always absolute (relative paths are not clickable in the CLI / VS Code / Cursor / iTerm2 / Warp terminals). When both `spec.md` and `plan.md` have unresolved OQs, both are listed.

### Branch mismatch — two opposite answers

`.specwork/` is gitignored, so it survives `git checkout` and outlives the branch it belongs to. When the pipeline on disk isn't this branch's, `/sdd:whatnext` first works out *why*, because the two cases take opposite advice:

- **Still in flight on another branch** → switch back to it and resume. Closing it would destroy unmerged work.
- **Already merged, `/sdd:close` never run** → nothing to resume; `/sdd:close` clears it so you can start new work.

The merge state is inferred from git alone (is the branch an ancestor of its base?), so it is reported as a reason, not a verdict — a branch renamed without `/sdd:resync` looks the same as one merged and deleted, and `/sdd:whatnext` offers `/sdd:resync` in that case. `/sdd:close` re-checks the real MR state via `glab` before deleting anything.

When the current branch *does* own its pipeline and merged leftovers exist elsewhere, they change nothing — you get a single trailing note, never a blocker:

```text
Note: 1 merged pipeline still in .specwork/ (PROJ-15500) — /sdd:close clears it.
```

For the full list, run `/sdd:state`.

---

## Pipeline Position

```
Pipeline:
  /sdd:start → /sdd:implement → /sdd:commit → /sdd:test-design
  → /sdd:test-impl → /sdd:code-review → /sdd:mr → /sdd:mr-address → /sdd:close

Optional handoff:
  /sdd:handoff   # package the current execution context for another agent/model

/sdd:whatnext  ←  run at any point in the pipeline
```
