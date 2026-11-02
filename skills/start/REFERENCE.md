# start — Reference

Reference material for `/sdd:start`. Schemas, templates, and example output. `SKILL.md` is the execution flow; this file holds the artifact structures.

---

## State file schema

`.specwork/_state/<slug>-state.json`:

```json
{
  "schema_version": 1,
  "id": "<slug>",
  "ticket": "<TICKET or null>",
  "input_type": "jira|freetext",
  "non_interactive": false,
  "branch": "<branch_name_or_current_branch>",
  "base_branch": "<branch_started_from>",
  "source_title": "<title>",
  "source_body_file": ".specwork/_spec/<slug>-source.md",
  "spec_file": ".specwork/_spec/<slug>-spec.md",
  "context_file": ".specwork/_progress/<slug>-context.md",
  "rules_file": ".specwork/_state/<slug>-rules.json",
  "path_file": ".specwork/_state/<slug>-path.json",
  "implementation_cache_file": ".specwork/_state/<slug>-implementation-cache.json"
}

Fields:
- `path_file`: Points to the advisory pipeline path (written by triage classification in `/sdd:spec` draft mode — see `skills/spec/SKILL.md` § Step 9).

`implementation_cache_file` points to the feature-local implementation memory artifact.

---

## Implementation cache file schema

`.specwork/_state/<slug>-implementation-cache.json`:

```json
{
  "schema_version": 1,
  "id": "<slug>",
  "repositories": [],
  "patterns": [],
  "related_tests": [],
  "similar_classes": [],
  "notes": []
}
```

This file is append/update only during the feature lifecycle and is consumed by `/sdd:implement` to reduce rediscovery and repeated scans.

---

## Rules file schema

`.specwork/_state/<slug>-rules.json` is generated only by `/sdd:start`.

```json
{
  "schema_version": 1,
  "id": "<slug>",
  "source_files": ["${CLAUDE_PLUGIN_ROOT}/AGENTS.md", ".claude/service-rules.md"],
  "global_rules": [
    "Never silently infer missing business rules.",
    "Open Questions block implementation."
  ],
  "service_rules": [
    "<invariant extracted from service-rules.md>"
  ]
}
```

Downstream skills should read `rules.json` instead of re-reading markdown rules files.

---

## Spec template

`/sdd:start` does **not** write the spec. The canonical spec structure lives in
`${CLAUDE_PLUGIN_ROOT}/templates/spec.md`, and `/sdd:spec` draft mode writes
`.specwork/_spec/<slug>-spec.md` from it (sections: Summary, Scope, Behavior,
Implementation Context, **Expected Change Scope**, **Safe Constraints**, Open
Questions). The spec-writing rules and triage live in the `spec` SKILL.md.

`/sdd:handoff` reads `## Expected Change Scope` and `## Safe Constraints` verbatim
from the spec `/sdd:spec` produces.

---

## Output examples

Three canonical post-`/sdd:start` outputs. `/sdd:start` writes state/rules/cache and
captures the source — it does not draft the spec or run triage (that is `/sdd:spec`),
so the next step is always `/sdd:spec`.

**Started on `development` and creates a new branch:**

```text
Branch:  feature/PROJ-1234  (created from development)
Source:  JIRA: PROJ-1234
State:   .specwork/_state/proj-1234-state.json
Rules:   .specwork/_state/proj-1234-rules.json
Cache:   .specwork/_state/proj-1234-implementation-cache.json

Next:    /sdd:spec (draft the spec from the captured source)
```

**Started on another branch and creates a dependent branch from it:**

```text
Branch:  feature/IR-45  (created from feature/IR-40)
Base:    feature/IR-40
Source:  JIRA: IR-45
State:   .specwork/_state/ir-45-state.json
Rules:   .specwork/_state/ir-45-rules.json
Cache:   .specwork/_state/ir-45-implementation-cache.json

Next:    /sdd:spec (draft the spec from the captured source)
```

**Started on another branch and keeps the current branch:**

```text
Branch:  bugfix/existing-work  (pipeline initialized on current branch)
Base:    bugfix/existing-work
Source:  free-text: "add validation to login form"
State:   .specwork/_state/existing-work-state.json
Rules:   .specwork/_state/existing-work-rules.json
Cache:   .specwork/_state/existing-work-implementation-cache.json

Next:    /sdd:spec (draft the spec from the captured source)
```

---

## Existing-pipeline messages

**Step 0** — print the block for the case that applies, substituting the placeholders.

### Case A — this branch owns an active pipeline

```text
✗ There is an active pipeline for <ACTIVE_SLUG> (branch <CURRENT_BRANCH>).
  /sdd:start will not start new work on top of it.

  • Continue it:  run /sdd:spec (draft/refine) or /sdd:state (next step)
  • Park it:      run /sdd:pause to stash <ACTIVE_SLUG> and resume later
  • Close it:     run /sdd:close (then /sdd:start for the new work)
```

### Case B — orphan leftovers whose work already landed

```text
✗ /sdd:start did not start anything — .specwork/ still holds a finished pipeline.

    • <slug> (branch <branch>) — already merged into <base_branch>
    • <slug> (branch <branch>) — branch no longer exists locally

  That work already landed. Clear the leftovers, then start again:

    /sdd:close                 # re-checks MR state, then wipes .specwork/
    /sdd:start <your input>
```

### Case C — orphan leftovers still in flight

```text
✗ .specwork/ belongs to '<branch>' (slug '<slug>'), not '<CURRENT_BRANCH>'.
  /sdd:start will not start new work on top of another branch's pipeline.

  • Resume it:  switch to '<branch>' and run /sdd:state
  • Park it:    switch to '<branch>' and run /sdd:pause, then come back here
  • Renamed?    run /sdd:resync if '<branch>' is this branch under an old name
```

Case B, extra line for each `branch-gone` entry:

```text
  If <branch> was renamed rather than merged, run /sdd:resync instead of /sdd:close.
```

---

## Jira fetch

**Jira Access Without MCP** — the fetch, with the supplementary note appended:

```bash
source ${CLAUDE_PLUGIN_ROOT}/lib/jira.sh

if jira_is_ticket_key "$TICKET" && jira_is_configured; then
  jira_write_issue_markdown "$TICKET" ".specwork/_spec/<slug>-source.md"
  # Preserve any supplementary free text typed alongside the ticket
  # (e.g. /sdd:start PROJ-123 "watch out: only the publisher, not the consumer").
  # That note is usually the highest-value, least-recoverable context — never drop it.
  if [ -n "$DESC" ]; then
    printf '\n## Additional context (from /sdd:start)\n\n%s\n' "$DESC" \
      >> ".specwork/_spec/<slug>-source.md"
  fi
fi
```

Jira not configured — print and stop:

```
✗ Jira is not configured. Set the following environment variables and retry:

  export JIRA_BASE_URL=https://<your-domain>.atlassian.net
  export JIRA_USER=your@email.com
  export JIRA_TOKEN=<personal-access-token>

Run /sdd:start again once Jira is configured.
```

---

## Related Skills

- `spec` — drafts the spec from the source captured here; run it next
- `plan` — optional discovery + plan step (recommended for medium/large features)
- `implement` — consumes the spec + rules (and the plan if it exists)
- `close` — clears `.specwork/` artifacts including `_state/`
