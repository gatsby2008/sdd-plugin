# Lib

Shared bash libraries for SDD pipeline skills. Each skill sources these to access common functionality.

## jira.sh

Provides shared direct Jira REST helpers for SDD skills, primarily `/sdd:start`.

Typical usage:

```bash
source ${CLAUDE_PLUGIN_ROOT}/lib/jira.sh

if jira_is_configured; then
  jira_write_issue_markdown "PROJ-1234" ".specwork/_spec/proj-1234-source.md"
fi
```

Expected environment:
- `JIRA_BASE_URL` (or `JIRA_URL`)
- Jira Cloud: `JIRA_USER` + `JIRA_TOKEN`
- Jira Server/Data Center PAT: `JIRA_TOKEN` + `JIRA_AUTH_MODE=bearer`

## gates.py

Shared validation gates and utility functions for SDD pipeline skills. Callable standalone:

```bash
# Check for unresolved Open Questions in spec + plan
python3 ${CLAUDE_PLUGIN_ROOT}/lib/gates.py check-oqs <slug>

# Check if plan is stale (plan mtime < spec mtime)
python3 ${CLAUDE_PLUGIN_ROOT}/lib/gates.py check-staleness <slug>

# Check required artifacts exist
python3 ${CLAUDE_PLUGIN_ROOT}/lib/gates.py check-artifacts <slug>

# Detect risk signals from spec text
python3 ${CLAUDE_PLUGIN_ROOT}/lib/gates.py risk <slug>

# Check spec for internal contradictions
python3 ${CLAUDE_PLUGIN_ROOT}/lib/gates.py consistency <slug>

# Merge new facts into implementation-cache.json (append-only, dedupe)
python3 ${CLAUDE_PLUGIN_ROOT}/lib/gates.py merge-cache <slug> '{"key":["val"]}'

# Detect behavioral change signals from spec + plan
python3 ${CLAUDE_PLUGIN_ROOT}/lib/gates.py behavioral-signals <slug>

# Validate plan Target Files against current worktree
python3 ${CLAUDE_PLUGIN_ROOT}/lib/gates.py worktree-freshness <slug>
```

Replace inline Python heredocs (`python3 - <<'PY'`) across all SDD skills with these commands to reduce token consumption by keeping script logic outside the LLM context window.

## repair.py

State, attempt cap and metric guard for `/sdd:mr`'s Repair Loop. State lives in
`.git/sdd-repair-<branch>-<hash>.json` (one loop per branch, never committed); `validation.py record`
refuses to stamp HEAD while a loop is open, so the push hook blocks until it closes.
The guard rejects changes to `commands/check.sh` and test-runner configs, test
exclusions added to build files, removed/modified lines in existing tests, deleted
tests, and skip/disable/focus markers.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/repair.py red     # check.sh failed: open the loop / count it (rc 3 = exhausted)
python3 ${CLAUDE_PLUGIN_ROOT}/lib/repair.py pre     # before check.sh: guard + count → NONE | RUN_CHECK | SKIP_CHECK
python3 ${CLAUDE_PLUGIN_ROOT}/lib/repair.py green   # check.sh passed: 0 closed · 4 commit first · 1 violation
python3 ${CLAUDE_PLUGIN_ROOT}/lib/repair.py reset   # a human drops the loop
python3 ${CLAUDE_PLUGIN_ROOT}/lib/repair.py guard <base>   # guard only: 0 clean · 1 violations · 2 bad ref
```
