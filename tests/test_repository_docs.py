from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RepositoryDocsTests(unittest.TestCase):
    def test_readmes_list_shared_book_asset_directory(self) -> None:
        for readme in ("README.md", "README.ko.md"):
            with self.subTest(readme=readme):
                content = (ROOT / readme).read_text()

                self.assertIn("`assets/book-of/`", content)

    def test_work_briefing_language_selection_ignores_invocation_boilerplate(self) -> None:
        content = (
            ROOT / "plugins" / "book-of-engineering" / "skills" / "work-briefing" / "SKILL.md"
        ).read_text()

        self.assertIn("substantive natural-language user messages", content)
        self.assertIn("inspect the host locale or preferred OS languages", content)
        self.assertIn("Language-signal exclusions:", content)
        self.assertIn("- skill triggers, invocation boilerplate, and default prompts", content)
        self.assertIn("Output language boundaries:", content)
        self.assertIn("- Write narrative prose in the selected language.", content)
        self.assertNotIn("Keep section headings from `Briefing Structure` in English", content)
        self.assertIn(
            "- Do not translate commands, code, identifiers, branch names, commit hashes, and issue IDs.",
            content,
        )


if __name__ == "__main__":
    unittest.main()
