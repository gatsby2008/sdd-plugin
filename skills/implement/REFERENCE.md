# implement — Reference

Reference material for `/sdd:implement`. `SKILL.md` is the execution flow and holds every step, gate, and rule; this file holds what is only needed on demand — abort messages, rationale, examples, decision tables, and output templates. Each section names the step that points to it.

---

## Abort messages

Print the matching block verbatim (substituting `<slug>`) when a gate in `SKILL.md` aborts. Every abort writes nothing.

**Step 0 — no pipeline** (`gates.py precheck` non-zero):

```text
✗ Cannot implement.
No active pipeline (.specwork/ missing or uninitialized). Run /sdd:start first.
```

**Step 2 — missing spec:**

```text
✗ Cannot implement.

Missing spec:
.specwork/_spec/<slug>-spec.md

The spec has not been drafted yet. /sdd:start bootstraps state; /sdd:spec writes
the spec. Run /sdd:spec on this pipeline branch to draft it, then rerun /sdd:implement.
```

**Step 3 — unresolved Open Questions** (list only the files that block):

```text
✗ Cannot implement.

Unresolved Open Questions:
  - .specwork/_spec/<slug>-spec.md  (N items)
  - .specwork/_plan/<slug>-plan.md  (M items)

Resolve them in the respective file, then re-run /sdd:implement.
```

**Step 3.4 — plan required:**

```text
✗ Cannot implement.

Triage classified this work as high-risk — a reviewable plan is required before
implementation, and no plan exists yet:
  .specwork/_plan/<slug>-plan.md

Run /sdd:plan to produce it (it discovers target files and writes the approach),
then re-run /sdd:implement.

  /sdd:plan
  /sdd:implement

If the classification is wrong (e.g. the spec only says it does NOT publish an
event), force the tier with a reason instead:

  /sdd:spec --tier standard "<why this is not high-risk>"
```

**Step 3.5 — stale plan:**

```text
✗ Cannot implement.

The spec changed after the plan was built:
  .specwork/_spec/<slug>-spec.md
  .specwork/_plan/<slug>-plan.md

The plan no longer reflects the current spec — likely after a /sdd:spec refine
or a manual spec edit. The plan's Target Files, Approach, and Risk Assessment
may miss endpoints, classes, or constraints that the new spec introduced.

Re-run /sdd:plan to regenerate the plan (idempotent — overwrites in place),
then re-run /sdd:implement.

  /sdd:plan
  /sdd:implement

If you intentionally want to discard the existing plan and let /sdd:implement
discover targets from the spec directly, delete the plan file:
  rm .specwork/_plan/<slug>-plan.md
```

**Step 5 — ambiguity found while implementing** (after appending `- [ ] <question>` to the spec):

```text
Open Question added to spec.

.specwork/_spec/<slug>-spec.md
  - [ ] <question>

Answer it in the spec, then rerun /sdd:implement.
```

---

## Slug examples

Used in Step 1. The slug is the branch name without its type prefix, with its case preserved — `/sdd:start` passes it to `start.py` verbatim, so it is exactly the prefix of the files under `.specwork/_state/`:

```text
feature/IR-45        -> IR-45        (.specwork/_state/IR-45-state.json)
feature/ir-45-fix    -> ir-45-fix    (.specwork/_state/ir-45-fix-state.json)
hotfix/foo           -> foo          (.specwork/_state/foo-state.json)
```

If `<slug>-state.json` does not exist but a state file whose name differs **only in case** does (for example `ir-46-state.json` after `/sdd:resync`, which derives a lowercase slug), use that file's prefix as the slug. Never pick a state file whose name differs in anything other than case — that is another branch's pipeline; let Step 2 abort on the missing spec instead.

---

## Gate rationale

Background for Steps 3, 3.4 and 3.5. The operative rules are in `SKILL.md`.

