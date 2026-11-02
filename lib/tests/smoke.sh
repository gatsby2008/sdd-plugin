#!/usr/bin/env bash
# Self-contained smoke test for the SDD pipeline in THIS repo (sdd-pipeline).
# Exercises the non-interactive cases: the unit suite, precheck against a real
# start state, and non-interactive flag resolution from state.json.
# Runs every scenario in an isolated scratch git repo. References nothing outside
# this repo.
set -uo pipefail

SDD="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"   # lib/tests -> lib -> sdd
export PYTHONPATH="$SDD"
PASS=0; FAIL=0
SCRATCH_ROOT="$(mktemp -d)"
trap 'rm -rf "$SCRATCH_ROOT"' EXIT

ok()  { printf '  \033[32mPASS\033[0m %s\n' "$1"; PASS=$((PASS+1)); }
bad() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; FAIL=$((FAIL+1)); }

assert_rc()  { local exp="$1" label="$2"; shift 3; local out rc
  out="$("$@" 2>&1 </dev/null)"; rc=$?
  if [ "$rc" -eq "$exp" ]; then ok "$label (rc=$rc)"; else bad "$label (rc=$rc, want $exp) :: ${out:0:120}"; fi; }
assert_out() { local sub="$1" label="$2"; shift 3; local out
  out="$("$@" 2>&1 </dev/null)"
  if printf '%s' "$out" | grep -qF "$sub"; then ok "$label"; else bad "$label (missing '$sub') :: ${out:0:160}"; fi; }
new_repo() { local d="$SCRATCH_ROOT/$1"; mkdir -p "$d"; ( cd "$d" && git init -q && git commit -q --allow-empty -m init && git checkout -q -b feature/demo ); echo "$d"; }

echo "== unit suite =="
( cd "$SDD" && python3 -m unittest discover -s lib/tests -p 'test_*.py' >/dev/null 2>&1 ) \
  && ok "unittest suite" || bad "unittest suite"

echo "== precheck =="
d=$(new_repo precheck-none); cd "$d"
assert_rc 1 "no .specwork rejects" -- python3 "$SDD/lib/gates.py" precheck
assert_out "Run /sdd:start first" "rejection message" -- python3 "$SDD/lib/gates.py" precheck
d=$(new_repo precheck-empty); cd "$d"; mkdir -p .specwork/_state
assert_rc 1 "empty .specwork rejects" -- python3 "$SDD/lib/gates.py" precheck

echo "== precheck against real start state =="
d=$(new_repo status); cd "$d"
python3 "$SDD/lib/start.py" --slug demo --ticket PROJ-1 --input-type jira --branch feature/demo --base-branch main >/dev/null 2>&1
assert_rc 0  "precheck initialized passes" -- python3 "$SDD/lib/gates.py" precheck
assert_rc 0  "precheck known slug passes" -- python3 "$SDD/lib/gates.py" precheck demo
assert_rc 1  "precheck unknown slug rejects" -- python3 "$SDD/lib/gates.py" precheck nope
assert_out "0" "non-interactive defaults to 0 when not set" -- python3 "$SDD/lib/gates.py" non-interactive demo

echo "== non-interactive from state.json =="
printf '{"id":"demo","ticket_type":"feature","input_type":"jira","non_interactive":true}' > .specwork/_state/demo-state.json
assert_out "1" "non-interactive reads from state.json" -- python3 "$SDD/lib/gates.py" non-interactive demo

echo "== repair loop (red → pre → green, push stamp gated) =="
d=$(new_repo repair); cd "$d"
mkdir -p commands tests
printf 'python3 -m unittest discover -s tests -t .\n' > commands/check.sh
printf 'def add(a, b):\n    return a - b\n' > calc.py
printf 'import unittest\nfrom calc import add\n\nclass T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n' > tests/test_calc.py
: > tests/__init__.py; printf '.specwork/\n__pycache__/\n' > .gitignore; export PYTHONDONTWRITEBYTECODE=1
git add -A && git commit -qm base
python3 "$SDD/lib/start.py" --slug demo --ticket PROJ-1 --input-type jira --branch feature/demo --base-branch main >/dev/null 2>&1
assert_rc 1 "check.sh is red" -- bash commands/check.sh
assert_out "REPAIR_BASE=" "red opens the loop and prints the base" -- python3 "$SDD/lib/repair.py" red
assert_rc 1 "validation stamp refused while the loop is open" -- python3 "$SDD/lib/validation.py" record demo
printf '[pytest]\naddopts = -k "not add"\n' > pytest.ini
assert_out "test-runner config" "pre rejects a pytest.ini deselect" -- python3 "$SDD/lib/repair.py" pre
rm pytest.ini
printf 'def add(a, b):\n    return a + b\n' > calc.py
assert_out "RUN_CHECK" "pre counts a clean attempt" -- python3 "$SDD/lib/repair.py" pre
assert_rc 0 "check.sh is green after the fix" -- bash commands/check.sh
assert_rc 4 "green asks to commit the repair first" -- python3 "$SDD/lib/repair.py" green
printf 'import unittest\nfrom calc import add\n\nclass Extra(unittest.TestCase):\n    def test_extra(self):\n        self.assertEqual(add(1, 1), 2)\n' > tests/test_extra.py
assert_out "Ran 2 tests" "the repair's new test file actually runs" -- bash commands/check.sh
assert_out "tests/test_extra.py" "green lists a new untracked test file to commit" -- python3 "$SDD/lib/repair.py" green
git add -A && git commit -qm "fix: repair"
assert_out "SKIP_CHECK" "re-run after commit skips the re-check" -- python3 "$SDD/lib/repair.py" pre
assert_rc 0 "green closes the loop" -- python3 "$SDD/lib/repair.py" green
assert_rc 0 "validation stamp allowed once closed" -- python3 "$SDD/lib/validation.py" record demo

echo "------------------------------------------------------------------"
printf " RESULT: %d passed, %d failed\n" "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
