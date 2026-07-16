import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "plugins"
    / "grimoire"
    / "skills"
    / "handoff-to-main-task"
    / "scripts"
    / "handoff_guard.py"
)


def run_guard(action, payload):
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), action],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


class HandoffGuardTests(unittest.TestCase):
    def candidate(self, identifier="main-1", title="Skill design", preview="Design conclusion"):
        return {
            "id": identifier,
            "hostId": "local",
            "cwd": "/repo",
            "title": title,
            "preview": preview,
            "status": "idle",
            "updatedAt": 1784165208,
        }

    def resolve(self, candidates):
        return run_guard(
            "resolve",
            {
                "sourceThreadId": "side-source",
                "anchors": {
                    "cwd": "/repo",
                    "title": "Skill design",
                    "preview": "Design conclusion",
                    "hostId": "local",
                },
                "candidates": candidates,
            },
        )

    def test_resolve_returns_only_one_exact_candidate(self):
        result = self.resolve(
            [
                self.candidate(),
                self.candidate("other", title="Other design"),
                self.candidate("side-source"),
            ]
        )

        self.assertEqual(result["state"], "unique")
        self.assertEqual(result["target"]["id"], "main-1")

    def test_resolve_rejects_none_ambiguous_and_fuzzy_only(self):
        self.assertEqual(self.resolve([])["state"], "none")
        self.assertEqual(
            self.resolve([self.candidate(), self.candidate("main-2")])["state"],
            "ambiguous",
        )
        fuzzy = self.candidate(title="Skill design discussion")
        result = self.resolve([fuzzy])
        self.assertEqual(result["state"], "none")
        self.assertIn("title: mismatch", result["candidates"][0]["mismatches"])

    def test_resolve_normalizes_title_and_preview_but_not_cwd(self):
        normalized = self.candidate(title="ＳＫＩＬＬ   DESIGN", preview="Design\nconclusion")
        self.assertEqual(self.resolve([normalized])["state"], "unique")
        wrong_cwd = dict(normalized, cwd="/REPO")
        self.assertEqual(self.resolve([wrong_cwd])["state"], "none")

    def test_prepare_is_stable_across_line_endings_and_trailing_spaces(self):
        first = run_guard(
            "prepare",
            {"targetId": "main-1", "updatedAt": 100, "payload": "Decision\r\nNext  "},
        )
        second = run_guard(
            "prepare",
            {"targetId": "main-1", "updatedAt": 100, "payload": "Decision\nNext"},
        )

        self.assertEqual(first["handoffId"], second["handoffId"])
        self.assertTrue(first["message"].endswith(first["marker"]))

    def test_revalidate_blocks_duplicate(self):
        preview = run_guard(
            "prepare",
            {"targetId": "main-1", "updatedAt": 100, "payload": "Decision"},
        )
        result = run_guard(
            "revalidate",
            {
                "preview": preview,
                "target": {"id": "main-1", "updatedAt": 100},
                "recentMessages": ["older", preview["message"]],
            },
        )

        self.assertEqual(result, {"valid": False, "reason": "duplicate"})

    def test_revalidate_blocks_any_timestamp_change(self):
        preview = run_guard(
            "prepare",
            {"targetId": "main-1", "updatedAt": 100, "payload": "Decision"},
        )
        result = run_guard(
            "revalidate",
            {
                "preview": preview,
                "target": {"id": "main-1", "updatedAt": 101},
                "recentMessages": "",
            },
        )

        self.assertEqual(result, {"valid": False, "reason": "target-stale"})

    def test_revalidate_blocks_modified_exact_message(self):
        preview = run_guard(
            "prepare",
            {"targetId": "main-1", "updatedAt": 100, "payload": "Decision"},
        )
        preview["message"] = "Modified\n\n" + preview["marker"]
        result = run_guard(
            "revalidate",
            {
                "preview": preview,
                "target": {"id": "main-1", "updatedAt": 100},
                "recentMessages": "",
            },
        )

        self.assertEqual(result, {"valid": False, "reason": "payload-changed"})


class HandoffPackagingTests(unittest.TestCase):
    def test_two_user_facing_skills_share_one_non_skill_reference(self):
        plugin = ROOT / "plugins" / "grimoire"
        old_skill = plugin / "skills" / "handoff"
        reference = plugin / "references" / "handoff-composition.md"
        skill_names = ("create-handoff-prompt", "handoff-to-main-task")

        self.assertFalse(old_skill.exists())
        self.assertTrue(reference.is_file())
        self.assertFalse((reference.parent / "SKILL.md").exists())
        for name in skill_names:
            skill = plugin / "skills" / name
            self.assertIn(
                "../../references/handoff-composition.md",
                (skill / "SKILL.md").read_text(),
            )
            self.assertIn(
                "allow_implicit_invocation: false",
                (skill / "agents" / "openai.yaml").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
