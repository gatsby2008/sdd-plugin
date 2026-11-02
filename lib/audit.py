#!/usr/bin/env python3
"""High-risk auditor receipt for the SDD pipeline.

Reviewer agents cost tokens, so ``/sdd:commit`` runs ``/sdd:code-review``
automatically **only** when triage classified the pipeline as ``high-risk``,
and only once per distinct diff. After a review, the verdict is stamped
together with a fingerprint of the diff it covered (the "receipt"); re-running
``/sdd:commit`` on the same staged content finds a matching receipt and skips
the review. The verdict is advisory — nothing here blocks a commit.

The audit has two stages. Stage 1 (spec conformance) reads the spec against the
diff, Behavior by Behavior; it runs only when the spec has Behavior ids. Stage 2
is ``/sdd:code-review`` (quality + security), skipped when stage 1 finds the diff
deviates from the spec — reviewing the quality of a diff that does not do what
the spec says is wasted tokens. Both results land in one receipt.

Split of responsibility (mirrors ``validation.py``):
  - ``/sdd:commit`` asks ``required`` (cheap) and, after the review, calls ``record``.
  - this module never runs a reviewer itself.

CLI:
  python3 audit.py required <slug>            # exit 1 = run the auditor, 0 = skip
  python3 audit.py spec-review <slug>         # JSON for stage 1: {"spec", "ref", "ids"}; ids [] = skip it
  python3 audit.py record   <slug> <verdict> [--spec <spec-verdict>]
      verdict: PASS | PASS WITH WARNINGS | FAIL
      spec-verdict: CONFORMS | UNVERIFIED | DEVIATES | SKIPPED (DEVIATES requires FAIL)
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import paths

VERDICTS = ("PASS", "PASS WITH WARNINGS", "FAIL")
SPEC_VERDICTS = ("CONFORMS", "UNVERIFIED", "DEVIATES", "SKIPPED")


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


def diff_ref(slug, spec_dir=paths.DEFAULT_SPEC_DIR):
    """The ref the audited diff starts from: merge-base with ``base_branch``, else HEAD."""
    state = _read_json(paths.state_file(slug, spec_dir)) or {}
    base = state.get("base_branch", "")
    if base:
        try:
            return _git(["merge-base", base, "HEAD"]).decode().strip() or "HEAD"
        except Exception:
            pass
    return "HEAD"


def diff_fingerprint(slug, spec_dir=paths.DEFAULT_SPEC_DIR):
    """SHA-256 of the staged branch diff: ``git diff --cached <merge-base>``."""
    return hashlib.sha256(_git(["diff", "--cached", diff_ref(slug, spec_dir)])).hexdigest()


def spec_review_input(slug, spec_dir=paths.DEFAULT_SPEC_DIR):
    """What stage 1 needs: spec path, diff ref and Behavior ids. ``ids == []`` → skip stage 1."""
    spec = paths.spec_file(slug, spec_dir)
    ids = []
    try:
        from conformance import behavior_ids
        ids = behavior_ids(Path(spec).read_text(encoding="utf-8"))
    except Exception:
        ids = []
    return {"spec": spec, "ref": diff_ref(slug, spec_dir) if ids else "", "ids": ids}


def audit_required(slug, spec_dir=paths.DEFAULT_SPEC_DIR):
    """True only for a high-risk pipeline whose current diff has no receipt. Fails open."""
    try:
        if not is_high_risk(slug, spec_dir):
            return False
        receipt = _read_json(receipt_file(slug, spec_dir)) or {}
        return receipt.get("fingerprint") != diff_fingerprint(slug, spec_dir)
    except Exception:
        return False


def record(slug, verdict, spec_dir=paths.DEFAULT_SPEC_DIR, spec_verdict=None):
    """Stamp the verdict for the current diff. Returns the fingerprint; raises ValueError on a bad verdict.

    ``spec_verdict`` (stage 1) adds a ``stages`` block to the receipt. ``DEVIATES``
    means stage 2 was skipped, so the overall verdict must be ``FAIL``.
    """
    verdict = verdict.strip().upper()
    if verdict not in VERDICTS:
        raise ValueError("unknown verdict {!r}; expected one of {}".format(verdict, ", ".join(VERDICTS)))
    receipt = {"fingerprint": None, "verdict": verdict}
    if spec_verdict is not None:
        spec_verdict = spec_verdict.strip().upper()
        if spec_verdict not in SPEC_VERDICTS:
            raise ValueError("unknown spec verdict {!r}; expected one of {}".format(
                spec_verdict, ", ".join(SPEC_VERDICTS)))
        if spec_verdict == "DEVIATES" and verdict != "FAIL":
            raise ValueError("spec verdict DEVIATES skips the code review; the verdict must be FAIL")
        receipt["stages"] = {
            "spec": spec_verdict,
            "quality": "SKIPPED" if spec_verdict == "DEVIATES" else "RUN",
        }
    fingerprint = diff_fingerprint(slug, spec_dir)
    receipt["fingerprint"] = fingerprint
    receipt["recorded_at"] = datetime.now(timezone.utc).isoformat()
    target = Path(receipt_file(slug, spec_dir))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
    return fingerprint


def _main(argv):
    if len(argv) == 2 and argv[0] == "required":
        if audit_required(argv[1]):
            print("AUDIT_REQUIRED reason=high-risk")
            return 1
        return 0
    if len(argv) == 2 and argv[0] == "spec-review":
        try:
            print(json.dumps(spec_review_input(argv[1])))
        except Exception:
            print(json.dumps({"spec": "", "ref": "", "ids": []}))  # fail open: skip stage 1
        return 0
    if len(argv) >= 3 and argv[0] == "record":
        rest = list(argv[2:])
        spec_verdict = None
        if "--spec" in rest:
            i = rest.index("--spec")
            if i + 1 >= len(rest):
                sys.stderr.write("✗ --spec needs a value\n")
                return 2
            spec_verdict = rest[i + 1]
            del rest[i:i + 2]
        try:
            record(argv[1], " ".join(rest), spec_verdict=spec_verdict)
        except ValueError as exc:
            sys.stderr.write("✗ {}\n".format(exc))
            return 2
        except Exception as exc:
            sys.stderr.write("⚠ audit receipt not recorded: {}\n".format(exc))
            return 0
        print("✓ audit receipt recorded")
        return 0
    sys.stderr.write("Usage: audit.py required <slug> | audit.py spec-review <slug> | "
                     "audit.py record <slug> <verdict> [--spec <spec-verdict>]\n")
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
