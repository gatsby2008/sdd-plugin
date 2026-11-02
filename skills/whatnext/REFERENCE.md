# whatnext — Reference

Reference material for `/sdd:whatnext`. `SKILL.md` is the contextual flow; this file holds the static reference card printed only by `/sdd:whatnext overview`.

---

## Overview Mode

When called as `/sdd:whatnext overview`, print the full pipeline reference regardless of
current branch state:

```
Feature Development Pipeline
═════════════════════════════════════════════════════════════════

SETUP (once per machine)
  /plugin install sdd@gatsby    installs the whole plugin: pipeline + reviewers + doc commands

─────────────────────────────────────────────────────────────────

FEATURE PIPELINE

  /sdd:auto                Non-interactive driver: runs the early flow
                         (start → spec → plan → implement → commit → mr) end-to-end
                         without pausing at each step. Use for small/obvious features;
                         drop back to the individual commands when you need control.

  /sdd:start PROJ-1234    Initialize the pipeline, create/select the working branch,
                         and write .specwork/_state metadata plus source/rules/cache files.
                         Does NOT write the spec — run /sdd:spec next.

  /sdd:spec                Draft the spec from the captured source (first run), or
                         feed extra context into an existing spec — files,
                         jira <TICKET>, pasted text, or free text. Draft mode runs
                         triage; refine mode resolves Open Questions, expands
                         Implementation Context, appends constraints, and warns
                         when plan.md becomes stale. Refine with no args is a no-op.
                         Review the spec before continuing — especially Open Questions.
                         

  /sdd:implement           Pick the next piece to implement with inline tests.
                         Repeat: code → test → /sdd:commit until feature is done.

  /sdd:commit              Stage changes, propose a semantic commit message, confirm.
                         Run after each /sdd:implement step.

  /sdd:test-design         [optional] Design missing test cases (gap analysis).
                         Works standalone on any branch with code changes.

  /sdd:test-impl           [optional] Implement missing test files from design doc.
                         Works standalone; does not depend on pipeline.

  /sdd:code-review         [optional] Quality and security review (Java or frontend).

  /sdd:mr                  Generate MR description, optionally publish spec to docs/specs/,
                          squash commits, push branch, create/update MR in GitLab.

  /sdd:mr-address      After the MR receives review comments: work through each
                          unresolved thread — fix, reply, or defer. Resolves in GitLab.

  /sdd:close               After the MR is merged: deletes .specwork/ artifacts.
                          Preserves published specs in docs/specs/.

  /sdd:handoff             Optional. Package spec + rules + context into a handoff file
                         for another agent/model to continue execution.

─────────────────────────────────────────────────────────────────

UTILITIES

  /sdd:state              Full status: commits, spec content, open questions.
  /sdd:whatnext                This. Shows your next step contextually.
  /sdd:pause               Need to switch context? Stashes everything (including
                         .specwork/) with a pipeline label and leaves branch
                         switching to you.
  /sdd:restore              Lists paused pipeline branches and restores the one you select.
  /sdd:resync              Sync .specwork/ artifacts with current branch.
                         Two modes:
                           /sdd:resync                         (after a manual git branch -m)
                           /sdd:resync --rename-branch feature/IR-70-foo  (atomic: rename + sync)
                         Renames files, updates state.json (id, branch, ticket,
                         input_type, internal paths). Use when a free-text feature
                         gets assigned a ticket, after a typo fix, or whenever the
                         pipeline state and the current branch diverge.

─────────────────────────────────────────────────────────────────

STANDALONE TOOLS  (independent — run on any branch, any time, no pipeline required)

  /sdd:code-review         Stack-aware quality and security review of staged+unstaged
                         changes. Auto-detects Java (build.gradle / pom.xml) or
                         Frontend (package.json) and runs the matching reviewer
                         agents in parallel. Inside the SDD pipeline, persists the
                         report to .specwork/_review/; outside, runs the same flow
                         without writing to disk. Use before committing — hotfixes,
                         config changes, or mid-implementation checks.

  /sdd:mr-review           Review a PEER's MR/PR or branch — resolves the input to a
                         diff and runs the same stack-aware quality+security review,
                         read-only, without ever touching your working tree. Use when
                         reviewing someone else's work (vs /sdd:code-review for your own).

  /sdd:undo                Discard uncommitted code changes — from /sdd:implement or
                         free-hand coding — reversibly (stash by default; --restore to
                         recover, --hard to discard for good). Works on any branch and
                         preserves .specwork/ when a pipeline is active.

  --- doc/adr commands below come from the `doc` bundle (ships with the pipeline,
      installed with the sdd plugin) ---

  /sdd:doc-adr               Capture an architectural decision: technology choice,
                         pattern adoption, compliance constraint, significant trade-off.
                         Stores it straight in the ADR registry at
                         $CLAUDE_DOC_HOME/adr-registry/<service>/ (no in-repo copy).
                         Modes: free text · /sdd:doc-adr PROJ-1234 · /sdd:doc-adr open-questions · /sdd:doc-adr list

  /sdd:doc-catalog           Generate or refresh the service catalog for the current
                         microservice. Scans REST endpoints, SQS/SNS integrations,
                         Feign clients, and scheduled jobs → stores it straight in the
                         service-catalog registry at $CLAUDE_DOC_HOME/service-catalog/
                         (default ~/.claude/; no in-repo copy). /sdd:doc-catalog list shows the registry.

  /sdd:doc-spec              Store a hand-written / standalone spec.md in the central
                         spec registry at $CLAUDE_DOC_HOME/spec-registry/<service>/
                         (default: ~/.claude/). The pipeline's /sdd:mr stores it
                         automatically; this is the vibe-coding counterpart. /sdd:doc-spec list shows the registry.

  /sdd:doc-investigation     Capture the current session's investigation into a typed
                         findings doc (bug or exploration) at
                         $CLAUDE_DOC_HOME/investigation-registry/<service>/. Auto-detects
                         the type; run it in any repo after researching code.

  /sdd:ask                   One query across all registries (catalog/adr/spec/
                         investigation). Loads only the docs that match, grounds answers
                         in raw/, and follows wiki/ backlinks when that layer exists
                         (warns if it is stale). Optional type:/service: filters.
                         Examples:
                           /sdd:ask who consumes the LeadCreated SNS event?
                           /sdd:ask why did consumer-portal pick PostgreSQL?
                           /sdd:ask type:spec which specs have open questions?
                           /sdd:ask have we seen ReportToken reuse before?
                           /sdd:ask who consumes LeadCreated and why did we design it that way?

  /sdd:doc-ingest            Compile raw/ → wiki/ in a two-layer vault: extract entities +
                         concepts, write pages with [[backlinks]], update indexes + log.
                         The producer that keeps /sdd:ask sharp (no-op without a wiki/ layer).

─────────────────────────────────────────────────────────────────

CONTEXT SWITCHING

  /sdd:pause → /sdd:restore   Need to work on another branch? /sdd:pause stashes
                         everything and leaves branch switching to you.
                         /sdd:restore shows only pipeline branches, switches back
                         to the right branch, and restores the stash.

─────────────────────────────────────────────────────────────────

ARTIFACTS  (live in .specwork/, local-only/gitignored)

  _spec/<id>-spec.md        Feature spec (optionally published to docs/specs/ on /sdd:mr)
  _plan/<id>-plan.md        Implementation plan written by /sdd:plan (deleted by /sdd:close after merge)
  _progress/<id>-context.md Optional human-authored execution context (deleted by /sdd:close after merge)
  _progress/escalations.md  Append-only log of /sdd:implement escalations (deleted by /sdd:close after merge)
  _review/<id>-*.md         Code review reports (deleted by /sdd:close after merge)
```
