#!/usr/bin/env python3
"""Metric guard for the ``/sdd:mr`` repair loop.

When ``commands/check.sh`` fails before a push, ``/sdd:mr`` may try to repair
the code (at most 3 attempts; it asks first unless the pipeline runs
non-interactively). ``check.sh`` is the loop's metric, and a loop is only as
good as a metric it cannot edit: "fixing" a red build by deleting an assertion
or skipping a test raises the number without fixing the code.

So after every attempt this guard compares the working tree against the commit
the loop started from (``base``, the ``HEAD`` at the first failure) and rejects:

  - any change to ``commands/check.sh``;
  - a removed or modified line in a test file that already existed at ``base``
    (new lines are fine — adding a test or an assertion is a legitimate repair);
  - a deleted test file;
  - a skip/disable marker on an added line of any test file, new ones included
    (``@Disabled``, ``@pytest.mark.skip``, ``it.skip(``, ``xit(`` …).

No state is written: ``base`` is just a sha the skill keeps for the loop.

CLI:
  python3 repair.py guard <base-ref>   # exit 0 clean · 1 violations (printed) · 2 bad ref
"""
import re
import subprocess
import sys
from pathlib import Path

CHECK_SCRIPT = "commands/check.sh"

SKIP_MARKER = re.compile(
    r"@Disabled\b|@Ignore\b|@pytest\.mark\.(?:skip|xfail)\b|@unittest\.skip"
    r"|\bpytest\.skip\(|\bself\.skipTest\("
    r"|\b(?:it|test|describe|context)\.(?:skip|todo)\(|\bx(?:it|describe|test)\("
)


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

def parse_diff(diff_text):
    """Map path -> {"removed": [...], "added": [...], "deleted": bool} from ``git diff -U0`` output.

    Header lines are only read before a file's first ``@@`` hunk, so a removed
    line whose content starts with ``-- `` is not mistaken for a header.
    """
    files = {}
    current = None
    in_header = False
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            # "diff --git a/<path> b/<path>" — the b/ side names the file.
            path = line.split(" b/", 1)[1] if " b/" in line else None
            current = files.setdefault(path, {"removed": [], "added": [], "deleted": False}) if path else None
            in_header = True
            continue
        if current is None:
            continue
        if in_header:
            if line.startswith("@@"):
                in_header = False
            elif line.startswith("deleted file mode"):
                current["deleted"] = True
            continue
        if line.startswith("@@"):
            continue
        if line.startswith("-"):
            current["removed"].append(line[1:])
        elif line.startswith("+"):
            current["added"].append(line[1:])
    return files


def skip_markers(lines):
    """The lines that disable or skip a test."""
    return [line.strip() for line in lines if SKIP_MARKER.search(line)]


def violations(diff, untracked, base_files, is_test):
    """Violation messages for a repair attempt.

    ``diff``: :func:`parse_diff` output (``base`` → working tree).
    ``untracked``: ``{path: content}`` of untracked files.
    ``base_files``: set of paths that exist at ``base``.
    ``is_test``: predicate ``path -> bool``.
    """
    found = []
    if CHECK_SCRIPT in diff:
        found.append("{} was modified — the repair loop may not change its own metric".format(CHECK_SCRIPT))
    for path in sorted(diff):
        if not is_test(path):
            continue
        change = diff[path]
        if path in base_files:
            if change["deleted"]:
                found.append("{}: existing test file deleted".format(path))
                continue
            if change["removed"]:
                found.append("{}: {} existing line(s) removed or modified".format(path, len(change["removed"])))
        for marker in skip_markers(change["added"]):
            found.append("{}: skip marker added — {}".format(path, marker))
    for path in sorted(untracked):
        if is_test(path):
            for marker in skip_markers(untracked[path].splitlines()):
                found.append("{}: skip marker added — {}".format(path, marker))
    return found


# ---------------------------------------------------------------------------
# Thin git / fs wrappers (impure)
# ---------------------------------------------------------------------------

def _git(args):
    out = subprocess.run(["git"] + args, capture_output=True, check=True)
    return out.stdout.decode("utf-8", "replace")


def _detect_stack():
    try:
        from gates import detect_stack
        return detect_stack()
    except Exception:
        return "unknown"


def guard(base):
    """Violations of the working tree against ``base``. Raises ValueError on an unknown ref."""
    from conformance import is_test_file

    try:
        _git(["rev-parse", "--verify", "--quiet", base + "^{commit}"])
    except subprocess.CalledProcessError:
        raise ValueError("unknown ref {!r}".format(base))
    stack = _detect_stack()
    diff = parse_diff(_git(["diff", "-U0", "--no-renames", "--no-color", base]))
    base_files = set(_git(["ls-tree", "-r", "--name-only", base]).splitlines())
    untracked = {}
    for path in _git(["ls-files", "--others", "--exclude-standard"]).splitlines():
        if path.strip() and is_test_file(path, stack):
            try:
                untracked[path] = Path(path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    return violations(diff, untracked, base_files, lambda p: is_test_file(p, stack))


def _main(argv):
    if len(argv) != 3 or argv[1] != "guard":
        print("Usage: repair.py guard <base-ref>", file=sys.stderr)
        return 2
    try:
        found = guard(argv[2])
    except (ValueError, subprocess.CalledProcessError) as exc:
        print("✗ repair guard: {}".format(exc), file=sys.stderr)
        return 2
    if found:
        print("✗ Repair rejected — the change touches the metric:")
        for v in found:
            print("  - " + v)
        return 1
    print("✓ Repair guard: check.sh and existing tests untouched")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
