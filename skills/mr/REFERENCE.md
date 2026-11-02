# mr — Reference

Reference material for `/sdd:mr`. `SKILL.md` is the execution flow and holds every step, gate, and rule; this file holds what a run reads only when it needs it. Each section names the step that points to it.

---

## Foreign-pipeline warning

**Resolve the pipeline** — `has_any_pipeline` true, `owns_pipeline` false. Print before the pre-push validation:

```
⚠ .specwork/ belongs to '<recorded_branch>' (slug '<slug>'), not '<BRANCH>'.
  It's gitignored, so it didn't move when you switched branches.

  Opening this MR from commits only. Not publishing '<slug>'s spec: it would be
  committed into this branch, shipped in this MR's diff, and stored in the
  cross-service spec registry under this service's key.

  To clean this up:
    • /sdd:pause  — stash '<slug>' to resume it later (its MR is still open)
    • /sdd:close  — clear it (its MR merged, or the work was abandoned)
```

---

## Repair Loop

A bounded loop against `check.sh`: fix the code, re-check, at most **3 attempts**.
`check.sh` is the metric, so the loop must not be able to edit it. `lib/repair.py`
holds the loop in code: its state lives in the git dir, one file per branch
(`.git/sdd-repair-<branch>-<hash>.json`, never committed); `pre` re-runs the guard
and counts every attempt whose content changed (re-checking the same red content is
free), and `validation.py record` refuses to stamp HEAD while the loop is open —
so the push hook blocks any push, a raw `git push` included, until `green` closed it.
This raises the bar; it is not tamper-proof (a human can `reset`). State left by
deleted branches is pruned whenever a new loop opens.

The guard rejects: any change to `commands/check.sh` or to a test-runner config
(`pytest.ini`, `conftest.py`, `jest.config.*`, `.mocharc*` …); an added line that
excludes or deselects tests in a build file (`pyproject.toml`, `package.json`,
`pom.xml`, `build.gradle` …); a removed or modified line in an existing test file;
a deleted (or renamed) test file; and an added skip/disable/focus marker. Files that
were already untracked when the loop opened (`.DS_Store`, local scratch) are left out
and never block the close — including an untracked test file whose skip marker
predates the loop: the guard judges only what the repair changes.

**Ask first, unless non-interactive.** Detect the mode the same way `/sdd:commit` does:

```bash
if [ "${SDD_NON_INTERACTIVE:-0}" != "1" ] && [ -n "$SLUG" ]; then
  SDD_MODE="$(python3 ${CLAUDE_PLUGIN_ROOT}/lib/gates.py non-interactive "$SLUG" 2>/dev/null || echo 0)"
  [ "$SDD_MODE" = "1" ] && export SDD_NON_INTERACTIVE=1
fi
```

- Interactive, on the first failure → ask:

  ```text
  ✗ check.sh failed (<one-line summary of what failed>).
    Try to repair it? (max 3 attempts, without touching check.sh, test configs or existing tests) [y/N]
  ```

  On anything but yes, drop the loop and stop — the user fixes it by hand:

  ```bash
  python3 ${CLAUDE_PLUGIN_ROOT}/lib/repair.py reset
  ```

- Non-interactive (`/sdd:auto`) → start without asking.

Not offered with `--skip-validation`, when `commands/check.sh` is missing, or after a
post-rebase failure (Branch Sync Check) — those keep their current behavior.

**Each attempt:**

1. Read the `check.sh` output and find the cause (failing test, compile error, lint).
2. Fix the **code**, staying inside the spec (and plan, when present). Allowed: production
   code, and *new* lines or files in tests. Not allowed: anything the guard rejects (above).
   Never special-case the failing test's inputs in production code (`if price == 200: …`)
   — the guard cannot see that, so it is on you. If the test itself looks wrong, or the fix
   needs a business decision the spec does not settle, stop — that is an Open Question,
   not a repair.
3. Re-run SKILL.md § Pre-Push Validation from step 1. Its `pre` step runs
   the guard and counts the attempt (unchanged content costs no attempt, but `check.sh`
   still re-runs in full — do not re-run just to read the output again); it ends red (next attempt, or exhausted) or green
   (commit, then push).

**Stopped** (guard rejection or exhausted) → do not push; report the reason and the last
failure. The attempts' changes stay in the working tree for the user (`/sdd:undo`
discards them; `repair.py reset` drops the loop once a human has reviewed them).

---

## Related Skills

- `commit` — finalize commits before MR
- `mr-address` — handle review comments after MR opens
- `close` — clean `.specwork/` after merge