**Open Questions (Step 3).** Spec Open Questions are business-behavior ambiguity, resolved in the spec. Plan Open Questions are discovery/implementation-path ambiguity surfaced by `/sdd:plan`, resolved in the plan. The canonical gate scans only the body of each file's `## Open Questions` section; checkboxes elsewhere are ignored. When no plan exists only the spec is checked (the no-plan workflow).

**Plan required (Step 3.4).** High-risk / architectural work is the one place the otherwise-optional plan step becomes mandatory — it is the tier where skipping discovery is most costly. Triage stamps `plan_required: true` into `.specwork/_state/<slug>-path.json` for that tier; trivial, focused, and standard keep the optional plan (the vibe-coding path). A tier forced with `/sdd:spec --tier` wins over the automatic one in both directions. With no `path.json` (a pipeline triaged before the field existed) the gate passes. Once `/sdd:plan` writes the plan, this gate passes and Step 3.5 takes over.

**Plan staleness (Step 3.5).** A plan built against an older spec describes Target Files, an Approach, and a Risk Assessment that no longer match the behavior — implementing against it silently skips whatever `/sdd:spec` (or a manual edit) added. The gate compares the spec **content fingerprint** stamped into the plan by `/sdd:plan`, so it stays correct after `git stash`/`checkout`/`rebase` and `/sdd:pause` → `/sdd:restore` (which reset mtimes). It fires on any real content change, whoever made it (`/sdd:spec`, a manual edit, `/sdd:resync`); a `touch` or whitespace-only save does not. Legacy plans with no fingerprint fall back to spec mtime > plan mtime (equal mtimes are fresh).

---

## Cache fields

Used in Step 2 (read) and Step 7 (write). `implementation-cache.json` is a fast index for this feature:

- `repositories`: already identified repositories
- `patterns`: validated local implementation patterns
- `related_tests`: tests likely to cover behavior
- `similar_classes`: classes with similar behavior to reuse
- `notes`: small implementation breadcrumbs

Example shape:

```json
{
  "schema_version": 1,
  "id": "<slug>",
  "repositories": ["LeadsRequestRepository"],
  "patterns": ["fallback lookup uses person + collateral identity"],
  "related_tests": ["DetailedLeadsProcessorIT"],
  "similar_classes": ["ExistingFallbackProcessor"],
  "notes": ["leadId fallback path is exercised in IT only"]
}
```

---

## Discovery guidance

Used in Step 4 on the discovery-fallback path (no plan).

Look in the spec and cache for: explicit files, classes, endpoints, repositories, DTOs, test classes, package hints.

Cache-first targeting:

- if `similar_classes` contains a likely match, inspect that file first
- if `related_tests` exists, start from those tests to locate production code
- if `repositories` exists, prioritize those repositories before searching new ones

Allowed targeted discovery:

```bash
find src -name "*KnownClassName*"
grep -r "knownMethodOrEndpoint" src/main src/test
```

Avoid broad commands like these unless the user explicitly approves:

```bash
find src -type f
grep -r "<generic term>" .
```

---

## Running individual tests

Used in Step 6. Run only the tests you created or modified, with the stack's command:

```bash
# Java
./gradlew test --tests "com.example.MyTest"

# Frontend
npm test -- MyComponent.test    # or pnpm/yarn equivalent
```

---

Used in Step 6 to classify a test or validation failure before attempting a fix:

| Failure type | Signals | Action |
| --- | --- | --- |
| Direct implementation error | assertion mismatch tied to changed behavior, wrong return value, missing field, wrong mapping, compile error in modified file | Attempt focused fix |
| Related test setup error | test fixture missing new required field, mock not updated for changed method signature, expected payload outdated because behavior intentionally changed | Attempt focused fix |
| Existing unrelated failure | failing test does not touch modified files or changed behavior | Escalate immediately |
| Spring context / infrastructure failure | `ApplicationContext` fails, bean wiring unclear, profile/config issue, datasource/Testcontainers issue, port/env problem | Escalate unless clearly caused by this change |
| Environmental/flaky failure | timeout, network, Docker/Testcontainers instability, random ordering, non-deterministic failure | Escalate immediately |
| Business ambiguity | expected behavior unclear, assertion could be valid under multiple interpretations | Stop and create/update Open Question |

