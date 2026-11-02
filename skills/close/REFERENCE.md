# close — Reference

Reference material for `/sdd:close`. `SKILL.md` is the execution flow and holds every step, gate, and rule; this file holds procedures a run needs only in some branches of the flow. Each section names the step that points to it.

---

## Promote durable rules

**Step 6.5** — interactive only, MR not `closed`, spec present.

1. **Read only the spec** — `## Safe Constraints` and the resolved (`- [x]`) items in
   `## Open Questions`. Do not re-read the diff or the code; this step must stay cheap.
2. **Pick candidates.** Keep only feature-agnostic, durable invariants: business rules,
   ownership/identity rules, idempotency or fallback contracts, the *why* behind a design
   choice. Drop ticket-only decisions, dates, rollout notes, and anything already stated
   in the rules files (the template's "Out of Scope (Do Not Add Here)" list applies).
   At most **4** candidates; zero is a normal outcome — then print
   `No durable rules to promote.` and go to Step 7.
3. **Choose a target per candidate.** If `.claude/rules/*.md` exist, pick the topic file
   whose subject matches, and a section heading inside it. Otherwise target
   `.claude/service-rules.md` and one of its sections (`Business Invariants`,
   `Fallback and Idempotency`, `Architecture Constraints`, `Historical Constraints`).
4. **Check for conflicts.** If a candidate contradicts an existing rule, do **not**
   propose it as a write — list it separately as a question for the user
   (`⚠ Conflicts with "<existing rule>" in <file> — which one holds?`). Existing rules
   are never edited, reworded, or removed by this step.
5. **Ask once**, with a single multi-select `AskUserQuestion`: one option per candidate,
   label = the rule, description = `<target file> § <section>`. Nothing is selected by
   default.
6. **Write only the approved ones**, one call per target file:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/lib/promote.py apply "<rules-file>" "$SLUG" \
     '[{"section": "Business Invariants", "rule": "<approved rule text>"}]'
   ```

   `promote.py` inserts each rule as a new bullet at the end of its section (creating the
   section, or the file, if missing) with a provenance marker —
   `- <rule> _(from spec <slug>, <YYYY-MM-DD>)_` — and **refuses to write** (exit 1) if any
   pre-existing line would change. Hand-written rules and rationale are preserved
   byte-for-byte; that guarantee is enforced in code, not left to this prose. On exit 1,
   report it and continue to Step 7 without retrying.

---

## checkout_parent

**Step 8** — choices **d** and **k**.

To switch to the parent safely — checking it out from `origin` when it only exists remotely:

```bash
checkout_parent() {
  if git rev-parse --verify --quiet "refs/heads/$PARENT" >/dev/null; then
    git checkout "$PARENT"
  elif git rev-parse --verify --quiet "refs/remotes/origin/$PARENT" >/dev/null; then
    git checkout -b "$PARENT" "origin/$PARENT"
  else
    echo "Parent branch '$PARENT' not found locally or on origin." >&2
    return 1
  fi
}
```
