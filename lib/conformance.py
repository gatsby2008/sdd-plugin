#!/usr/bin/env python3
"""Spec-conformance check: flag spec Behaviors that no test claims to cover.

A deterministic, token-free stand-in for an LLM "implementation vs spec"
review. Each Behavior in the spec carries a stable id (``1. **B1** — …``);
``/sdd:implement`` tags every test it writes with the id(s) it covers
(``// spec: B1`` or ``spec: B1, B3`` in a display name). This module diffs the
branch, collects the tags from *added* test lines only, and reports the
Behavior ids nobody tagged.

Advisory by design: ``check`` always exits 0 and fails open. A spec with no
Behavior ids (older specs) is a silent no-op. Only added lines count, so tags
left in a test file by earlier features cannot satisfy this feature's ids.

CLI:
  python3 conformance.py check <slug>   # print uncovered Behavior ids (exit 0)
"""
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

SPECWORK = ".specwork"

_BEHAVIOR_ID = re.compile(r"\*\*B(\d+)\*\*")
_TAG = re.compile(r"spec:\s*(B\d+(?:\s*,\s*B\d+)*)", re.IGNORECASE)
_TAG_ID = re.compile(r"B(\d+)", re.IGNORECASE)

# Generic test-file patterns for stacks the coverage gate has no convention for.
_TEST_DIRS = ("tests", "test", "__tests__")


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

def behavior_ids(spec_text):
    """Ordered, de-duplicated Behavior ids (``B1``…) from the ``## Behavior`` section only."""
    ids = []
    in_section = False
    for line in spec_text.splitlines():
        if line.startswith("## "):
            in_section = line.strip() == "## Behavior"
            continue
        if in_section:
            for n in _BEHAVIOR_ID.findall(line):
                bid = "B" + n
                if bid not in ids:
                    ids.append(bid)
    return ids


def tags_in(lines):
    """Set of Behavior ids referenced by ``spec: B<n>`` tags in ``lines``."""
    found = set()
    for line in lines:
        for group in _TAG.findall(line):
            found.update("B" + n for n in _TAG_ID.findall(group))
    return found


def is_test_file(path, stack):
    """True for test files: the coverage-gate conventions plus generic patterns."""
    p = path.replace("\\", "/")
    try:
        from coverage import is_test_path
        if is_test_path(p, stack):
            return True
    except Exception:
        pass
    pure = PurePosixPath(p)
    name = pure.name
    stem = name.split(".")[0]
    if stem.startswith("test_") or stem.endswith("_test"):
        return True
    parts = name.split(".")
    if len(parts) >= 3 and parts[-2] in ("test", "spec"):
        return True
    return any(d in _TEST_DIRS for d in pure.parts[:-1])


def added_lines_by_file(diff_text):
    """Map file path -> list of added lines, from ``git diff`` unified output."""
    result = {}
    current = None
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip()
            current = target[2:] if target.startswith("b/") else None
            if current is not None:
                result.setdefault(current, [])
            continue
        if current is not None and line.startswith("+"):
            result[current].append(line[1:])
    return result


def uncovered(ids, covered):
    """Behavior ids (in spec order) with no covering tag."""
    return [i for i in ids if i not in covered]


# ---------------------------------------------------------------------------
# Thin git / fs wrappers (impure)
# ---------------------------------------------------------------------------

def _git(args):
    try:
        out = subprocess.check_output(["git"] + args, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
    return out.decode("utf-8", "replace")


def _base_branch(slug):
    state = Path("{}/_state/{}-state.json".format(SPECWORK, slug))
    try:
        return json.loads(state.read_text(encoding="utf-8")).get("base_branch", "")
    except (ValueError, OSError):
        return ""


def covered_ids(slug, stack):
    """Behavior ids tagged in test lines added on this branch (committed or not)."""
    base = _base_branch(slug)
    merge_base = _git(["merge-base", base, "HEAD"]).strip() if base else ""
    diff = _git(["diff", "-U0", merge_base or "HEAD"])
    lines = []
    for path, added in added_lines_by_file(diff).items():
        if is_test_file(path, stack):
            lines.extend(added)
    for path in _git(["ls-files", "--others", "--exclude-standard"]).splitlines():
        if path.strip() and is_test_file(path, stack):
            try:
                lines.extend(Path(path).read_text(encoding="utf-8", errors="replace").splitlines())
            except OSError:
                continue
    return tags_in(lines)


def _detect_stack():
    try:
        from gates import detect_stack
        return detect_stack()
    except Exception:
        return "unknown"


def check(slug):
    """Print uncovered Behavior ids. Never raises; always returns 0."""
    try:
        spec = Path("{}/_spec/{}-spec.md".format(SPECWORK, slug))
        if not spec.exists():
            return 0
        ids = behavior_ids(spec.read_text(encoding="utf-8"))
        if not ids:
            return 0
        missing = uncovered(ids, covered_ids(slug, _detect_stack()))
        if missing:
            print("⚠ Spec conformance: {} of {} Behavior(s) have no test tagged "
                  "`spec: B<n>`: {}".format(len(missing), len(ids), ", ".join(missing)))
        else:
            print("✓ Spec conformance: all {} Behavior(s) have a tagged test".format(len(ids)))
    except Exception:
        pass
    return 0


def _main(argv):
    if len(argv) >= 2 and argv[0] == "check":
        return check(argv[1])
    sys.stderr.write("Usage: conformance.py check <slug>\n")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
