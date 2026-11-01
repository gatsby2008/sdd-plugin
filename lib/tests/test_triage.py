import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import triage


class TestClassify(unittest.TestCase):
    def test_trivial_when_no_layers_or_logic(self):
        c = triage.classify("Rename the welcome copy on the landing page.")
        self.assertEqual(c["ticket_type"], "trivial")
        self.assertEqual(c["path"], ["/sdd:commit", "/sdd:mr"])

    def test_focused_single_layer(self):
        c = triage.classify("Add a service method that validates the login form input.")
        self.assertEqual(c["ticket_type"], "focused")
        self.assertEqual(c["next"], "/sdd:implement")

    def test_standard_two_layers(self):
        c = triage.classify(
            "The service computes the discount and the repository persists the result."
        )
        self.assertEqual(c["ticket_type"], "standard")
        self.assertIn("service", c["layers"])
        self.assertIn("repository", c["layers"])
        self.assertEqual(c["path"][0], "/sdd:plan")

    def test_high_risk_on_async(self):
        c = triage.classify("A Kafka listener consumes the event and enriches it.")
        self.assertEqual(c["ticket_type"], "high-risk")
        self.assertIn("async/eventing", c["high_risk_signals"])
        self.assertIn("/sdd:test-design", c["path"])

    def test_high_risk_on_migration(self):
        c = triage.classify("Add a Flyway migration to alter table consent.")
        self.assertEqual(c["ticket_type"], "high-risk")
        self.assertIn("db-migration", c["high_risk_signals"])

    def test_high_risk_on_security(self):
        c = triage.classify("Add JWT token validation in the SecurityConfig.")
        self.assertEqual(c["ticket_type"], "high-risk")
        self.assertIn("security", c["high_risk_signals"])

    def test_high_risk_on_four_layers(self):
        text = (
            "The controller calls the service, which uses the repository, "
            "and a Feign client fetches external data."
        )
        c = triage.classify(text)
        self.assertEqual(c["ticket_type"], "high-risk")

    def test_complexity_label_matches_type(self):
        self.assertEqual(triage.classify("Kafka listener")["complexity"], "HIGH")
        self.assertEqual(
            triage.classify("service and repository")["complexity"], "MEDIUM"
        )


class TestEstimateFiles(unittest.TestCase):
    def test_two_per_layer(self):
        self.assertEqual(triage.estimate_files(2, "no files named"), 4)

    def test_floor_of_one(self):
        self.assertEqual(triage.estimate_files(0, "no files named"), 1)

    def test_respects_explicit_mentions(self):
        text = "Touch `Foo.java`, `Bar.java`, `Baz.java`, `Qux.java`."
        self.assertEqual(triage.estimate_files(1, text), 4)


class TmpSpecCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        (self.tmp / "_spec").mkdir(parents=True)
        self.addCleanup(self._tmp.cleanup)

    def _write_spec(self, slug, body):
        (self.tmp / "_spec" / f"{slug}-spec.md").write_text(body)


class TestMain(TmpSpecCase):
    def test_writes_path_json(self):
        self._write_spec(
            "s",
            "## Summary\nAdd a Kafka listener.\n\n## Behavior\nConsume the event.\n",
        )
        rc = triage.main(["s", "--spec-dir", str(self.tmp)])
        self.assertEqual(rc, 0)
        out = self.tmp / "_state" / "s-path.json"
        self.assertTrue(out.exists())
        data = json.loads(out.read_text())
        self.assertEqual(data["id"], "s")
        self.assertEqual(data["ticket_type"], "high-risk")
        self.assertEqual(data["schema_version"], 1)

    def test_missing_spec_returns_error(self):
        rc = triage.main(["nope", "--spec-dir", str(self.tmp)])
        self.assertEqual(rc, 1)

    def test_scopes_to_summary_and_behavior(self):
        # Risky word only outside Summary/Behavior must not drive the result.
        self._write_spec(
            "s",
            "## Summary\nRename a label.\n\n## Behavior\nNo logic change.\n\n"
            "## Notes\nUnrelated mention of a Kafka listener elsewhere.\n",
        )
        triage.main(["s", "--spec-dir", str(self.tmp)])
        data = json.loads((self.tmp / "_state" / "s-path.json").read_text())
        self.assertEqual(data["ticket_type"], "trivial")