---

## Retry and escalation detail

Used in Step 6.

**Failing area** — retries are tracked per area. An area is one of: the same unit test, the same integration test, the same compile failure, the same runtime exception, the same Spring context failure, the same infrastructure/configuration issue, the same test data / fixture setup issue. The count increments only when the same area persists after a fix attempt; unrelated new failures are reported separately, not counted.

**Escalation report** — when the budget is exhausted, STOP and report:

1. failing test or component
2. exact error excerpt
3. suspected root cause
4. files modified
5. fixes already attempted
6. recommended human review area

**While escalating, do not:** continue retrying indefinitely; rewrite unrelated infrastructure; perform broad exploratory refactors; modify unrelated production code attempting speculative fixes; change test expectations just to make tests pass; remove assertions unless the spec explicitly requires a behavior change.

**Human escalation is a valid and preferred outcome when:** integration tests repeatedly fail; infrastructure behavior is unclear; Spring context failures persist; the issue appears environmental; the fix requires historical or domain-specific knowledge; the failure cannot be tied directly to the current spec.

**Why `_progress/escalations.md`.** Escalations are runtime learning — what blocked execution, what was tried, what the human should look at next. They are not part of the contract (`_spec/`) or the deterministic state (`_state/`). `/sdd:handoff` reads the file and adds a *Known Blockers / Escalations* section to the execution capsule so an external executor doesn't repeat failed attempts. The on-screen summary is ephemeral; the file is the persistent record. `/sdd:close` wipes it with the rest of `.specwork/` once the feature merges.

---

## Escalation entry format

Used in Step 6 when persisting an escalation to `.specwork/_progress/escalations.md`. Append one block per escalation:

```markdown
## <YYYY-MM-DD> — <one-line summary, e.g. "Integration test escalation">

Failing area:
<test/component/subsystem>

Error excerpt:
<short excerpt — keep it tight, no full stack traces>

Suspected root cause:
<summary>

Files modified:
- <file>
- <file>

Fixes attempted:
- <attempt 1>
- <attempt 2>

Recommended human review:
<file/config/test setup>
```

---

## Simplicity checklist

Used in Step 7.5. Look for concrete, **spec-preserving** simplifications in the diff just written:

- **Fewer moving parts** — a new abstraction, layer, or indirection the spec did not ask for and a single call site does not justify.
- **Reuse over reinvention** — an existing helper, pattern, or class in the touched area that already does what the new code does.
- **Smaller surface** — a narrower signature, fewer new public methods, less config, a shorter diff that still satisfies the spec.
- **No speculative generality** — parameters, hooks, or branches added "just in case" with no current caller.

Simplification is about *form*, not *function*: a simplification that would change behavior is a spec concern, not an elegance note — do not reopen a resolved Open Question here.

---

## Risk classification table

Used in Step 8 to assign a final risk level. Risk is not determined by file count alone — one async change in a single class may be HIGH; dozens of DTO changes may still be LOW.

