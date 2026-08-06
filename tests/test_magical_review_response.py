from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
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


def checkpoint(*, phase="completed", remote_write_status="completed"):
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
            "state": "open",
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
        "remote_write_status": remote_write_status,
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

    def test_initial_output_has_orientation_and_translation_in_order(self):
        labels = ("`PR orientation`", "`Full review translation`")
        positions = [self.skill.index(label) for label in labels]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("A horizontal rule, then `Full review translation`", self.skill)
        self.assertIn("stable platform item ID when available", self.skill)
        self.assertIn("Do not include interpretation,\n      takeaway, decisions, or recommendations", self.skill)

    def test_first_response_branches_on_whether_decisions_exist(self):
        self.assertIn(
            "the first decision interview, when at least one independent decision",
            self.skill,
        )
        self.assertIn(
            "the consolidated response plan from step 8, when no independent",
            self.skill,
        )
        self.assertIn(
            "In either branch, do not implement until the consolidated response plan is\n"
            "   explicitly confirmed",
            self.skill,
        )

    def test_decision_interview_separates_recommendations_and_requires_evidence(self):
        self.assertIn("**Reviewer recommendation:**", self.skill)
        self.assertIn("**Agent recommendation:**", self.skill)
        self.assertIn("state the verified repository path, contract, test, or observed runtime", self.skill)
        self.assertIn("Do not interview decision-free documentation fixes", self.skill)
        self.assertIn("question must ask only about the one current decision", self.skill)

    def test_visual_decision_support_is_active_and_bounded(self):
        self.assertIn("actively assess whether a visual would materially", self.skill)
        self.assertIn("`$visualize:visualize`", self.skill)
        self.assertIn("Use Mermaid for verified static structure", self.skill)
        self.assertIn(
            "Place a decision visual after **Takeaway** and before **Decision needed**",
            self.skill,
        )
        self.assertIn("Do not include visuals\nin the full-translation phase", self.skill)
        self.assertIn("Visuals supplement, never replace", self.skill)

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
    def test_fingerprint_is_canonical_and_rejects_raw_text(self):
        payload = {
            "id": "PRRC_123",
            "updated_at": "2026-08-03T00:00:00Z",
            "body": "안녕하세요\nReview",
        }
        expected = "8fd1e632eaabe0a049b6d332eff280facb475a34807042dd29905520d7b0bc32"

        self.assertEqual(expected, STATE.source_fingerprint(payload))
        self.assertEqual(
            expected,
            STATE.source_fingerprint(dict(reversed(list(payload.items())))),
        )

        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "fingerprint"],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual({"fingerprint": expected}, json.loads(completed.stdout))

        rejected = subprocess.run(
            [sys.executable, str(SCRIPT), "fingerprint"],
            input="raw review body",
            text=True,
            capture_output=True,
        )
        self.assertEqual(2, rejected.returncode)

    def test_checkpoint_accepts_only_closed_enum_values(self):
        fields = (
            (("phase",), STATE.PHASES),
            (("pull_request", "state"), STATE.PULL_REQUEST_STATES),
            (("source_items", 0, "kind"), STATE.SOURCE_KINDS),
            (("source_items", 0, "state"), STATE.SOURCE_STATES),
            (("decisions", 0, "type"), STATE.DECISION_TYPES),
            (("decisions", 0, "status"), STATE.DECISION_STATUSES),
            (("decisions", 0, "implementation_status"), STATE.IMPLEMENTATION_STATUSES),
            (("decisions", 0, "verification_status"), STATE.VERIFICATION_STATUSES),
            (("decisions", 0, "reply_status"), STATE.REPLY_STATUSES),
            (("decisions", 0, "resolve_action"), STATE.RESOLVE_ACTIONS),
            (("remote_write_status",), STATE.REMOTE_WRITE_STATUSES),
        )
        for path, allowed in fields:
            for member in allowed:
                with self.subTest(path=path, member=member):
                    value = checkpoint()
                    target = value
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] = member
                    STATE.validate_checkpoint(value)
            with self.subTest(path=path, member="UNKNOWN"):
                value = checkpoint()
                target = value
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = "UNKNOWN"
                with self.assertRaises(STATE.StateError):
                    STATE.validate_checkpoint(value)

        for path, alias in (
            (("pull_request", "state"), "OPEN"),
            (("decisions", 0, "type"), "defer/reject"),
            (("decisions", 0, "resolve_action"), "auto-resolve"),
        ):
            with self.subTest(path=path, alias=alias):
                value = checkpoint()
                target = value
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = alias
                with self.assertRaises(STATE.StateError):
                    STATE.validate_checkpoint(value)

    def test_checkpoint_rejects_non_digest_fingerprint(self):
        for fingerprint in ("review body", "A" * 64, "a" * 63, "a" * 65):
            with self.subTest(fingerprint=fingerprint):
                value = checkpoint()
                value["source_items"][0]["fingerprint"] = fingerprint
                with self.assertRaises(STATE.StateError):
                    STATE.validate_checkpoint(value)

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
            pending["decisions"][0]["reply_status"] = "pending"
            path, _ = STATE.write_checkpoint(root, pending)
            api = FakeApi()
            api.fail = True

            result = STATE.cleanup_checkpoints(root, api)

            self.assertTrue(path.exists())
            self.assertEqual([], result["skipped_repositories"])

    def test_cleanup_preserves_each_pending_decision_status(self):
        for field in ("implementation_status", "verification_status", "reply_status"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                pending = checkpoint()
                pending["decisions"][0][field] = "pending"
                path, _ = STATE.write_checkpoint(root, pending)
                api = FakeApi()
                api.fail = True

                result = STATE.cleanup_checkpoints(root, api)

                self.assertTrue(path.exists())
                self.assertEqual([], result["skipped_repositories"])

    def test_cleanup_preserves_pending_remote_write_without_querying(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, _ = STATE.write_checkpoint(
                root,
                checkpoint(remote_write_status="pending"),
            )
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
