# AGENTS.md

## Core Rules

- Never silently infer missing business behavior.
- Create Open Questions for ambiguous behavior.
- BLOCKING Open Questions stop progression.

## Scope

- Keep changes minimal and localized.
- Do not modify unrelated files.
- Avoid broad repository scans unless requested.
- Prefer existing patterns unless a significant issue exists.

## Critical Review

- Identify issues likely to:
    - break behavior
    - violate business rules
    - create data inconsistency
    - affect contracts
    - create cross-service regressions
    - introduce security or transaction risks

- Avoid optional refactors or redesigns.

## Findings Severity

- BLOCKING → stop progression
- IMPORTANT → warn only
- OPTIONAL → non-critical improvements

## Open Questions

Create only for:
- ambiguous behavior
- missing dependencies
- conflicting rules/contracts
- unsafe implementation conditions

Do not create for:
- optional refactors
- stylistic preferences
- speculative improvements

## State

- Service invariants: `.claude/service-rules.md`
- Feature state: `.specwork/`
- Prefer `.specwork/_state/*.json`

## Testing

- New classes require dedicated test classes **when they carry testable behavior**; logic-less types (DTOs, enums, plain records) do not need tests of their own.
- Prefer focused regression tests for changed logic.
- New endpoints require integration test coverage.
- Avoid full test suites unless requested.

## Quality Gates

- `bash commands/check.sh` must pass before committing (`/sdd:commit`) and again before pushing (`/sdd:mr`). The project provides this script (see `docs/setup.md` §5 "Project validation script" in the plugin); a template lives at `${CLAUDE_PLUGIN_ROOT}/templates/check.sh.example`.
- If the project is non-Gradle, the script should run the equivalent test command (`npm test`, `pytest`, `mvn verify`, etc.). The template auto-detects the common stacks.
- Failed quality checks block progression — do not commit or push on failure.