| Risk Signal | Description | Risk Level | Recommend test-design |
| --- | --- | --- | --- |
| DTO changes only | Simple request/response field changes without logic | LOW | No |
| Mapper adjustments | MapStruct/manual mapping updates without business logic | LOW | No |
| Validation message changes | Minor validation or error message updates | LOW | No |
| CRUD isolated change | Simple repository/service CRUD behavior | LOW | No |
| Existing tests already cover behavior | High confidence in current coverage | LOW | No |
| Single service method modification | Business logic changed in one bounded area | MEDIUM | Usually No |
| Multiple repositories affected | Change spans several persistence operations | MEDIUM | Maybe |
| Business rule modifications | Logic affecting calculations/decision paths | MEDIUM | Maybe |
| Controller + Service + Repository touched | Cross-layer impact detected | MEDIUM | Maybe |
| Existing tests require updates in multiple areas | Regression surface increasing | MEDIUM | Maybe |
| Async processing detected | CompletableFuture, ExecutorService, @Async, threads | HIGH | Yes |
| Event-driven flow modified | SNS/SQS/Kafka/event consumers/producers touched | HIGH | Yes |
| Retry logic changed | RetryTemplate, retry policies, backoff logic | HIGH | Yes |
| Transactional boundaries modified | @Transactional behavior or transaction flow changes | HIGH | Yes |
| Integration-test-sensitive flow | Multiple services/components interact | HIGH | Yes |
| Distributed side effects possible | External APIs/events/state propagation | HIGH | Yes |
| Concurrency-sensitive logic | Shared state, locks, synchronization, race conditions | HIGH | Yes |
| Critical business flow impacted | Consent, payments, lead creation, approvals, etc. | HIGH | Yes |
| Weak or missing test coverage detected | Low confidence in regression protection | HIGH | Yes |
| Unclear regression surface | Difficult to predict affected areas | HIGH | Yes |

## Recommendation logic

| Final Risk Level | Recommended Next Phase |
| --- | --- |
| LOW | `/sdd:commit` |
| MEDIUM | `/sdd:commit` (optionally `/sdd:test-design` first) |
| HIGH | `/sdd:test-design` |

The recommendation is advisory **to the developer** — they may skip any step — but the printed next phase must match the assigned risk level. Do not substitute a lower phase.

**HIGH does not downgrade because inline tests exist.** `/sdd:test-design` scans the tests already written during `/sdd:implement` and designs **only the missing cases** (real concurrency/race coverage, migration idempotency, untested edge cases) — it never duplicates them. Existing inline coverage is a reason to *run* test-design (to find its gaps), not to skip it.

When more implementation steps remain before the feature is complete, recommend `/sdd:implement` instead.

---

## Output templates

Used in Step 8 to print the final summary. Pick the block matching the assigned risk level (or the escalation block if Step 6 escalation triggered).

**Normal completion — HIGH risk:**

```text
Implementation completed.
Risk assessment: HIGH
- <observed signal, e.g. async/event-driven changes detected>
- <observed signal, e.g. transactional boundaries modified>
- <observed signal, e.g. weak test coverage detected>

Recommended next phase:
/sdd:test-design
```

**Normal completion — MEDIUM risk:**

```text
Implementation completed.
Risk assessment: MEDIUM
- <observed signal, e.g. multiple repositories affected>
- <observed signal, e.g. cross-layer change detected>

Recommended next phase:
/sdd:commit

Optional: run /sdd:test-design first if you want targeted test coverage before committing.
```

**Normal completion — LOW risk:**

```text
Implementation completed.
Risk assessment: LOW
<One sentence describing why scope is simple, e.g. "Change limited to DTO and mapper adjustments.">

Recommended next phase:
/sdd:commit
```

**Escalation triggered:**

```text
Escalation required.

Failing area:
  <test/component/subsystem>

Error excerpt:
  <short excerpt>

Suspected root cause:
  <summary>

Files modified:
  <files>

Fixes attempted:
  <list>

Recommended human review area:
  <file/config/test setup>

Review the reported failing area manually before continuing.
After fixing manually, rerun the focused test or continue with:
/sdd:implement
```

Do not hide failed tests behind a normal "done" message.

---

## Related skills

- `start` — creates rules/state artifacts and captures the source
- `spec` — drafts the spec + Open Questions, and refines it mid-pipeline; a spec change can trigger the Plan Staleness Gate; `--tier` corrects a wrong triage tier
- `plan` — when the staleness or plan-required gate fires, run `/sdd:plan` (idempotent)
- `commit` — stage and commit implementation changes
