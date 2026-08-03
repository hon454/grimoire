from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "plugins" / "grimoire" / "skills" / "magical-review-response"
SKILL = SKILL_DIR / "SKILL.md"
GUIDE = SKILL_DIR / "guides" / "github.md"
SCRIPT = SKILL_DIR / "scripts" / "review_response_state.py"
SIDECAR = SKILL_DIR / "agents" / "openai.yaml"

SPEC = importlib.util.spec_from_file_location("review_response_state", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
STATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STATE)


def checkpoint(*, phase="completed", workflow=None):
    return {
        "schema_version": 1,
        "revision": 0,
        "platform": "github",
        "host": "github.com",
        "repository": {
            "id": 123,
            "owner": "CINEV",
            "name": "shotloom",
            "url": "https://github.com/CINEV/shotloom",
        },
        "pull_request": {
            "id": 8740,
            "number": 874,
            "url": "https://github.com/CINEV/shotloom/pull/874",
            "head_sha": "a" * 40,
            "state": "OPEN",
        },
        "phase": phase,
        "source_items": [
            {
                "id": "PRRC_kwDOExample",
                "kind": "review_comment",
                "fingerprint": "b" * 64,
                "state": "unresolved",
                "decision_required": True,
                "decision_id": "D1",
            }
        ],
        "decisions": [
            {
                "id": "D1",
                "source_ids": ["PRRC_kwDOExample"],
                "type": "fix",
                "status": "decided",
                "choice": "Apply the smallest contract fix.",
                "implementation_status": "completed",
                "verification_status": "completed",
                "reply_status": "completed",
                "resolve_action": "not_applicable",
            }
        ],
        "workflow_status": workflow
        or {
            "implementation": "completed",
            "verification": "completed",
            "reply": "completed",
            "resolve": "not_applicable",
            "remote_write": "completed",
        },
        "updated_at": "2026-08-03T00:00:00+00:00",
    }


def open_pull(number=874, repository_id=123):
    return {
        "number": number,
        "state": "open",
        "merged_at": None,
        "base": {"repo": {"id": repository_id}},
    }


def closed_pull(number=874, repository_id=123):
    return {
        "number": number,
        "state": "closed",
        "merged_at": None,
        "base": {"repo": {"id": repository_id}},
    }


class FakeApi:
    def __init__(self, root=None, mutate_on_exact=False):
        self.root = root
        self.mutate_on_exact = mutate_on_exact
        self.fail_exact = False
        self.open_pages = [[]]
        self.repository_id = 123
        self.fail = False

    def __call__(self, host, endpoint, paginate):
        if self.fail:
            raise STATE.StateError("unavailable")
        if endpoint == "repos/CINEV/shotloom":
            return {"id": self.repository_id}
        if endpoint == "repos/CINEV/shotloom/pulls?state=open&per_page=100":
            self.assert_paginate(paginate)
            return self.open_pages
        if endpoint == "repos/CINEV/shotloom/pulls/874":
            if self.fail_exact:
                raise STATE.StateError("exact PR lookup unavailable")
            if self.mutate_on_exact:
                changed = checkpoint()
                changed["decisions"][0]["choice"] = "A newer decision"
                STATE.write_checkpoint(self.root, changed)
            return closed_pull(repository_id=self.repository_id)
        raise AssertionError(f"unexpected endpoint: {endpoint}")

    @staticmethod
    def assert_paginate(paginate):
        if not paginate:
            raise AssertionError("OPEN PR collection must paginate")


class MagicalReviewResponseContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = SKILL.read_text(encoding="utf-8")
        cls.guide = GUIDE.read_text(encoding="utf-8")

    def test_initial_output_has_orientation_translation_and_interview_in_order(self):
        labels = ("`PR orientation`", "`Full review translation`", "the first decision interview")
        positions = [self.skill.index(label) for label in labels]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("A horizontal rule, then `Full review translation`", self.skill)
        self.assertIn("A horizontal rule, then the first decision interview", self.skill)
        self.assertIn("stable platform item ID when available", self.skill)
        self.assertIn("Do not include interpretation,\n      takeaway, decisions, or recommendations", self.skill)

    def test_decision_interview_separates_recommendations_and_requires_evidence(self):
        self.assertIn("**Reviewer recommendation:**", self.skill)
        self.assertIn("**Agent recommendation:**", self.skill)
        self.assertIn("state the verified repository path, contract, test, or observed runtime", self.skill)
        self.assertIn("Do not interview decision-free documentation fixes", self.skill)
        self.assertIn("question must ask only about the one current decision", self.skill)

    def test_checkpoint_scope_and_non_goals_are_explicit(self):
        self.assertIn("Keep pasted or copied review text in conversation\nmemory only", self.skill)
        self.assertIn("not store reviewer bodies, translations, diffs, chat or tool logs", self.skill)
        self.assertIn("Writes are last-writer-wins", self.guide)
        self.assertIn("There is no remote-write crash protocol", self.guide)
        self.assertIn("Unknown or malformed schema is not readable, overwriteable, or deletable", self.guide)

    def test_cleanup_contract_is_fail_closed_and_immediate(self):
        self.assertIn("Run `cleanup` once near the start", self.guide)
        self.assertIn("The helper deletes no trash or recovery copy", self.guide)
        for guard in (
            "complete `state=open` PR list",
            "An exact follow-up query",
            "`phase: completed`",
            "immutable repository ID",
            "acquiring the file-specific lock",
            "regular non-symlink JSON file",
            "401, 403, 404,\n429",
        ):
            with self.subTest(guard=guard):
                self.assertIn(guard, self.guide)

    def test_sidecar_still_matches_skill_scope(self):
        sidecar = SIDECAR.read_text(encoding="utf-8")
        self.assertIn('display_name: "Magical Review Response"', sidecar)
        self.assertIn("translate and handle this PR review feedback end to end", sidecar)

    def test_script_uses_python_39_compatible_type_syntax(self):
        self.assertNotIn(" | None", SCRIPT.read_text(encoding="utf-8"))


