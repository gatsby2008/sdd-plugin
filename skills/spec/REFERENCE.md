# spec — Reference

Reference material for `/sdd:spec`. `SKILL.md` is the execution flow and holds every step, gate, and rule; this file holds what is only needed on demand — messages, the Jira fetch, the `--tier` detail, and output templates. Each section names the step that points to it.

---

## No-op message

**Step 2.5** — refine mode with zero arguments. Print verbatim, write nothing:

```text
Spec is already drafted (.specwork/_spec/<slug>-spec.md).
No arguments passed — nothing to refine, nothing changed.

To refine, pass additional context:
  /sdd:spec <file> [<file> ...]        — add file context
  /sdd:spec jira <TICKET>              — add Jira ticket context
  /sdd:spec "free text"                — add free text
  /sdd:spec <file> jira <TICKET> "..." — combine sources

Next:
  /sdd:plan        (discover target files)
  /sdd:implement   (start implementing — inline discovery if no plan)
```

---

## Fetching Jira

**Step 5** — for each `jira <TICKET>` input:

```bash
source ${CLAUDE_PLUGIN_ROOT}/lib/jira.sh

if jira_is_ticket_key "$TICKET" && jira_is_configured; then
  jira_write_issue_markdown "$TICKET" "/tmp/spec-${TICKET}.md"
  cat "/tmp/spec-${TICKET}.md"
else
  echo "Jira not configured or invalid ticket key: $TICKET"
  echo "Set JIRA_BASE_URL + JIRA_USER + JIRA_TOKEN, or paste the ticket body instead."
fi
```

---

## Forcing the tier (`--tier`)

**Step 9** — when the arguments include `--tier`.

Triage is a keyword classifier and can misfire — a Behavior that says "does
**not** publish to Kafka" still matches the async/eventing signal and lands in
`high-risk`, which makes the plan mandatory. To correct it explicitly:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/triage.py <slug> --tier <trivial|focused|standard|high-risk> --reason "<reason>"
python3 ${CLAUDE_PLUGIN_ROOT}/lib/triage.py <slug> --tier auto      # drop the override
```

- **The reason is mandatory.** If the user gave `--tier` without one, ask for it
  (interactive) or stop and report it (non-interactive) — never invent one.
  `triage.py` exits 2 and writes nothing when the reason is missing.
- The forced tier drives everything downstream: `path`, `plan_required` (so the
  `/sdd:implement` plan-required gate follows it, both ways), and the
  `/sdd:commit` high-risk auditor. The automatic tier and its reason stay in
  `path.json` under `override` (`tier`, `reason`, `auto_tier`, `auto_why`).
- The override is sticky: a later triage run without `--tier` (e.g. after a
  re-draft) re-applies it. `--tier auto` returns to the automatic tier.
- Print the triage summary; it includes an `Override:` line with the automatic
  tier so the decision stays visible.

---

## Output templates

**Step 11**.

### Clickable paths

Whenever output references the spec or its Open Questions, use the canonical
format documented across `/sdd:whatnext`, `/sdd:plan`, `/sdd:start`, `/sdd:state`: an
**absolute path with the line number of the `## Open Questions` heading**,
wrapped in single backticks so Claude Code renders it as a clickable token.

```bash
SPEC=".specwork/_spec/${SLUG}-spec.md"
ABS_SPEC="$(cd "$(dirname "$SPEC")" && pwd)/$(basename "$SPEC")"
OQ_LINE="$(grep -n "^## Open Questions" "$SPEC" | head -1 | cut -d: -f1)"
# Use `${ABS_SPEC}:${OQ_LINE}` (wrapped in backticks) wherever output references OQs.
```

Do **not** wrap the whole output block in a fenced code block — fenced blocks
suppress inline-code coloring on the path. Emit it as plain markdown text.

### Draft mode output

```text
Spec drafted: `/abs/path/repo/.specwork/_spec/<slug>-spec.md:42`  ← Open Questions

Triage:  standard (MEDIUM)
Path:    /sdd:plan → /sdd:implement → /sdd:commit → /sdd:mr
Why:     3 layers (controller, service, repository), no high-risk signals.

Open Questions: 3 open
  Resolve them in `/abs/path/repo/.specwork/_spec/<slug>-spec.md:42` before /sdd:plan
  (re-run /sdd:spec with the answers as context).

Next:
  /sdd:plan        (recommended for 3+ files)
  /sdd:implement   (small / obvious changes — inline discovery)
```

When the draft has zero Open Questions, drop the OQ lines and shorten `Next:`.

### Refine mode output

Emit only sections that actually changed; omit empty ones.

```text
Spec refined: `/abs/path/repo/.specwork/_spec/<slug>-spec.md:42`  ← Open Questions

Open Questions:    5 → 3
  ✓ Resolved #1 — Use UUID for personId        (from: OrderController.java)
  ✓ Resolved #3 — Notifications are fire-and-forget, no retry   (from: paste)
  ⚠ Still open:  #2, #4, #5
      `/abs/path/repo/.specwork/_spec/<slug>-spec.md:42`  ← Open Questions

Implementation Context:
  + OrderController.createOrder()        (from: OrderController.java)
  + PaymentClient (Feign)                (from: paste)

Safe Constraints:
  + Unsafe: Logging unmasked PII fields  (from: jira IR-122)

Downstream artifacts (now potentially stale):
  ⚠ .specwork/_plan/<slug>-plan.md is older than the spec
    Run /sdd:plan to regenerate (it is idempotent — overwrites in place).
  ⚠ Working tree has uncommitted changes
    Review them against the new spec before committing.

Next:
  Resolve Open Questions in `/abs/path/repo/.specwork/_spec/<slug>-spec.md:42` (3 open).
  Then /sdd:plan (recommended — plan is stale).
  Or /sdd:implement if no plan exists / plan is still valid.
```

When **all** OQs are resolved, drop the OQ-related lines and shorten `Next:` to
the pipeline-step commands.

If refine produced no change, print:

```text
No changes to the spec.

The input did not produce any updates — either the spec was already up to date,
or the input didn't match any actionable category. The file mtime was not
modified.
```

---

## When to use


- **Right after `/sdd:start`** — draft the spec from the captured source.
- **Resolve Open Questions** once you have the answer (a file, a Jira ticket, a
  paste, or free text).
- **Add scope** you forgot at `/sdd:start` — a specific endpoint, class, service.
- **Record constraints** that surfaced later (a PII rule, retry policy, SLA).

When **not** to use:
- The pipeline hasn't started — `.specwork/` is missing. Run `/sdd:start` first.
- You need to change the branch, ticket, or rules — those belong to
  `/sdd:start` / `/sdd:resync`.

---

## Related Skills

- `start` — captures the source and state that `/sdd:spec` turns into the spec;
  it does **not** create spec.md.
- `plan` — idempotent re-run absorbs spec updates; the staleness warning here
  recommends running it.
- `implement` — blocks on unresolved Open Questions; refining the spec to
  close OQs unblocks it.
- `handoff` — reads the latest spec; running `/sdd:spec` before `/sdd:handoff`
  ensures the execution pack is current.
- the old `spec-refine` alias has been removed — use `/sdd:spec` (refine mode) instead.
