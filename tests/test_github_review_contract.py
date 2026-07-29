from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "plugins/grimoire/skills/gh-pr-review-loop"
SKILL = SKILL_DIR / "SKILL.md"
SIDECAR = SKILL_DIR / "agents/openai.yaml"
CONTRACT = SKILL_DIR / "references/github-review-contract.md"


class GitHubReviewPackageStaticGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.launcher = SKILL.read_text()
        cls.sidecar_text = SIDECAR.read_text()
        cls.contract = CONTRACT.read_text()

    def test_runtime_package_has_only_three_files(self) -> None:
        files = {
            path.relative_to(SKILL_DIR).as_posix()
            for path in SKILL_DIR.rglob("*")
            if path.is_file()
        }

        self.assertEqual(
            files,
            {
                "SKILL.md",
                "agents/openai.yaml",
                "references/github-review-contract.md",
            },
        )

    def test_launcher_only_gates_the_contract(self) -> None:
        self.assertLessEqual(len(self.launcher.splitlines()), 16)
        self.assertIn("Use only when explicitly invoked", self.launcher)
        self.assertIn("Before querying any target data", self.launcher)
        self.assertIn(
            "read\n`references/github-review-contract.md` completely",
            self.launcher,
        )
        self.assertIn("sole\nnormative source", self.launcher)
        self.assertNotIn("Finish only", self.launcher)
        self.assertNotIn("\n## ", self.launcher)

    def test_sidecar_has_exact_explicit_only_structure(self) -> None:
        self.assertEqual(
            self.sidecar_text,
            """\
interface:
  display_name: "GitHub PR Review Loop"
  short_description: "Review one exact GitHub PR and publish one review"
  default_prompt: "Use $gh-pr-review-loop to review the exact GitHub PR I provide."

policy:
  allow_implicit_invocation: false
""",
        )

    def test_contract_identity_blocks_have_static_shape(self) -> None:
        self.assertIn("`github-review-contract/v1`", self.contract)
        self.assertIn(
            "contract_source_identifier=github-review-contract/v1\\n\n"
            "contract_sha256=<SHA-256 of the exact bytes of "
            "github-review-contract.md>\\n\n"
            "principal=<authenticated principal login>\\n",
            self.contract,
        )
        self.assertNotIn("prompt_digest", self.contract)
        self.assertIn(
            "<!-- grimoire:gh-pr-review-loop review_key=<review_key> -->",
            self.contract,
        )

    def test_contract_has_expected_static_sections(self) -> None:
        headings = (
            "## Scope and trust boundary",
            "## Immutable identity",
            "## Static review and immutable decision",
            "## Closed validation matrix",
            "## Publication and reconciliation",
            "## Terminal output",
            "## Author-time repository validation",
        )

        for heading in headings:
            with self.subTest(heading=heading):
                self.assertEqual(self.contract.count(heading), 1)

    def test_validation_matrix_has_five_static_rows(self) -> None:
        rows = [
            line.split("|")[1].strip()
            for line in self.contract.splitlines()
            if line.startswith(
                (
                    "| Authority |",
                    "| Snapshot |",
                    "| Decision |",
                    "| Prepublication |",
                    "| Readback |",
                )
            )
        ]

        self.assertEqual(
            rows,
            ["Authority", "Snapshot", "Decision", "Prepublication", "Readback"],
        )
        for terminal in (
            "AUTHORITY_UNVERIFIED",
            "SNAPSHOT_INVALID",
            "DECISION_INVALID",
            "SNAPSHOT_CHANGED",
            "DECISION_EVIDENCE_CHANGED",
            "EXACT_MATCH",
            "READBACK_UNRESOLVED",
        ):
            with self.subTest(terminal=terminal):
                self.assertIn(terminal, self.contract)

    def test_static_publication_guards_are_present(self) -> None:
        self.assertIn("Support serialized invocations only", self.contract)
        self.assertIn("makes no concurrent or global exactly-once claim", self.contract)
        self.assertIn("PUBLICATION_REJECTED", self.contract)
        self.assertIn(
            "Never retry after a request might have been sent",
            self.contract,
        )
        self.assertNotIn("byte-identical retry", self.contract)

    def test_static_event_and_check_mappings_are_present(self) -> None:
        for mapping in (
            "`COMMENT` → `COMMENTED`",
            "`REQUEST_CHANGES` → `CHANGES_REQUESTED`",
            "`APPROVE` → `APPROVED`",
            "`NOT_CONFIGURED`",
            "`PASS`",
            "`PENDING`",
            "`FAIL_OR_UNVERIFIABLE`",
        ):
            with self.subTest(mapping=mapping):
                self.assertIn(mapping, self.contract)
        self.assertIn(
            "Authenticated principal is the PR author | `COMMENT`",
            self.contract,
        )
        self.assertIn(
            "Non-author review has any P0, P1, or P2 finding | `REQUEST_CHANGES`",
            self.contract,
        )
        self.assertIn("no P0/P1/P2 finding", self.contract)
        self.assertIn("check runs with `filter=latest`", self.contract)
        self.assertIn(
            "latest commit status per\ncase-insensitive context",
            self.contract,
        )
        for guard in (
            "`check_source_sha`",
            "complete configuration evidence proves no checks are required",
            "needed by a stronger event is missing or ambiguous | `COMMENT`",
            "`APPROVE` and `REQUEST_CHANGES` require complete, unambiguous evidence",
            "SNAPSHOT_CHANGED_AFTER_PUBLICATION",
        ):
            with self.subTest(guard=guard):
                self.assertIn(guard, self.contract)

    def test_static_readback_canonicalization_is_present(self) -> None:
        for field in (
            "Plan start anchor",
            "Observed end anchor: `(side, original_line)`",
            "original_start_line",
            "order-independent multisets",
            "Nonmatching markers never suppress",
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.contract)
        self.assertIn(
            "`(path, start_anchor, end_anchor, normalized_body)`",
            self.contract,
        )
        self.assertNotIn("fingerprint", self.contract)

    def test_repository_validation_is_explicitly_static(self) -> None:
        self.assertIn(
            "static-contract guards, not proof of\nruntime state safety",
            self.contract,
        )
        self.assertIn("live GitHub mutation as validation", self.contract)


if __name__ == "__main__":
    unittest.main()
