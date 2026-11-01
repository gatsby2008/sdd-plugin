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
State:   .specwork/_state/feature-ir-45-state.json
Rules:   .specwork/_state/feature-ir-45-rules.json
Cache:   .specwork/_state/feature-ir-45-implementation-cache.json

Next:    /sdd:spec (draft the spec from the captured source)
```

**Started on another branch and keeps the current branch:**

```text
Branch:  bugfix/existing-work  (pipeline initialized on current branch)
Base:    bugfix/existing-work
Source:  free-text: "add validation to login form"
State:   .specwork/_state/bugfix-existing-work-state.json
Rules:   .specwork/_state/bugfix-existing-work-rules.json
Cache:   .specwork/_state/bugfix-existing-work-implementation-cache.json

Next:    /sdd:spec (draft the spec from the captured source)
```
