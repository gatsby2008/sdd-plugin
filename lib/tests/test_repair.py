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

import repair  # noqa: E402


def _git(cwd, *args):
    subprocess.check_call(["git"] + list(args), cwd=cwd,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _is_test(path):
    return path.startswith("tests/")


class TestParseDiff(unittest.TestCase):
    def test_removed_and_added_lines(self):
        diff = (
            "diff --git a/tests/test_a.py b/tests/test_a.py\n"
            "index 1..2 100644\n"
            "--- a/tests/test_a.py\n"
            "+++ b/tests/test_a.py\n"
            "@@ -3 +3 @@\n"
            "-    assert x == 1\n"
            "+    assert x == 2\n"
        )
        parsed = repair.parse_diff(diff)
        self.assertEqual(parsed["tests/test_a.py"]["removed"], ["    assert x == 1"])
        self.assertEqual(parsed["tests/test_a.py"]["added"], ["    assert x == 2"])
        self.assertFalse(parsed["tests/test_a.py"]["deleted"])

    def test_removed_line_starting_with_dashes_is_not_a_header(self):
        diff = (
            "diff --git a/q.sql b/q.sql\n"
            "--- a/q.sql\n"
            "+++ b/q.sql\n"
            "@@ -1 +0,0 @@\n"
            "--- a sql comment\n"
        )
        self.assertEqual(repair.parse_diff(diff)["q.sql"]["removed"], ["-- a sql comment"])

    def test_deleted_file(self):
        diff = (
            "diff --git a/tests/test_a.py b/tests/test_a.py\n"
            "deleted file mode 100644\n"
            "--- a/tests/test_a.py\n"
            "+++ /dev/null\n"
            "@@ -1 +0,0 @@\n"
            "-x\n"
        )
        self.assertTrue(repair.parse_diff(diff)["tests/test_a.py"]["deleted"])


class TestSkipMarkers(unittest.TestCase):
    def test_detects_common_markers(self):
        for line in ("@Disabled", "  @Ignore", "@pytest.mark.skip(reason='x')", "@pytest.mark.xfail",
                     "@unittest.skip('x')", "pytest.skip('x')", "self.skipTest('x')",
                     "it.skip('does x', () => {})", "describe.skip('x')", "test.todo('x')",
                     "xit('x', () => {})", "xdescribe('x')"):
            self.assertEqual(len(repair.skip_markers([line])), 1, line)

    def test_ignores_ordinary_lines(self):
        self.assertEqual(repair.skip_markers(["assert skipped == 0", "def test_exit():", "it('x')"]), [])


class TestViolations(unittest.TestCase):
    def _change(self, removed=(), added=(), deleted=False):
        return {"removed": list(removed), "added": list(added), "deleted": deleted}

    def test_clean_repair_of_production_code(self):
        diff = {"src/app.py": self._change(removed=["x = 1"], added=["x = 2"])}
        self.assertEqual(repair.violations(diff, {}, {"src/app.py"}, _is_test), [])

    def test_check_script_change_is_rejected(self):
        diff = {"commands/check.sh": self._change(added=["exit 0"])}
        found = repair.violations(diff, {}, {"commands/check.sh"}, _is_test)
        self.assertEqual(len(found), 1)
        self.assertIn("commands/check.sh", found[0])

    def test_modified_existing_test_is_rejected(self):
        diff = {"tests/test_a.py": self._change(removed=["assert x == 1"], added=["assert x == 2"])}
        found = repair.violations(diff, {}, {"tests/test_a.py"}, _is_test)
        self.assertEqual(len(found), 1)
        self.assertIn("existing line", found[0])

    def test_insertions_in_existing_test_are_allowed(self):
        diff = {"tests/test_a.py": self._change(added=["    assert y == 3"])}
        self.assertEqual(repair.violations(diff, {}, {"tests/test_a.py"}, _is_test), [])

    def test_deleted_existing_test_is_rejected(self):
        diff = {"tests/test_a.py": self._change(removed=["x"], deleted=True)}
        found = repair.violations(diff, {}, {"tests/test_a.py"}, _is_test)
        self.assertEqual(found, ["tests/test_a.py: existing test file deleted"])

    def test_skip_marker_added_to_existing_test_is_rejected(self):
        diff = {"tests/test_a.py": self._change(added=["@pytest.mark.skip"])}
        found = repair.violations(diff, {}, {"tests/test_a.py"}, _is_test)
        self.assertEqual(len(found), 1)
        self.assertIn("skip marker", found[0])

    def test_new_test_file_may_change_freely_but_not_skip(self):
        diff = {"tests/test_new.py": self._change(added=["def test_x():", "    pass"])}
        self.assertEqual(repair.violations(diff, {}, set(), _is_test), [])
        found = repair.violations({}, {"tests/test_new.py": "xit('x', () => {})\n"}, set(), _is_test)
        self.assertEqual(len(found), 1)

    def test_untracked_non_test_file_is_ignored(self):
        self.assertEqual(repair.violations({}, {"src/new.py": "@Disabled\n"}, set(), _is_test), [])


class TestGuardCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        _git(self.tmp, "init", "-q", "-b", "main")
        _git(self.tmp, "config", "user.email", "t@t")
        _git(self.tmp, "config", "user.name", "t")
        self._write("commands/check.sh", "python3 -m pytest\n")
        self._write("app.py", "x = 1\n")
        self._write("tests/test_app.py", "def test_x():\n    assert x == 1\n")
        _git(self.tmp, "add", ".")
        _git(self.tmp, "commit", "-q", "-m", "base")
        os.chdir(self.tmp)
        self.base = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.tmp)

    def _write(self, rel, text):
        path = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def _run(self, *args):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = repair._main(["repair.py"] + list(args))
        return rc, out.getvalue() + err.getvalue()

    def test_clean_production_fix_passes(self):
        self._write("app.py", "x = 2\n")
        rc, out = self._run("guard", self.base)
        self.assertEqual(rc, 0, out)

    def test_edited_existing_test_fails(self):
        self._write("tests/test_app.py", "def test_x():\n    assert True\n")
        rc, out = self._run("guard", self.base)
        self.assertEqual(rc, 1)
        self.assertIn("tests/test_app.py", out)

    def test_edited_check_script_fails(self):
        self._write("commands/check.sh", "exit 0\n")
        rc, out = self._run("guard", self.base)
        self.assertEqual(rc, 1)
        self.assertIn("commands/check.sh", out)

    def test_committed_violation_is_still_caught(self):
        os.remove(os.path.join(self.tmp, "tests/test_app.py"))
        _git(self.tmp, "commit", "-q", "-am", "drop test")
        rc, out = self._run("guard", self.base)
        self.assertEqual(rc, 1)
        self.assertIn("deleted", out)

    def test_untracked_test_with_skip_fails(self):
        self._write("tests/test_new.py", "import pytest\n\n@pytest.mark.skip\ndef test_y():\n    pass\n")
        rc, out = self._run("guard", self.base)
        self.assertEqual(rc, 1)
        self.assertIn("tests/test_new.py", out)

    def test_unknown_ref_exits_2(self):
        rc, _ = self._run("guard", "no-such-ref")
        self.assertEqual(rc, 2)

    def test_usage_exits_2(self):
        rc, _ = self._run("guard")
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
