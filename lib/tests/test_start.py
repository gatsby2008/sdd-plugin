import importlib.util
import json
import os
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

LIB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, LIB_DIR)

# start.py can't be imported by name (hyphen in filename).
_mod_spec = importlib.util.spec_from_file_location("start", Path(LIB_DIR) / "start.py")
_start = importlib.util.module_from_spec(_mod_spec)
_mod_spec.loader.exec_module(_start)


class TestBuildState(unittest.TestCase):
    def test_basic_state_shape(self):
        state = _start.build_state(
            "test-slug", "TICKET-123", "jira", "feature/TICKET-123", "development", ".specwork")
        self.assertEqual(state["id"], "test-slug")
        self.assertEqual(state["ticket"], "TICKET-123")
        self.assertEqual(state["branch"], "feature/TICKET-123")
        self.assertEqual(state["base_branch"], "development")
        self.assertEqual(state["schema_version"], 1)
        self.assertFalse(state["non_interactive"])

    def test_sets_none_ticket(self):
        state = _start.build_state("test-slug", "none", "freetext", "feature/test", "main", ".specwork")
        self.assertIsNone(state["ticket"])

    def test_sets_non_interactive_from_env(self):
        with mock.patch.dict(os.environ, {"SDD_NON_INTERACTIVE": "1"}, clear=False):
            state = _start.build_state(
                "test-slug", "TICKET-123", "jira", "feature/TICKET-123", "development", ".specwork")
        self.assertTrue(state["non_interactive"])

    def test_sets_non_interactive_from_param(self):
        # --non-interactive CLI flag passes non_interactive=True explicitly,
        # independent of the environment variable.
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SDD_NON_INTERACTIVE", None)
            state = _start.build_state(
                "test-slug", "TICKET-123", "jira", "feature/TICKET-123", "development",
                ".specwork", non_interactive=True)
        self.assertTrue(state["non_interactive"])

    def test_non_interactive_param_wins_over_missing_env(self):
        # Even with no env var, param=True produces True.
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SDD_NON_INTERACTIVE", None)
            state = _start.build_state(
                "test-slug", "none", "freetext", "feature/test", "main", ".specwork",
                non_interactive=True)
        self.assertTrue(state["non_interactive"])

class TestBuildCache(unittest.TestCase):
    def test_empty_cache_shape(self):
        cache = _start.build_cache("test-slug")
        self.assertEqual(cache["id"], "test-slug")
        self.assertEqual(cache["repositories"], [])
        self.assertEqual(cache["related_tests"], [])
        self.assertEqual(cache["notes"], [])


class TmpSpecCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        (self.tmp / "_spec").mkdir(parents=True)
        self.addCleanup(self._tmp.cleanup)


class TestSourceHasRealBody(TmpSpecCase):
    def test_false_when_file_absent(self):
        self.assertFalse(_start._source_has_real_body(self.tmp / "_spec" / "missing.md"))

    def test_false_when_placeholder(self):
        p = self.tmp / "_spec" / "s.md"
        p.write_text("# s — Source\n\nRaw input from freetext goes here.\n")
        self.assertFalse(_start._source_has_real_body(p))

    def test_true_when_real_content(self):
        p = self.tmp / "_spec" / "s.md"
        p.write_text("# s — Source\n\n> JIRA: TICKET-1\n\nFix duplicate leads.\n")
        self.assertTrue(_start._source_has_real_body(p))

    def test_false_when_empty(self):
        p = self.tmp / "_spec" / "s.md"
        p.write_text("")
        self.assertFalse(_start._source_has_real_body(p))


