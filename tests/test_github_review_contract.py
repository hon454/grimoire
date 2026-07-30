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
            "- `comparison_base_sha`: exact commit GitHub PR Files uses as the "
            "old side of\n"
            "  its changed-file inventory and anchors.\n"
            "- `head_sha`: PR head commit SHA.\n"
            "- `snapshot_tuple`:\n"
            "  `(base_sha, merge_base_sha, comparison_base_sha, head_sha)`.",
            self.contract,
        )
        self.assertIn(
            "Compute `contract_sha256` as lowercase hexadecimal SHA-256 of the "
            "exact bytes of\n"
            "this file. Do not include `SKILL.md`, `agents/openai.yaml`, user "
            "prose, PR data,\n"
            "paths, or sidecar changes. Compute `review_key` as lowercase "
            "hexadecimal\n"
            "SHA-256 of the exact UTF-8 bytes formed by concatenating:",
            self.contract,
        )
        self.assertIn(
            "```\n"
            "contract_source_identifier=github-review-contract/v1<LF>\n"
            "contract_sha256=<lowercase hexadecimal contract_sha256><LF>\n"
            "host=<verified GitHub host><LF>\n"
            "principal_id=<authenticated principal node ID><LF>\n"
            "repository_id=<repository node ID><LF>\n"
            "pull_request_id=<pull request node ID><LF>\n"
            "base_sha=<base_sha><LF>\n"
            "merge_base_sha=<merge_base_sha><LF>\n"
            "comparison_base_sha=<comparison_base_sha><LF>\n"
            "head_sha=<head_sha><LF>\n"
            "```",
            self.contract,
        )
        self.assertIn(
            """\
Each displayed `<LF>` is exactly one byte `0x0a`, not the four literal
characters, and the final `head_sha` field includes that trailing LF. Add no
other whitespace, CR, separator, or encoding transformation. This fixed vector
must produce the shown result:

```
contract_source_identifier=github-review-contract/v1
contract_sha256=0000000000000000000000000000000000000000000000000000000000000000
host=github.com
principal_id=U_1
repository_id=R_2
pull_request_id=PR_3
base_sha=1111111111111111111111111111111111111111
merge_base_sha=2222222222222222222222222222222222222222
comparison_base_sha=3333333333333333333333333333333333333333
head_sha=4444444444444444444444444444444444444444
review_key=cd88cf1e826606ba34a5d64888a39489e79ff9833b243189ed7a4e4ec053dcf3
```
""",
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
        matrix = self.contract.split("## Closed validation matrix\n", 1)[1].split(
            "\nA later row never repairs an earlier failure.",
            1,
        )[0]
        rows = [
            line.split("|")[1].strip()
            for line in matrix.splitlines()
            if line.startswith("| ")
            and not line.startswith(("| Row |", "| --- |"))
        ]

        self.assertEqual(
            rows,
            ["Authority", "Snapshot", "Decision", "Prepublication", "Readback"],
        )
        self.assertIn(
            "| Prepublication | Immediate tuple revalidation; zero exact plan "
            "matches; for either strong event, fresh author, permission, "
            "queue-absence, check-source, required-check, and current-check "
            "evidence; for `APPROVE`, fresh resolved-thread evidence. | Tuple "
            "drift: `NONE / ABORTED / SNAPSHOT_CHANGED`. Decision evidence "
            "drift: `NONE / ABORTED / DECISION_EVIDENCE_CHANGED`. One exact "
            "match: `NONE / NO_OP / NONE`. Missing or multiple-match evidence: "
            "`NONE / UNCERTAIN / PREPUBLICATION_UNVERIFIABLE`. |",
            self.contract.splitlines(),
        )
        self.assertIn(
            "| Decision | Complete review-content evidence; deterministic "
            "event; immutable plan; complete exact candidate reconciliation; "
            "for a selected strong event, complete applicable strong-event "
            "evidence. | Forbidden plan, anchor, event, or target: `NONE / "
            "BLOCKED / DECISION_INVALID`. Missing, conflicting, or incomplete "
            "review-content evidence, or missing evidence for a selected "
            "strong event: `NONE / UNCERTAIN / DECISION_UNVERIFIABLE`. |",
            self.contract.splitlines(),
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
            "Non-author review has any `P0`, `P1`, or `P2` finding | "
            "`REQUEST_CHANGES`",
            self.contract,
        )
        self.assertIn(
            "Review has only `P3` or `NIT` findings | `COMMENT`",
            self.contract,
        )
        self.assertIn(
            "Review has no findings, all existing threads are resolved, and "
            "checks are approval eligible | `APPROVE`",
            self.contract,
        )
        self.assertIn("check runs with `filter=latest`", self.contract)
        self.assertIn(
            "latest commit status per\ncase-insensitive context",
            self.contract,
        )
        for guard in (
            "`check_source_sha`",
            "complete configuration evidence proves no checks are required",
            "evidence needed by a stronger event is missing or ambiguous | "
            "`COMMENT`",
            "`APPROVE` and `REQUEST_CHANGES` require complete, unambiguous evidence",
            "SNAPSHOT_CHANGED_AFTER_PUBLICATION",
        ):
            with self.subTest(guard=guard):
                self.assertIn(guard, self.contract)

    def test_review_evidence_and_bounded_fallback_are_exact(self) -> None:
        self.assertIn(
            """\
Use exactly two evidence sets:

- Review-content evidence, required for any publication: complete Authority and
  Snapshot rows, complete changed-file inventory and contents, frozen findings,
  body, and anchors, exact candidate reconciliation, and immediate tuple
  revalidation. Missing or ambiguous review-content evidence is a no-write
  `NONE / UNCERTAIN` terminal from the decisive validation row; do not publish.
- Strong-event evidence, required only for `APPROVE` or `REQUEST_CHANGES`:
  complete author relation, selected-event permission, proof that the PR is not
  queued, check source, required-check configuration, and current check results;
  `APPROVE` also requires complete resolved-thread evidence. When review-content
  evidence is complete but strong-event evidence is missing or ambiguous, use
  `COMMENT`.
""",
            self.contract,
        )
        self.assertIn(
            """\
The changed-file inventory is complete only when its unique entry count equals
the PR's `changed_files` and every page is complete while `snapshot_tuple`
remains current. A successful response or pagination end alone does not prove
completeness across the REST 3,000-file or compare 300-file cap. Do not rebuild
an over-cap inventory by traversing full Git trees. Prove
`comparison_base_sha` is the old side GitHub PR Files actually used; never
substitute a graph merge base or compare-page merge base. Bind inventory,
anchors, and fallback to `comparison_base_sha` and `head_sha`. When the inventory
is complete but a known entry has a missing or truncated patch, fetch its exact
comparison-base/head blobs, text-or-binary evidence, and Git tree mode and
object type at both commits. If any comparison-base, inventory, fallback blob,
mode, type, rename, deletion, submodule, or binary evidence remains incomplete
or ambiguous, review-content evidence is incomplete.
""",
            self.contract,
        )

    def test_required_checks_join_source_and_kind_exactly(self) -> None:
        self.assertIn(
            """\
Build current required-result records keyed by
`(casefold(context), app_id/integration_id, check kind)`, distinguishing check
runs from commit statuses. Preserve an explicit API-defined any-source setting;
never infer it from missing or unreadable source evidence. The required-result
join is complete only when every configured required context and expected
source has at least one matching current record. Retain every matching check
kind; when both a check run and commit status have the required context, both
must succeed. Optional results and same-context results from a nonmatching
source never satisfy the requirement.
""",
            self.contract,
        )
        rows = (
            "| Any missing required result, source mismatch, unverifiable "
            "source or kind, other conclusion, unidentified check source, "
            "incomplete configuration or pagination, or unverifiable result | "
            "`FAIL_OR_UNVERIFIABLE` | No |",
            "| Otherwise, any `queued`, `pending`, `requested`, `waiting`, "
            "`expected`, or `in_progress` result | `PENDING` | No |",
            "| Otherwise, no reported checks, and complete configuration "
            "evidence proves no checks are required | `NOT_CONFIGURED` | Yes |",
            "| Otherwise, the required-result join is complete, at least one "
            "current result exists, and every current result completed as "
            "`success`, `skipped`, or `neutral` | `PASS` | Yes |",
        )
        self.assertIn(
            "Classify that current evidence by evaluating these rows in order "
            "and selecting\nthe first match:",
            self.contract,
        )
        for row in rows:
            with self.subTest(row=row):
                self.assertIn(row, self.contract.splitlines())

    def test_finding_rubric_and_event_rows_are_exact(self) -> None:
        self.assertIn(
            """\
- `P0`: an immediately actionable critical security, data-loss, or
  service-outage defect.
- `P1`: a major defect with high impact or high likelihood.
- `P2`: a correctness, security, or contract defect that must be fixed before
  merge.
- `P3`: a real but limited-impact defect that can be fixed after merge.
- `NIT`: an optional style, readability, or wording improvement, not a defect.

`P0` through `P2` are blocking; `P3` and `NIT` are non-blocking. The `P2`/`P3`
boundary is whether the defect must be fixed before merge. The `P3`/`NIT`
boundary is whether an actual behavioral defect exists. When the `P2`/`P3`
boundary cannot be resolved, do not use it to select a strong event; use
`COMMENT`.
""",
            self.contract,
        )
        event_rows = [
            line
            for line in self.contract.splitlines()
            if line.startswith("| ") and line.endswith((" | `COMMENT` |", " | `REQUEST_CHANGES` |", " | `APPROVE` |"))
        ]
        self.assertEqual(
            event_rows,
            [
                "| Review-content evidence is complete, but evidence needed by "
                "a stronger event is missing or ambiguous | `COMMENT` |",
                "| Authenticated principal is the PR author | `COMMENT` |",
                "| The PR is queued, or complete evidence that it is not queued "
                "is unavailable | `COMMENT` |",
                "| The P2/P3 boundary of any finding is unresolved | `COMMENT` |",
                "| Non-author review has any `P0`, `P1`, or `P2` finding | "
                "`REQUEST_CHANGES` |",
                "| Review has only `P3` or `NIT` findings | `COMMENT` |",
                "| Review has no findings, all existing threads are resolved, "
                "and checks are approval eligible | `APPROVE` |",
                "| Otherwise | `COMMENT` |",
            ],
        )
        self.assertIn(
            "Do not track `merge_group` SHA or monitor queue\nchanges.",
            self.contract,
        )

    def test_static_readback_canonicalization_is_present(self) -> None:
        self.assertIn(
            """\
Use REST anchors:

- Plan end anchor: `(side, line)`.
- Plan start anchor: `(start_side, start_line)` for a multi-line comment;
  otherwise the end anchor.
- Observed end anchor: `(side, original_line)`.
- Observed start anchor: `(start_side, original_start_line)` when present;
  otherwise the observed end anchor.
""",
            self.contract,
        )
        self.assertIn("order-independent multisets", self.contract)
        self.assertIn("Nonmatching markers never suppress", self.contract)
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
        self.assertIn(
            "Do not use a live GitHub mutation as validation.",
            self.contract.splitlines(),
        )


if __name__ == "__main__":
    unittest.main()