class TestPlanRequired(unittest.TestCase):
    def test_high_risk_requires_plan(self):
        self.assertTrue(
            triage.classify("A Kafka listener consumes the event and enriches it.")[
                "plan_required"
            ]
        )

    def test_lower_tiers_do_not_require_plan(self):
        for text in [
            "Rename the welcome copy on the landing page.",
            "Add a service method that validates the login form input.",
            "The service computes the discount and the repository persists it.",
        ]:
            self.assertFalse(triage.classify(text)["plan_required"], text)

    def test_summary_flags_plan_required_only_for_high_risk(self):
        self.assertIn("REQUIRED", triage.render_summary(triage.classify("Kafka listener")))
        self.assertNotIn(
            "REQUIRED", triage.render_summary(triage.classify("Rename a label."))
        )


class TestPlanRequiredPersisted(TmpSpecCase):
    def test_path_json_carries_plan_required(self):
        (self.tmp / "_spec" / "s-spec.md").write_text(
            "## Summary\nAdd a Kafka listener.\n\n## Behavior\nConsume the event.\n"
        )
        triage.main(["s", "--spec-dir", str(self.tmp)])
        data = json.loads((self.tmp / "_state" / "s-path.json").read_text())
        self.assertTrue(data["plan_required"])



KAFKA_SPEC = "## Summary\nLog the lead.\n\n## Behavior\n1. **B1** — does not publish to Kafka.\n"
TRIVIAL_SPEC = "## Summary\nRename a label.\n\n## Behavior\nNo logic change.\n"


class TestTierOverride(TmpSpecCase):
    def _run(self, *extra):
        return triage.main(["s", "--spec-dir", str(self.tmp), *extra])

    def _path_json(self):
        return json.loads((self.tmp / "_state" / "s-path.json").read_text())

    def test_force_lower_tier(self):
        # A negated mention ("does not publish to Kafka") still trips the
        # async/eventing regex — the case the override exists for.
        self._write_spec("s", KAFKA_SPEC)
        self.assertEqual(self._run(), 0)
        self.assertEqual(self._path_json()["ticket_type"], "high-risk")

        self.assertEqual(self._run("--tier", "focused", "--reason", "negated Kafka mention"), 0)
        data = self._path_json()
        self.assertEqual(data["ticket_type"], "focused")
        self.assertEqual(data["complexity"], "LOW")
        self.assertEqual(data["path"], triage.PATHS["focused"])
        self.assertEqual(data["next"], "/sdd:implement")
        self.assertFalse(data["plan_required"])
        self.assertEqual(data["override"]["tier"], "focused")
        self.assertEqual(data["override"]["reason"], "negated Kafka mention")
        self.assertEqual(data["override"]["auto_tier"], "high-risk")

    def test_force_higher_tier(self):
        self._write_spec("s", TRIVIAL_SPEC)
        self.assertEqual(self._run("--tier", "high-risk", "--reason", "touches billing"), 0)
        data = self._path_json()
        self.assertEqual(data["ticket_type"], "high-risk")
        self.assertTrue(data["plan_required"])
        self.assertIn("/sdd:test-design", data["path"])
        self.assertEqual(data["override"]["auto_tier"], "trivial")

    def test_reason_is_mandatory(self):
        self._write_spec("s", KAFKA_SPEC)
        self.assertEqual(self._run("--tier", "focused"), 2)
        self.assertEqual(self._run("--tier", "focused", "--reason", "   "), 2)
        self.assertFalse((self.tmp / "_state" / "s-path.json").exists())

    def test_unknown_tier_rejected(self):
        self._write_spec("s", KAFKA_SPEC)
        with self.assertRaises(SystemExit):
            self._run("--tier", "medium", "--reason", "x")

    def test_override_is_sticky_across_reruns(self):
        self._write_spec("s", KAFKA_SPEC)
        self._run("--tier", "standard", "--reason", "no eventing")
        self._run()  # e.g. spec re-drafted: triage runs again without --tier
        data = self._path_json()
        self.assertEqual(data["ticket_type"], "standard")
        self.assertEqual(data["override"]["reason"], "no eventing")

    def test_tier_auto_drops_override(self):
        self._write_spec("s", KAFKA_SPEC)
        self._run("--tier", "focused", "--reason", "x")
        self.assertEqual(self._run("--tier", "auto"), 0)
        data = self._path_json()
        self.assertEqual(data["ticket_type"], "high-risk")
        self.assertNotIn("override", data)

    def test_no_override_keeps_path_json_shape(self):
        self._write_spec("s", KAFKA_SPEC)
        self._run()
        self.assertNotIn("override", self._path_json())

    def test_summary_shows_override(self):
        c = triage.apply_override(triage.classify("Kafka listener"), "focused", "why not")
        out = triage.render_summary(c)
        self.assertIn("Override: forced focused (auto: high-risk", out)
        self.assertIn("Why:     override: why not", out)
        self.assertNotIn("REQUIRED", out)


