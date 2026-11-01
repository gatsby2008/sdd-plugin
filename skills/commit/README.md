# Git Commit

Generates a semantic commit message for any workflow: SDD pipeline, vibe coding,
or git-only branches.

Commits all accumulated changes (whether from one `/sdd:implement` pass or several)
in a single, well-formatted commit. Works the same way with or without `.specwork/`
state — the only thing that changes is whether the ticket ID comes from the spec
or from the branch name.

---

## Prerequisites

- On the active pipeline branch recorded in `.specwork/_state/<slug>-state.json` when using SDD (optional for vibe coding / git-only)
- Either: files staged with `git add`, or unstaged modifications/new files that `/sdd:commit` will offer to auto-stage from `git status`

---

## Usage

```bash
# After /sdd:implement — no manual git add needed
/sdd:commit

# After manual edits — stage first, then run
git add <files>
/sdd:commit
```

---

## What It Produces

A commit message in this format:

```
[TICKET-ID] <type>: <concise description>

<optional body explaining why, not just what>
```

### Commit types

| Type | When to use |
|---|---|
| `feat` | New feature or behavior |
| `fix` | Bug fix |
| `refactor` | Code change with no behavior change |
| `docs` | Documentation only |
| `test` | Test code only |
| `perf` | Performance improvement |

### Ticket ID extraction

Extracted automatically from the branch name:
- `feature/PROJ-15535-consent` → `[PROJ-15535]`
- `feature/PROJ-15535` → `[PROJ-15535]`
- `bugfix/PROJ-15535-retry` → `[PROJ-15535]`
- No ticket found → `[NO-TICKET]`

---

## Auto-Stage

If nothing is staged, `/sdd:commit` reads `git status --porcelain` and offers to
stage every modified or new file:

```
Nothing staged. Files with unstaged changes:

  M  src/main/java/.../ConsentService.java
  A  src/main/java/.../ConsentRequest.java
  A  src/test/java/.../ConsentServiceTest.java

Stage these files? (yes / no / edit)
```

Works for any tracked files — the list mirrors `git status`, so frontend changes look identical:

```
Nothing staged. Files with unstaged changes:

  M  src/components/UserProfile.tsx
  A  src/hooks/useConsent.ts
  A  src/components/UserProfile.test.tsx
```

Choose **yes** to stage them all, **edit** to remove individual files from the
list before staging, or **no** to fall back to manual staging.

---

## Example Output

Typical workflow:

```
> /sdd:commit

Staged changes:
  modified: src/main/java/.../ConsentService.java
  new file:  src/main/java/.../ConsentController.java
  new file:  src/main/java/.../ConsentRequest.java
  new file:  src/test/java/.../ConsentServiceTest.java
  new file:  src/test/java/.../ConsentControllerTest.java

Proposed commit:
  [PROJ-15535] feat: add consent capture endpoint for lead creation

  Consent must be recorded at the time of lead creation to satisfy compliance
  requirements. Adds POST /api/v1/consent backed by ConsentService with unit
  and integration tests.

Commit? [y/n] y

Commit a1b2c3d recorded.
Push branch to origin now? (yes / no)
```

The mapping of "what was implemented" to "which commit" is preserved by git history
itself — the commit message, scope, and diff. `/sdd:mr` later uses this same history
to compose the MR description.

---

## Commit Discipline

**One logical change per commit.**
Each implementation step should ideally be one commit.
Avoid mixing migration + service + controller in a single commit.

Good examples:
```
[PROJ-15535] feat: add Flyway migration V23 for consent_flag column
[PROJ-15535] feat: add ConsentService with saveConsent logic
[PROJ-15535] feat: add ConsentController POST /api/v1/consent
[PROJ-15535] test: add unit and integration tests for consent flow
```

Bad example:
```
[PROJ-15535] feat: consent stuff
```

---

## Troubleshooting

**"Nothing staged" when running after manual edits**
Run `git add <files>` before invoking the skill. If you ran `/sdd:implement` first,
the auto-stage offer handles this automatically — answer `yes` at the prompt.

**Ticket shows as `[NO-TICKET]`**
Your branch name doesn't expose a recognizable ticket key. Rename the branch
or edit the commit message manually when prompted.

**Proposed message is too vague**
Reject it (`n`) and add context in the chat: "the reason for this change is X".
The skill will regenerate with that context.

---

## Next: Test Validation and Push

After committing, you're ready for `/sdd:mr`, which:
1. Runs full test suite validation via `bash commands/check.sh` (project-provided; see `docs/setup.md` §5 "Project validation script" — template at `${CLAUDE_PLUGIN_ROOT}/templates/check.sh.example`)
2. Pushes the branch if tests pass
3. Creates the merge request

This single pre-push validation gate prevents test failures in CI.

---

## Next Step

After committing all your changes, run:

```bash
/sdd:mr
```

This validates tests, pushes, and creates the merge request.

---

## Pipeline Position

```
/sdd:start
/sdd:implement (repeat N times)  ←  you are here
  ↓
/sdd:commit (one commit)
  ↓
/sdd:mr (validation + push + MR)
/sdd:mr-address
/sdd:close
```
