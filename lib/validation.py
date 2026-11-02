#!/usr/bin/env python3
"""Quality-gate validation marker for the SDD pipeline.

Records the commit sha that last passed ``commands/check.sh`` so the
PreToolUse(git push) hook can enforce the quality gate *cheaply*: instead of
re-running the multi-minute suite on every push (which would hit the hook
timeout and double the build ``/sdd:mr`` already ran), the hook just compares
``HEAD`` against the stamped sha.

Split of responsibility:
  - ``/sdd:mr`` *runs* ``check.sh`` (slow) and, on success, calls ``record`` here.
  - the push hook *enforces* by calling ``is_valid`` (cheap).

Standalone:
  python3 validation.py record [slug]   # stamp current HEAD as validated
  python3 validation.py check  [slug]    # exit 0 if HEAD is validated, else 1
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import gates
import paths
import repair


def head_sha():
    """Full sha of HEAD, or "" when not in a git repo / no commits yet."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except Exception:
        return ""


def current_branch():
    """Current branch name, or "" when not in a git repo / detached HEAD."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except Exception:
        return ""


def _resolve(slug):
    if slug:
        return slug
    try:
        return gates.resolve_slug() or ""
    except Exception:
        return ""


def record(slug=None, spec_dir=paths.DEFAULT_SPEC_DIR):
    """Stamp the current HEAD sha as having passed the quality gate.

    Returns the sha written, or "" when there is no HEAD or no slug to key on.
    """
    slug = _resolve(slug)
    sha = head_sha()
    if not slug or not sha:
        return ""
    target = Path(paths.validated_file(slug, spec_dir))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"sha": sha, "at": datetime.now(timezone.utc).isoformat()}) + "\n",
        encoding="utf-8",
    )
    return sha


def is_valid(slug=None, spec_dir=paths.DEFAULT_SPEC_DIR):
    """True when a marker exists and its sha matches the current HEAD."""
    slug = _resolve(slug)
    if not slug:
        return False
    marker = Path(paths.validated_file(slug, spec_dir))
    if not marker.is_file():
        return False
    try:
        stamped = json.loads(marker.read_text(encoding="utf-8")).get("sha", "")
    except Exception:
        return False
    head = head_sha()
    return bool(head) and stamped == head


def main(argv):
    if not argv:
        sys.stderr.write("usage: validation.py {record|check} [slug]\n")
        return 2
    cmd = argv[0]
    slug = argv[1] if len(argv) > 1 else None
    if cmd == "record":
        # An open repair loop (lib/repair.py) must close through `repair.py green`
        # — which re-runs its metric guard — before HEAD may be stamped. Without a
        # stamp the push-gate hook blocks the push.
        if repair.is_open():
            sys.stderr.write("✗ validation.py: a check.sh repair loop is open — run `repair.py green` "
                             "after a green check.sh (or `repair.py reset` to drop it). HEAD not stamped.\n")
            return 1
        sha = record(slug)
        if sha:
            sys.stdout.write("✓ quality gate validated for HEAD {}\n".format(sha[:8]))
            return 0
        sys.stderr.write("validation.py: no slug or HEAD to record — skipped\n")
        return 0  # never wedge the caller; absence of a marker just re-gates later
    if cmd == "check":
        return 0 if is_valid(slug) else 1
    sys.stderr.write("validation.py: unknown command {!r}\n".format(cmd))
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
