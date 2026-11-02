# doc-investigation — Reference

Reference material for `/sdd:doc-investigation`. `SKILL.md` is the execution flow and holds every step and rule; this file holds what a run reads only in one branch of the flow.

---

## Section mapping

**Step 1c** — read only the entry for the chosen type.

**bug** → Problem (one-line) · Symptoms (bullets) · Reproduction (how to trigger it;
`[TBD]` if not reproducible) · Investigation (what was checked + verbatim SQL/code) ·
Findings (facts) · Root Cause · Fix (fill the four fields: **Status**
applied/proposed/none-yet · **Where** `file` → symbol · **Change** the concrete edit ·
**Verify** how to confirm; mark any unknown field `[TBD]`) · Related Classes (bullets) ·
Future Signals (the "if you see X, check Y first" heuristic).

**exploration** → Question (what you set out to understand) · Context (why) · Map
(components/files/services and how they connect) · How It Works (the flow, step by step,
with verbatim traces) · Key Findings (the non-obvious) · Caveats & Gotchas · Open
Questions · Future Signals (where to start next time).

**improvements** → Goal (the requirement/standard and the bar for "done") · Current
State (the honest baseline) · Gap Analysis (one row per gap, each with an ADOPT /
PARTIAL / REJECT verdict + one-line rationale) · Plan (per ADOPT/PARTIAL item: the
concrete change, files/skills touched, effort; ordered cheapest/lowest-risk first —
written as a `- [ ]` **checklist** so a later agent sees what remains; a fresh capture
leaves every box unchecked and `status: proposed`) · Out of Scope (what is
*deliberately* rejected and why — as important as the Plan) · Open Decisions (calls a
human must make first) · Future Signals (where to pick it up).

---

## List mode

**`/sdd:doc-investigation list`** — after detecting the service:

1. Detect the target service exactly as Step 2 does (`spring.application.name` →
   git repo basename → `unscoped`), lowercased.
2. List that service's investigations, newest first:

```bash
SERVICE="<detected-service>"
REGISTRY="${CLAUDE_DOC_HOME:-$HOME/.claude}/investigation-registry"
DIR="$REGISTRY/$SERVICE"

if [ ! -d "$DIR" ] || ! ls "$DIR"/*.md >/dev/null 2>&1; then
  echo "No investigations registered for $SERVICE."
  echo "Run /sdd:doc-investigation after researching code to capture one."
  exit 0
fi

echo "Investigations for $SERVICE in $DIR:"
ls -1t "$DIR"/*.md 2>/dev/null | while read -r f; do
  title="$(grep -m1 '^title:' "$f" | sed 's/^title:[[:space:]]*//')"
  type="$(grep -m1 '^type:' "$f" | sed 's/^type:[[:space:]]*//')"
  printf "  %-40s  [%s]  %s\n" "$(basename "$f")" "${type:-?}" "$title"
done
```

The date prefix in each filename sorts naturally; `-1t` also surfaces the most recent
first. After listing, exit — do not proceed to capture. To search **across** services
or by content, use `/sdd:ask`.
