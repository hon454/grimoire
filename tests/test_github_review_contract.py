from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "plugins/grimoire/skills/gh-pr-review-loop"
SKILL = SKILL_DIR / "SKILL.md"
SIDECAR = SKILL_DIR / "agents/openai.yaml"
CONTRACT = SKILL_DIR / "references/github-review-contract.md"


class GitHubReviewContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = CONTRACT.read_text()

    def test_package_has_only_the_three_runtime_files(self) -> None:
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

    def test_launcher_is_small_and_only_gates_the_contract(self) -> None:
        launcher = SKILL.read_text()

        self.assertLessEqual(len(launcher.splitlines()), 20)
        self.assertIn("Use only when explicitly invoked", launcher)
        self.assertIn("Before querying any target data", launcher)
        self.assertIn("read\n`references/github-review-contract.md` completely", launcher)
        self.assertIn("contract-required terminal object", launcher)
        self.assertNotIn("\n## ", launcher)
        self.assertNotIn("Workflow", launcher)
        self.assertNotIn("Hard Boundaries", launcher)

    def test_sidecar_is_explicit_only_and_has_no_version_prose(self) -> None:
        sidecar = SIDECAR.read_text()

        self.assertIn('short_description: "Review one exact GitHub PR and publish once"', sidecar)
        self.assertIn('default_prompt: "Use $gh-pr-review-loop', sidecar)
        self.assertIn("allow_implicit_invocation: false", sidecar)
        self.assertNotRegex(sidecar, r"(?i)\bversion\b|\bv\d+(?:\.\d+)*\b")

    def test_prompt_digest_uses_only_contract_identity_and_exact_bytes(self) -> None:
        self.assertIn(
            "Compute `contract_sha256` as the SHA-256 of the exact bytes of this file.",
            self.contract,
        )
        self.assertIn(
            "Compute `prompt_digest` from only the following labeled UTF-8 byte "
            "sequence:\n\n"
            "```\n"
            "contract_source_identifier=github-review-contract/v1\\n\n"
            "contract_sha256=<SHA-256 of the exact bytes of "
            "github-review-contract.md>\\n\n"
            "```",
            self.contract,
        )
        self.assertIn(
            "Do not include `SKILL.md`,\n"
            "`agents/openai.yaml`, user prose, PR data, a local path, or any editorial\n"
            "sidecar change in this digest.",
            self.contract,
        )

    def test_snapshot_is_fixed_before_analysis_and_identity(self) -> None:
        self.assertIn(
            "Before beginning static analysis, record one complete `snapshot_tuple`.",
            self.contract,
        )
        self.assertIn(
            "same tuple for all analysis and the review-key calculation with its\n"
            "contract-only `prompt_digest`",
            self.contract,
        )

    def test_dedupe_is_readback_only_without_concurrency_state(self) -> None:
        for forbidden in (
            "CONCURRENT_RUN",
            "competing/nonterminal",
            "concurrency coordination",
            "shared state",
            "prepublication marker",
        ):
            self.assertNotIn(forbidden, self.contract)
        self.assertIn(
            "Deduplicate only through complete marker/review readback and exact\n"
            "reconciliation.",
            self.contract,
        )
        self.assertIn(
            "On every invocation, cancellation recovery, or\n"
            "resume, reconcile that key before any new publication decision.",
            self.contract,
        )

    def test_prepublication_rechecks_the_full_tuple_and_aborts_on_drift(self) -> None:
        self.assertIn(
            "Immediately before the single request, bounded revalidation of the same "
            "target's base, merge-base, and head; exact equality with "
            "`snapshot_tuple`",
            self.contract,
        )
        self.assertIn(
            "Tuple drift is immediately `NONE / ABORTED / SNAPSHOT_CHANGED`; do not "
            "publish, reanalyse, or restart automatically.",
            self.contract,
        )

    def test_matrix_has_exactly_the_five_closed_rows(self) -> None:
        rows = [
            line.split("|")[1].strip()
            for line in self.contract.splitlines()
            if line.startswith("| ") and not line.startswith("| ---")
        ]

        self.assertEqual(
            rows,
            [
                "Validation row",
                "Authority",
                "Snapshot",
                "Decision",
                "Prepublication",
                "Readback",
            ],
        )
        self.assertEqual(self.contract.count("## Closed validation matrix"), 1)

    def test_closed_matrix_branch_probes(self) -> None:
        probes = {
            "Authority": (
                "NONE / BLOCKED / AUTHORITY_UNVERIFIED",
                "NONE / UNCERTAIN / AUTHORITY_UNVERIFIABLE",
            ),
            "Snapshot": (
                "NONE / BLOCKED / SNAPSHOT_INVALID",
                "NONE / UNCERTAIN / SNAPSHOT_UNVERIFIABLE",
            ),
            "Decision": (
                "NONE / NO_OP / NONE",
                "NONE / BLOCKED / DECISION_INVALID",
                "NONE / UNCERTAIN / DECISION_UNVERIFIABLE",
            ),
            "Prepublication": (
                "NONE / ABORTED / SNAPSHOT_CHANGED",
                "NONE / NO_OP / NONE",
                "NONE / UNCERTAIN / PREPUBLICATION_UNVERIFIABLE",
            ),
            "Readback": (
                "PUBLISHED / CONFIRMED / EXACT_MATCH",
                "one byte-identical retry",
                "PUBLISHED / UNCERTAIN / READBACK_UNRESOLVED",
            ),
        }
        rows = {
            line.split("|")[1].strip(): line
            for line in self.contract.splitlines()
            if line.startswith("| ") and not line.startswith("| ---")
        }

        for row, expected_fragments in probes.items():
            with self.subTest(row=row):
                self.assertIn("Missing", rows[row])
                self.assertIn("unverifiable", rows[row])
                for fragment in expected_fragments:
                    self.assertIn(fragment, rows[row])

    def test_readback_and_retry_probes_are_exact_and_fail_closed(self) -> None:
        self.assertIn(
            "(fingerprint, path, side, start_anchor, end_anchor, normalized_body)",
            self.contract,
        )
        self.assertIn("order-independent multisets", self.contract)
        self.assertIn("Missing, duplicate, or extra inline comments", self.contract)
        self.assertIn("one and only one byte-identical retry", self.contract)
        self.assertIn(
            "A partial result, any conflict,\n"
            "an unknown result, or incomplete readback is `uncertain` and forbids retries.",
            self.contract,
        )

    def test_timeout_interruption_and_mutation_boundaries_fail_closed(self) -> None:
        self.assertIn("bounded-deadline `gh` REST or GraphQL calls", self.contract)
        self.assertIn(
            "Before publication it produces\n"
            "no write and an `uncertain` terminal result",
            self.contract,
        )
        self.assertIn("after a request might have been\nsent", self.contract)
        self.assertIn("Perform static review only.", self.contract)
        self.assertIn("Never check out the target or execute target code", self.contract)
        self.assertIn("only permitted GitHub mutation is one immutable GitHub review request", self.contract)
        self.assertIn("Unresolved review threads may be fetched only as read-only evidence", self.contract)
        self.assertRegex(
            self.contract,
            r"A\s+finding that cannot be anchored must be included in full in the final "
            r"review\s+body",
        )

    def test_validation_is_author_time_and_contract_owned(self) -> None:
        self.assertIn("sole normative contract source identifier", self.contract)
        self.assertIn("## Author-time repository validation", self.contract)
        self.assertRegex(
            self.contract,
            r"Do not use a live GitHub\s+mutation as validation\.",
        )
        self.assertNotIn("## Runtime Read-only validation oracle", self.contract)
        self.assertNotRegex(self.contract, r"(?im)^## .*runtime.*validation oracle")


if __name__ == "__main__":
    unittest.main()