class TestWriteSourceMd(TmpSpecCase):
    def test_creates_file(self):
        result = _start.write_source_md("test-slug", str(self.tmp), "TICKET-123", "jira")
        self.assertIn("test-slug-source.md", result)
        self.assertTrue((self.tmp / "_spec" / "test-slug-source.md").exists())

    def test_uses_freetext_label(self):
        file_path = _start.write_source_md("s", str(self.tmp), "none", "freetext")
        self.assertIn("Free text", Path(file_path).read_text())

    def test_placeholder_when_no_body(self):
        file_path = _start.write_source_md("s", str(self.tmp), "none", "freetext")
        self.assertIn("Raw input from freetext goes here", Path(file_path).read_text())

    def test_persists_body_when_given(self):
        body = "summary: dedupe leads\nbehaviour: ignore null applicationId"
        file_path = _start.write_source_md("s", str(self.tmp), "none", "freetext", body)
        content = Path(file_path).read_text()
        self.assertIn("summary: dedupe leads", content)
        self.assertIn("behaviour: ignore null applicationId", content)
        self.assertNotIn("Raw input from freetext goes here", content)

    def test_blank_body_falls_back_to_placeholder(self):
        file_path = _start.write_source_md("s", str(self.tmp), "none", "freetext", "   \n  ")
        self.assertIn("Raw input from freetext goes here", Path(file_path).read_text())

    def test_does_not_overwrite_existing_real_content(self):
        # Simulates the Jira path: jira_write_issue_markdown wrote the file first.
        existing = "# s — Source\n\n> JIRA: TICKET-1\n\nFix duplicate leads.\n"
        p = self.tmp / "_spec" / "s-source.md"
        p.write_text(existing)
        _start.write_source_md("s", str(self.tmp), "TICKET-1", "jira")
        self.assertEqual(p.read_text(), existing)

    def test_overwrites_placeholder_with_real_body(self):
        # Placeholder already exists — should be replaced when a real body is given.
        p = self.tmp / "_spec" / "s-source.md"
        p.write_text("# s — Source\n\nRaw input from freetext goes here.\n")
        _start.write_source_md("s", str(self.tmp), "none", "freetext", "real content here")
        self.assertIn("real content here", p.read_text())
        self.assertNotIn("goes here.", p.read_text())


class TestWriteSpecScaffold(TmpSpecCase):
    def test_creates_file(self):
        result = _start.write_spec_scaffold("test-slug", str(self.tmp), "TICKET-123", "jira")
        self.assertIn("test-slug-spec.md", result)
        self.assertTrue((self.tmp / "_spec" / "test-slug-spec.md").exists())

    def test_contains_expected_sections(self):
        file_path = _start.write_spec_scaffold("s", str(self.tmp), "none", "freetext")
        content = Path(file_path).read_text()
        self.assertIn("## Summary", content)
        self.assertIn("## Behavior", content)
        self.assertIn("## Open Questions", content)