class ReviewResponseStateTests(unittest.TestCase):
    def test_write_and_read_increment_revision_without_temp_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initial = checkpoint()
            initial.pop("revision")
            initial.pop("updated_at")
            path, first = STATE.write_checkpoint(root, initial)
            _, second = STATE.write_checkpoint(root, checkpoint())

            self.assertEqual(1, first["revision"])
            self.assertEqual(2, second["revision"])
            self.assertEqual(second, STATE.read_checkpoint(root, "github.com", 123, 874))
            self.assertEqual([], list(path.parent.glob("*.tmp")))

    def test_write_rejects_raw_or_unknown_fields_and_preserves_unknown_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = checkpoint()
            raw["review_body"] = "must not persist"
            with self.assertRaises(STATE.StateError):
                STATE.write_checkpoint(root, raw)

            escaped = checkpoint()
            escaped["host"] = ".."
            with self.assertRaises(STATE.StateError):
                STATE.write_checkpoint(root, escaped)

            path = root / "github.com" / "123" / "874.json"
            path.parent.mkdir(parents=True)
            path.write_text('{"schema_version": 99}\n', encoding="utf-8")
            with self.assertRaises(STATE.StateError):
                STATE.write_checkpoint(root, checkpoint())
            self.assertEqual('{"schema_version": 99}\n', path.read_text(encoding="utf-8"))

    def test_cleanup_deletes_only_completed_closed_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, _ = STATE.write_checkpoint(root, checkpoint())

            result = STATE.cleanup_checkpoints(root, FakeApi())

            self.assertFalse(path.exists())
            self.assertEqual([str(path)], result["deleted"])

    def test_cleanup_preserves_active_pr(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, _ = STATE.write_checkpoint(root, checkpoint())
            api = FakeApi()
            api.open_pages = [[open_pull()]]

            result = STATE.cleanup_checkpoints(root, api)

            self.assertTrue(path.exists())
            self.assertEqual([], result["deleted"])

    def test_cleanup_preserves_pending_checkpoint_without_querying(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pending = checkpoint()
            pending["workflow_status"]["reply"] = "pending"
            path, _ = STATE.write_checkpoint(root, pending)
            api = FakeApi()
            api.fail = True

            result = STATE.cleanup_checkpoints(root, api)

            self.assertTrue(path.exists())
            self.assertEqual([], result["skipped_repositories"])

    def test_cleanup_preserves_incomplete_or_failed_github_evidence(self):
        for mode in ("empty-pages", "query-failure", "repository-mismatch", "exact-failure"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path, _ = STATE.write_checkpoint(root, checkpoint())
                api = FakeApi()
                if mode == "empty-pages":
                    api.open_pages = []
                elif mode == "query-failure":
                    api.fail = True
                else:
                    api.repository_id = 999

                if mode == "exact-failure":
                    api.repository_id = 123
                    api.fail_exact = True

                result = STATE.cleanup_checkpoints(root, api)

                self.assertTrue(path.exists())
                self.assertEqual([], result["deleted"])
                if mode == "exact-failure":
                    self.assertEqual([], result["skipped_repositories"])
                else:
                    self.assertEqual(["github.com/CINEV/shotloom"], result["skipped_repositories"])

    def test_cleanup_preserves_invalid_schema_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            invalid = root / "github.com" / "123" / "874.json"
            invalid.parent.mkdir(parents=True)
            invalid.write_text('{"schema_version": 99}\n', encoding="utf-8")
            outside = root / "outside.json"
            outside.write_text("{}\n", encoding="utf-8")
            linked = root / "github.com" / "123" / "875.json"
            linked.symlink_to(outside)

            result = STATE.cleanup_checkpoints(root, FakeApi())

            self.assertTrue(invalid.exists())
            self.assertTrue(linked.is_symlink())
            self.assertEqual([], result["deleted"])

    def test_cleanup_rechecks_revision_after_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, _ = STATE.write_checkpoint(root, checkpoint())
            api = FakeApi(root=root, mutate_on_exact=True)

            result = STATE.cleanup_checkpoints(root, api)

            self.assertTrue(path.exists())
            self.assertEqual(2, STATE.read_checkpoint(root, "github.com", 123, 874)["revision"])
            self.assertEqual([], result["deleted"])

    @unittest.skipUnless(hasattr(STATE.os, "O_NOFOLLOW"), "requires no-follow file opens")
    def test_cleanup_preserves_checkpoint_when_lock_is_unsafe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, _ = STATE.write_checkpoint(root, checkpoint())
            lock = path.with_suffix(path.suffix + ".lock")
            lock.unlink()
            lock.symlink_to(path)

            result = STATE.cleanup_checkpoints(root, FakeApi())

            self.assertTrue(path.exists())
            self.assertEqual([], result["deleted"])


if __name__ == "__main__":
    unittest.main()
