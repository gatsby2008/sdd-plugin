#!/usr/bin/env python3
"""High-risk auditor receipt for the SDD pipeline.

Reviewer agents cost tokens, so ``/sdd:commit`` runs ``/sdd:code-review``
automatically **only** when triage classified the pipeline as ``high-risk``,
and only once per distinct diff. After a review, the verdict is stamped
together with a fingerprint of the diff it covered (the "receipt"); re-running
``/sdd:commit`` on the same staged content finds a matching receipt and skips
the review. The verdict is advisory — nothing here blocks a commit.

Split of responsibility (mirrors ``validation.py``):
  - ``/sdd:commit`` asks ``required`` (cheap) and, after the review, calls ``record``.
  - this module never runs a reviewer itself.

CLI:
  python3 audit.py required <slug>            # exit 1 = run the auditor, 0 = skip
  python3 audit.py record   <slug> <verdict>  # verdict: PASS | PASS WITH WARNINGS | FAIL
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import paths

VERDICTS = ("PASS", "PASS WITH WARNINGS", "FAIL")


def receipt_file(slug, spec_dir=paths.DEFAULT_SPEC_DIR):
    return str(Path(spec_dir) / "_review" / "{}-audit.json".format(slug))


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def _git(args):
    out = subprocess.run(["git"] + args, capture_output=True, check=True)
    return out.stdout


def is_high_risk(slug, spec_dir=paths.DEFAULT_SPEC_DIR):
    data = _read_json(paths.path_file(slug, spec_dir))
    return isinstance(data, dict) and data.get("ticket_type") == "high-risk"


def diff_fingerprint(slug, spec_dir=paths.DEFAULT_SPEC_DIR):
    """SHA-256 of the staged branch diff: ``git diff --cached <merge-base>``."""
    state = _read_json(paths.state_file(slug, spec_dir)) or {}
    base = state.get("base_branch", "")
    ref = "HEAD"
    if base:
        try:
            ref = _git(["merge-base", base, "HEAD"]).decode().strip() or "HEAD"
        except Exception:
            ref = "HEAD"
    return hashlib.sha256(_git(["diff", "--cached", ref])).hexdigest()


def audit_required(slug, spec_dir=paths.DEFAULT_SPEC_DIR):
    """True only for a high-risk pipeline whose current diff has no receipt. Fails open."""
    try:
        if not is_high_risk(slug, spec_dir):
            return False
        receipt = _read_json(receipt_file(slug, spec_dir)) or {}
        return receipt.get("fingerprint") != diff_fingerprint(slug, spec_dir)
    except Exception:
        return False


def record(slug, verdict, spec_dir=paths.DEFAULT_SPEC_DIR):
    """Stamp the verdict for the current diff. Returns the fingerprint; raises ValueError on a bad verdict."""
    verdict = verdict.strip().upper()
    if verdict not in VERDICTS:
        raise ValueError("unknown verdict {!r}; expected one of {}".format(verdict, ", ".join(VERDICTS)))
    fingerprint = diff_fingerprint(slug, spec_dir)
    target = Path(receipt_file(slug, spec_dir))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({
        "fingerprint": fingerprint,
        "verdict": verdict,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }) + "\n", encoding="utf-8")
    return fingerprint


def _main(argv):
    if len(argv) == 2 and argv[0] == "required":
        if audit_required(argv[1]):
            print("AUDIT_REQUIRED reason=high-risk")
            return 1
        return 0
    if len(argv) >= 3 and argv[0] == "record":
        try:
            record(argv[1], " ".join(argv[2:]))
        except ValueError as exc:
            sys.stderr.write("✗ {}\n".format(exc))
            return 2
        except Exception as exc:
            sys.stderr.write("⚠ audit receipt not recorded: {}\n".format(exc))
            return 0
        print("✓ audit receipt recorded")
        return 0
    sys.stderr.write("Usage: audit.py required <slug> | audit.py record <slug> <verdict>\n")
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
