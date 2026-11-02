import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

LIB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, LIB_DIR)

import audit  # noqa: E402


def _git(cwd, *args):
    subprocess.check_call(["git"] + list(args), cwd=cwd,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class TestAudit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        _git(self.tmp, "init", "-q", "-b", "main")
        _git(self.tmp, "config", "user.email", "t@t")
        _git(self.tmp, "config", "user.name", "t")
        self._write("app.py", "x = 1\n")
        _git(self.tmp, "add", ".")
        _git(self.tmp, "commit", "-q", "-m", "base")
        _git(self.tmp, "checkout", "-q", "-b", "feature/x")
        os.makedirs(os.path.join(self.tmp, ".specwork", "_state"))
        self._write(".specwork/_state/x-state.json", json.dumps({"base_branch": "main"}))
        os.chdir(self.tmp)

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.tmp)

    def _write(self, rel, text):
        with open(os.path.join(self.tmp, rel), "w") as f:
            f.write(text)

    def _tier(self, ticket_type):
        self._write(".specwork/_state/x-path.json", json.dumps({"ticket_type": ticket_type}))

    def _stage(self, text):
        self._write("app.py", text)
        _git(self.tmp, "add", "app.py")

    def test_high_risk_without_receipt_requires_audit(self):  # spec: B1
        self._tier("high-risk")
        self._stage("x = 2\n")
        self.assertTrue(audit.audit_required("x"))

    def test_other_tiers_never_require_audit(self):  # spec: B1
        self._stage("x = 2\n")
        for tier in ("trivial", "focused", "standard"):
            self._tier(tier)
            self.assertFalse(audit.audit_required("x"), tier)

    def test_missing_or_corrupt_path_json_fails_open(self):  # spec: B1
        self.assertFalse(audit.audit_required("x"))
        self._write(".specwork/_state/x-path.json", "{not json")
        self.assertFalse(audit.audit_required("x"))

    def test_fingerprint_tracks_staged_content_only(self):  # spec: B2
        self._stage("x = 2\n")
        first = audit.diff_fingerprint("x")
        self._write("app.py", "x = 3\n")  # unstaged edit: not part of the commit
        self.assertEqual(audit.diff_fingerprint("x"), first)
        _git(self.tmp, "add", "app.py")
        self.assertNotEqual(audit.diff_fingerprint("x"), first)

    def test_fingerprint_covers_committed_branch_work(self):  # spec: B2
        self._stage("x = 2\n")
        staged = audit.diff_fingerprint("x")
        _git(self.tmp, "commit", "-q", "-m", "wip")
        # Same branch content, now committed: still the same diff vs merge-base.
        self.assertEqual(audit.diff_fingerprint("x"), staged)

    def test_record_writes_receipt(self):  # spec: B3
        self._stage("x = 2\n")
        fp = audit.record("x", "pass with warnings")
        with open(audit.receipt_file("x")) as f:
            data = json.load(f)
        self.assertEqual(data["fingerprint"], fp)
        self.assertEqual(data["verdict"], "PASS WITH WARNINGS")
        self.assertIn("recorded_at", data)

    def test_unknown_verdict_rejected_without_write(self):  # spec: B3
        with self.assertRaises(ValueError):
            audit.record("x", "MAYBE")
        self.assertFalse(os.path.exists(audit.receipt_file("x")))
        with redirect_stderr(StringIO()):
            self.assertEqual(audit._main(["record", "x", "MAYBE"]), 2)

    def test_matching_receipt_skips_second_review(self):  # spec: B6, B1
        self._tier("high-risk")
        self._stage("x = 2\n")
        audit.record("x", "FAIL")
        self.assertFalse(audit.audit_required("x"))
        self.assertEqual(audit._main(["required", "x"]), 0)
        self._stage("x = 9\n")  # diff changed → review again
        self.assertTrue(audit.audit_required("x"))
        self.assertEqual(audit._main(["required", "x"]), 1)

    # --- two-stage audit (spec conformance, then code review) ---

    def _spec(self, text):
        os.makedirs(os.path.join(self.tmp, ".specwork", "_spec"), exist_ok=True)
        self._write(".specwork/_spec/x-spec.md", text)

    def test_spec_review_input_lists_ids_and_ref(self):  # spec: B7
        self._spec("## Behavior\n\n1. **B1** — a\n2. **B2** — b\n")
        data = audit.spec_review_input("x")
        self.assertEqual(data["ids"], ["B1", "B2"])
        self.assertEqual(data["spec"], ".specwork/_spec/x-spec.md")
        merge_base = subprocess.check_output(["git", "merge-base", "main", "HEAD"]).decode().strip()
        self.assertEqual(data["ref"], merge_base)

    def test_spec_review_skipped_without_ids_or_spec(self):  # spec: B7
        self.assertEqual(audit.spec_review_input("x")["ids"], [])
        self._spec("## Behavior\n\n1. legacy\n")
        self.assertEqual(audit.spec_review_input("x"), {"spec": ".specwork/_spec/x-spec.md",
                                                       "ref": "", "ids": []})
        out = StringIO()
        with redirect_stdout(out):
            self.assertEqual(audit._main(["spec-review", "x"]), 0)
        self.assertEqual(json.loads(out.getvalue())["ids"], [])

    def test_record_with_spec_stage(self):  # spec: B8
        self._stage("x = 2\n")
        audit.record("x", "pass", spec_verdict="conforms")
        with open(audit.receipt_file("x")) as f:
            data = json.load(f)
        self.assertEqual(data["stages"], {"spec": "CONFORMS", "quality": "RUN"})

    def test_deviation_skips_quality_and_requires_fail(self):  # spec: B8
        self._stage("x = 2\n")
        with self.assertRaises(ValueError):
            audit.record("x", "PASS", spec_verdict="DEVIATES")
        self.assertFalse(os.path.exists(audit.receipt_file("x")))
        with redirect_stdout(StringIO()):
            self.assertEqual(audit._main(["record", "x", "FAIL", "--spec", "DEVIATES"]), 0)
        with open(audit.receipt_file("x")) as f:
            self.assertEqual(json.load(f)["stages"], {"spec": "DEVIATES", "quality": "SKIPPED"})

    def test_cli_record_parses_multiword_verdict_with_spec_flag(self):  # spec: B8
        self._stage("x = 2\n")
        with redirect_stdout(StringIO()):
            self.assertEqual(audit._main(
                ["record", "x", "PASS", "WITH", "WARNINGS", "--spec", "UNVERIFIED"]), 0)
        with open(audit.receipt_file("x")) as f:
            data = json.load(f)
        self.assertEqual((data["verdict"], data["stages"]["spec"]), ("PASS WITH WARNINGS", "UNVERIFIED"))

    def test_bad_spec_verdict_rejected(self):  # spec: B8
        with redirect_stderr(StringIO()):
            self.assertEqual(audit._main(["record", "x", "PASS", "--spec", "MAYBE"]), 2)
            self.assertEqual(audit._main(["record", "x", "PASS", "--spec"]), 2)
        self.assertFalse(os.path.exists(audit.receipt_file("x")))

    def test_receipt_without_spec_stage_is_unchanged(self):  # spec: B3
        self._stage("x = 2\n")
        audit.record("x", "PASS")
        with open(audit.receipt_file("x")) as f:
            self.assertNotIn("stages", json.load(f))


if __name__ == "__main__":
    unittest.main()