class TestPlanGateRespectsOverride(TmpSpecCase):
    """The plan-required gate (/sdd:implement Step 3.4) follows the forced tier."""

    def setUp(self):
        super().setUp()
        import gates
        self.gates = gates

    def _required(self):
        return self.gates.plan_required("s", str(self.tmp))

    def test_forced_lower_tier_lifts_the_gate(self):
        self._write_spec("s", KAFKA_SPEC)
        triage.main(["s", "--spec-dir", str(self.tmp)])
        self.assertTrue(self._required())
        triage.main(["s", "--spec-dir", str(self.tmp), "--tier", "standard", "--reason", "x"])
        self.assertFalse(self._required())

    def test_forced_high_risk_engages_the_gate(self):
        self._write_spec("s", TRIVIAL_SPEC)
        triage.main(["s", "--spec-dir", str(self.tmp)])
        self.assertFalse(self._required())
        triage.main(["s", "--spec-dir", str(self.tmp), "--tier", "high-risk", "--reason", "x"])
        self.assertTrue(self._required())
        (self.tmp / "_plan").mkdir()
        (self.tmp / "_plan" / "s-plan.md").write_text("plan")
        self.assertFalse(self._required())

    def test_override_block_wins_over_plan_required_field(self):
        (self.tmp / "_state").mkdir()
        (self.tmp / "_state" / "s-path.json").write_text(json.dumps(
            {"id": "s", "plan_required": True, "override": {"tier": "focused", "reason": "x"}}
        ))
        self.assertFalse(self._required())

    def test_cli_exit_code_follows_override(self):
        import subprocess
        root = self.tmp.parent / (self.tmp.name + "-proj")
        sw = root / ".specwork"
        (sw / "_spec").mkdir(parents=True)
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        (sw / "_spec" / "s-spec.md").write_text(KAFKA_SPEC)
        lib = Path(triage.__file__).resolve().parent

        def check():
            return subprocess.run(
                [sys.executable, str(lib / "gates.py"), "check-plan-required", "s"],
                cwd=root, capture_output=True, text=True,
            ).returncode

        triage.main(["s", "--spec-dir", str(sw)])
        self.assertEqual(check(), 1)
        triage.main(["s", "--spec-dir", str(sw), "--tier", "focused", "--reason", "x"])
        self.assertEqual(check(), 0)

if __name__ == "__main__":
    unittest.main()
