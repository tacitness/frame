from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "validate_metadata", ROOT / "scripts" / "validate-metadata.py"
)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class GovernanceTests(unittest.TestCase):
    def test_valid_planned_issue(self) -> None:
        issue = {
            "title": "[protocol] Validate fragmented requests",
            "labels": [
                {"name": "test"},
                {"name": "p2"},
                {"name": "protocol"},
                {"name": "release:none"},
            ],
            "milestone": {"title": "v0.1.0 - Safety and conformance foundation"},
            "body": "Parent epic: E02 / #12",
        }
        self.assertEqual(VALIDATOR.validate_issue(issue), [])

    def test_missing_area_and_multiple_types_are_rejected(self) -> None:
        issue = {
            "title": "[protocol] Ambiguous work",
            "labels": [{"name": "bug"}, {"name": "test"}, {"name": "p2"}],
            "milestone": None,
            "body": "",
        }
        errors = VALIDATOR.validate_issue(issue)
        self.assertTrue(any("exactly one type" in error for error in errors))
        self.assertTrue(any("area label" in error for error in errors))

    def test_pr_title_uses_conventional_commits(self) -> None:
        self.assertEqual(
            VALIDATOR.validate_pr_title("fix(protocol): reject truncated requests"), []
        )
        self.assertTrue(VALIDATOR.validate_pr_title("Fix truncated requests"))

    def test_every_epic_maps_to_a_declared_milestone(self) -> None:
        milestones = {
            entry["title"]
            for entry in json.loads(
                (ROOT / "ops/github/milestones.json").read_text(encoding="utf-8")
            )
        }
        epics = json.loads((ROOT / "ops/github/epics.json").read_text(encoding="utf-8"))
        self.assertEqual(len({epic["id"] for epic in epics}), len(epics))
        self.assertTrue(all(epic["milestone"] in milestones for epic in epics))

    def test_issue_catalog_has_one_valid_parent_and_complete_axes(self) -> None:
        epics = json.loads((ROOT / "ops/github/epics.json").read_text(encoding="utf-8"))
        issues = json.loads((ROOT / "ops/github/issues.json").read_text(encoding="utf-8"))
        epic_ids = {epic["id"] for epic in epics}
        issue_ids = {issue["id"] for issue in issues}

        self.assertEqual(len(issue_ids), len(issues))
        self.assertTrue(all(issue["epic"] in epic_ids for issue in issues))
        self.assertTrue(
            all(issue["id"].startswith(f"{issue['epic']}-I") for issue in issues)
        )
        type_labels = set(VALIDATOR.POLICY["axes"]["type"]["labels"])
        priority_labels = set(VALIDATOR.POLICY["axes"]["priority"]["labels"])
        release_labels = set(VALIDATOR.POLICY["axes"]["release"]["labels"])
        self.assertTrue(all(issue["type"] in type_labels for issue in issues))
        self.assertTrue(
            all(issue["priority"] in priority_labels for issue in issues)
        )
        self.assertTrue(all(issue["areas"] for issue in issues))
        self.assertTrue(
            all(issue["releaseImpact"] in release_labels for issue in issues)
        )
        self.assertTrue(
            all(any(issue["epic"] == epic_id for issue in issues) for epic_id in epic_ids)
        )

    def test_default_branch_governance_targets_main(self) -> None:
        ruleset = json.loads(
            (ROOT / "ops/github/ruleset-main.json").read_text(encoding="utf-8")
        )
        self.assertEqual(ruleset["name"], "Protected main delivery")
        self.assertEqual(
            ruleset["conditions"]["ref_name"]["include"], ["refs/heads/main"]
        )
        bootstrap = (ROOT / "scripts/github-bootstrap.sh").read_text(encoding="utf-8")
        self.assertIn("contents/.github/workflows/ci.yml?ref=main", bootstrap)

    def test_ci_bootstrap_uses_published_actionlint_asset_and_safe_policy_fallback(
        self,
    ) -> None:
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        metadata = (ROOT / ".github/workflows/metadata.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("actionlint_1.7.12_linux_amd64.tar.gz", ci)
        self.assertNotIn("actionlint_1.7.12_linux_x86_64.tar.gz", ci)
        self.assertIn("github.event.pull_request.base.sha", metadata)
        self.assertIn("The policy-introduction PR has no validator", metadata)
        self.assertIn("len(title) > 72", metadata)

        secrets_scan = (ROOT / "scripts/git-secrets-scan.sh").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("--quiet", secrets_scan)

    def test_implemented_test_suites_are_hardware_free(self) -> None:
        manifest = json.loads((ROOT / "tests/manifest.json").read_text(encoding="utf-8"))
        implemented = [
            suite for suite in manifest["suites"] if suite["status"] == "implemented"
        ]
        self.assertTrue(implemented)
        self.assertTrue(all(not suite["hardware"] for suite in implemented))


if __name__ == "__main__":
    unittest.main()