class TestMainDoesNotCreateSpec(unittest.TestCase):
    """start no longer drafts spec.md — that is /sdd:spec's job."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self._cwd = os.getcwd()
        os.chdir(self.tmp)
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(lambda: os.chdir(self._cwd))

    def test_main_writes_state_but_not_spec(self):
        import subprocess
        start_py = Path(LIB_DIR) / "start.py"
        result = subprocess.run(
            ["python3", str(start_py), "--slug", "demo", "--ticket", "none",
             "--input-type", "freetext", "--branch", "feature/demo", "--base-branch", "main"],
            capture_output=True, text=True, check=True,
        )
        out = json.loads(result.stdout)
        # Bootstrap artifacts exist.
        self.assertTrue((self.tmp / ".specwork" / "_state" / "demo-state.json").exists())
        self.assertTrue((self.tmp / ".specwork" / "_spec" / "demo-source.md").exists())
        # spec.md is NOT created by start.
        self.assertFalse((self.tmp / ".specwork" / "_spec" / "demo-spec.md").exists())
        self.assertFalse(out["spec_created"])
        # spec_file is declared (path) for /sdd:spec to write.
        self.assertIn("demo-spec.md", out["spec_file"])

    def _run_start(self, slug_arg, branch="feature/PROJ-123"):
        import subprocess
        return subprocess.run(
            ["python3", str(Path(LIB_DIR) / "start.py"), "--slug", slug_arg, "--ticket", "none",
             "--input-type", "freetext", "--branch", branch, "--base-branch", "main"],
            capture_output=True, text=True,
        )

    def test_main_rejects_non_canonical_slug_without_writing(self):
        for bad in ["PROJ-123", "IR-70.1", "my_slug", "-"]:
            result = self._run_start(bad)
            self.assertEqual(result.returncode, 2, bad)
            self.assertIn("lib/slug.py", result.stderr)
        self.assertFalse((self.tmp / ".specwork").exists())

    def test_main_accepts_slug_py_output(self):
        import slug as slugs
        canonical = slugs.slug_from_branch("feature/PROJ-123")
        self.assertEqual(canonical, "proj-123")
        result = self._run_start(canonical)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.tmp / ".specwork" / "_state" / "proj-123-state.json").exists())

    def test_main_persists_source_body_file(self):
        import subprocess
        start_py = Path(LIB_DIR) / "start.py"
        body_file = self.tmp / "freetext.txt"
        body_file.write_text(
            "summary: fix duplicate leads when applicationId is null\n"
            "behaviour: skip dedupe instead of throwing",
            encoding="utf-8",
        )
        result = subprocess.run(
            ["python3", str(start_py), "--slug", "demo", "--ticket", "none",
             "--input-type", "freetext", "--branch", "feature/demo",
             "--base-branch", "main", "--source-body-file", str(body_file)],
            capture_output=True, text=True, check=True,
        )
        out = json.loads(result.stdout)
        self.assertTrue(out["source_has_body"])
        source = (self.tmp / ".specwork" / "_spec" / "demo-source.md").read_text()
        self.assertIn("fix duplicate leads when applicationId is null", source)
        self.assertNotIn("Raw input from freetext goes here", source)

    def test_main_missing_source_body_file_falls_back(self):
        import subprocess
        start_py = Path(LIB_DIR) / "start.py"
        result = subprocess.run(
            ["python3", str(start_py), "--slug", "demo", "--ticket", "none",
             "--input-type", "freetext", "--branch", "feature/demo",
             "--base-branch", "main", "--source-body-file", str(self.tmp / "nope.txt")],
            capture_output=True, text=True, check=True,
        )
        out = json.loads(result.stdout)
        self.assertFalse(out["source_has_body"])
        source = (self.tmp / ".specwork" / "_spec" / "demo-source.md").read_text()
        self.assertIn("Raw input from freetext goes here", source)

    def test_main_source_body_inline(self):
        """--source-body persists inline text without creating a temp file."""
        import subprocess
        start_py = Path(LIB_DIR) / "start.py"
        result = subprocess.run(
            ["python3", str(start_py), "--slug", "demo", "--ticket", "none",
             "--input-type", "freetext", "--branch", "feature/demo",
             "--base-branch", "main", "--source-body", "inline description, no temp file"],
            capture_output=True, text=True, check=True,
        )
        out = json.loads(result.stdout)
        self.assertTrue(out["source_has_body"])
        source = (self.tmp / ".specwork" / "_spec" / "demo-source.md").read_text()
        self.assertIn("inline description, no temp file", source)
        self.assertNotIn("Raw input from freetext goes here", source)
        # No source-input.md or other temp file should exist.
        extras = [p for p in (self.tmp / ".specwork" / "_spec").iterdir()
                  if "source-input" in p.name]
        self.assertEqual(extras, [])

    def test_main_source_body_takes_precedence_over_file(self):
        """--source-body wins when both --source-body and --source-body-file are given."""
        import subprocess
        start_py = Path(LIB_DIR) / "start.py"
        body_file = self.tmp / "other.txt"
        body_file.write_text("content from file", encoding="utf-8")
        result = subprocess.run(
            ["python3", str(start_py), "--slug", "demo", "--ticket", "none",
             "--input-type", "freetext", "--branch", "feature/demo",
             "--base-branch", "main",
             "--source-body", "inline wins",
             "--source-body-file", str(body_file)],
            capture_output=True, text=True, check=True,
        )
        source = (self.tmp / ".specwork" / "_spec" / "demo-source.md").read_text()
        self.assertIn("inline wins", source)
        self.assertNotIn("content from file", source)

    def test_main_non_interactive_flag_writes_true_in_state(self):
        """--non-interactive CLI flag sets non_interactive=true in state.json
        without relying on the SDD_NON_INTERACTIVE env var being inherited."""
        import subprocess
        start_py = Path(LIB_DIR) / "start.py"
        env = os.environ.copy()
        env.pop("SDD_NON_INTERACTIVE", None)  # ensure env var is absent
        result = subprocess.run(
            ["python3", str(start_py), "--slug", "demo", "--ticket", "none",
             "--input-type", "freetext", "--branch", "feature/demo",
             "--base-branch", "main", "--non-interactive"],
            capture_output=True, text=True, check=True, env=env,
        )
        state = json.loads(
            (self.tmp / ".specwork" / "_state" / "demo-state.json").read_text()
        )
        self.assertTrue(state["non_interactive"])

    def test_main_source_has_body_true_when_jira_prewritten(self):
        """source_has_body is True even when start.py is called without --source-body,
        as long as jira_write_issue_markdown already populated source.md."""
        import subprocess
        start_py = Path(LIB_DIR) / "start.py"
        # Simulate what jira_write_issue_markdown writes before start.py is called.
        spec_dir = self.tmp / ".specwork"
        (spec_dir / "_spec").mkdir(parents=True, exist_ok=True)
        (spec_dir / "_spec" / "demo-source.md").write_text(
            "# demo — Source\n\n> JIRA: TICKET-42\n\nFix the bug.\n", encoding="utf-8"
        )
        result = subprocess.run(
            ["python3", str(start_py), "--slug", "demo", "--ticket", "TICKET-42",
             "--input-type", "jira", "--branch", "feature/demo", "--base-branch", "main"],
            capture_output=True, text=True, check=True,
        )
        out = json.loads(result.stdout)
        self.assertTrue(out["source_has_body"])
        # Original Jira content must be intact.
        source = (spec_dir / "_spec" / "demo-source.md").read_text()
        self.assertIn("Fix the bug.", source)


class TestEnsureGitignore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self._cwd = os.getcwd()
        os.chdir(self.tmp)
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(lambda: os.chdir(self._cwd))

    def test_creates_gitignore_when_absent(self):
        result = _start.ensure_gitignore()
        self.assertTrue(result["appended"])
        content = (self.tmp / ".gitignore").read_text()
        self.assertIn(".specwork/", content)

    def test_appends_to_existing_gitignore(self):
        (self.tmp / ".gitignore").write_text("node_modules/\n")
        result = _start.ensure_gitignore()
        self.assertTrue(result["appended"])
        content = (self.tmp / ".gitignore").read_text()
        self.assertIn("node_modules/", content)
        self.assertIn(".specwork/", content)

    def test_idempotent_when_already_ignored(self):
        (self.tmp / ".gitignore").write_text(".specwork/\n")
        result = _start.ensure_gitignore()
        self.assertFalse(result["appended"])
        # No duplicate entry.
        content = (self.tmp / ".gitignore").read_text()
        self.assertEqual(content.count(".specwork/"), 1)

    def test_idempotent_for_bare_specwork_entry(self):
        # An entry without trailing slash also counts as ignored.
        (self.tmp / ".gitignore").write_text(".specwork\n")
        result = _start.ensure_gitignore()
        self.assertFalse(result["appended"])

    def test_tracked_false_outside_git(self):
        # No git repo here → ls-files yields nothing → not tracked.
        result = _start.ensure_gitignore()
        self.assertFalse(result["tracked"])


class TestExtractBullets(unittest.TestCase):
    def test_selective_when_invariants_heading_present(self):
        # A doc with an Invariants heading only yields bullets under matching sections.
        text = (
            "# Domain\n\n"
            "## How to organize\n\n- Intro prose bullet, not a rule.\n\n"
            "### Invariants\n\n- Real rule one.\n- Real rule two.\n\n"
            "## Adding a domain\n\n- Meta checklist bullet.\n"
        )
        self.assertEqual(_start._extract_rules(text), ["Real rule one.", "Real rule two."])

    def test_fallback_extracts_all_when_no_rule_heading(self):
        # AGENTS-style doc: no Invariants/Constraints heading → every bullet is a rule.
        text = "# AGENTS\n\n## Core Rules\n\n- Rule a.\n- Rule b.\n\n## Scope\n\n- Rule c.\n"
        self.assertEqual(_start._extract_rules(text), ["Rule a.", "Rule b.", "Rule c."])

    def test_constraint_heading_also_triggers_selective(self):
        text = "## Notes\n\n- skip me.\n\n## Architecture Constraints\n\n- keep me.\n"
        self.assertEqual(_start._extract_rules(text), ["keep me."])

    def test_joins_wrapped_continuation_lines(self):
        text = "### Invariants\n\n- First line of rule\n  wraps onto a second line.\n"
        self.assertEqual(
            _start._extract_rules(text), ["First line of rule wraps onto a second line."]
        )

    def test_ignores_tables_but_captures_callouts(self):
        # Tables are skipped; a callout under a rule section is captured (prefixed "Note: ").
        text = (
            "### Invariants\n\n"
            "| col | col |\n|-----|-----|\n| a | b |\n\n"
            "- the rule.\n\n"
            "> a clarifying callout.\n"
        )
        self.assertEqual(_start._extract_rules(text), ["the rule.", "Note: a clarifying callout."])

    def test_joins_multiline_callout(self):
        text = "## Invariants\n\n> first line of note\n> second line of note.\n"
        self.assertEqual(
            _start._extract_rules(text), ["Note: first line of note second line of note."]
        )

    def test_callouts_ignored_in_fallback_mode(self):
        # No rule-section heading → fallback (all bullets), but callouts are NOT pulled
        # so prose-heavy docs like AGENTS.md don't leak asides.
        text = "## Core Rules\n\n- a rule.\n\n> an aside, not a rule.\n"
        self.assertEqual(_start._extract_rules(text), ["a rule."])

    def test_blank_callout_line_separates_callouts(self):
        text = "## Invariants\n\n> note one.\n\n> note two.\n"
        self.assertEqual(
            _start._extract_rules(text), ["Note: note one.", "Note: note two."]
        )


class TestBuildRules(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_expands_directory_to_markdown_files(self):
        rules_dir = self.tmp / "rules"
        rules_dir.mkdir()
        (rules_dir / "a.md").write_text("- alpha rule.\n")
        (rules_dir / "b.md").write_text("- bravo rule.\n")
        (rules_dir / "ignore.txt").write_text("- not markdown.\n")

        result = _start.build_rules("slug", [str(rules_dir)])
        self.assertEqual(len(result["source_files"]), 2)  # only *.md
        self.assertIn("alpha rule.", result["global_rules"])
        self.assertIn("bravo rule.", result["global_rules"])
        self.assertNotIn("not markdown.", result["global_rules"])

    def test_missing_paths_are_skipped(self):
        result = _start.build_rules("slug", [str(self.tmp / "nope.md")])
        self.assertEqual(result["source_files"], [])
        self.assertEqual(result["global_rules"], [])

    def test_dedupes_preserving_order(self):
        f = self.tmp / "r.md"
        f.write_text("- one.\n- two.\n- one.\n")
        result = _start.build_rules("slug", [str(f)])
        self.assertEqual(result["global_rules"], ["one.", "two."])

    def test_caps_at_max_global_rules(self):
        f = self.tmp / "many.md"
        f.write_text("\n".join(f"- rule {i}." for i in range(_start.MAX_GLOBAL_RULES + 25)))
        result = _start.build_rules("slug", [str(f)])
        self.assertEqual(len(result["global_rules"]), _start.MAX_GLOBAL_RULES)

    def test_warns_on_stderr_when_truncating(self):
        import contextlib
        import io

        f = self.tmp / "many.md"
        f.write_text("\n".join(f"- rule {i}." for i in range(_start.MAX_GLOBAL_RULES + 25)))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            _start.build_rules("slug", [str(f)])
        msg = err.getvalue()
        self.assertIn("WARNING", msg)
        self.assertIn("25 dropped", msg)

    def test_no_warning_when_within_cap(self):
        import contextlib
        import io

        f = self.tmp / "few.md"
        f.write_text("- one.\n- two.\n")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            _start.build_rules("slug", [str(f)])
        self.assertEqual(err.getvalue(), "")


class TestScaffoldRulesIfMissing(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self._cwd = os.getcwd()
        os.chdir(self.tmp)
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(lambda: os.chdir(self._cwd))
        self.template = self.tmp / "template.md"
        self.template.write_text("# Service Rules\n\n- starter.\n", encoding="utf-8")

    def test_scaffolds_when_nothing_exists(self):
        result = _start.scaffold_rules_if_missing(str(self.template))
        self.assertTrue(result["scaffolded"])
        target = self.tmp / ".claude" / "rules" / "service-rules.md"
        self.assertTrue(target.exists())
        self.assertIn("starter.", target.read_text())

    def test_skips_when_legacy_file_exists(self):
        legacy = self.tmp / ".claude" / "service-rules.md"
        legacy.parent.mkdir(parents=True)
        legacy.write_text("# existing legacy\n", encoding="utf-8")
        result = _start.scaffold_rules_if_missing(str(self.template))
        self.assertFalse(result["scaffolded"])
        self.assertFalse((self.tmp / ".claude" / "rules" / "service-rules.md").exists())

    def test_skips_when_rules_dir_has_md(self):
        rules = self.tmp / ".claude" / "rules"
        rules.mkdir(parents=True)
        (rules / "existing.md").write_text("- a rule.\n", encoding="utf-8")
        result = _start.scaffold_rules_if_missing(str(self.template))
        self.assertFalse(result["scaffolded"])
        self.assertFalse((rules / "service-rules.md").exists())  # untouched

    def test_reports_missing_template(self):
        result = _start.scaffold_rules_if_missing(str(self.tmp / "nope.md"))
        self.assertFalse(result["scaffolded"])
        self.assertIn("template not found", result["reason"])


if __name__ == "__main__":
    unittest.main()
