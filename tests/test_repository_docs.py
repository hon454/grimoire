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

        self.assertIn(
            "Before the start message, the only allowed inspection is a read-only command "
            "to check the host locale or preferred OS languages when `Briefing Language` "
            "has no substantive user-language signal.",
            content,
        )
        self.assertIn("substantive natural-language user messages", content)
        self.assertIn("inspect the host locale or preferred OS languages", content)
        self.assertIn("Language-signal exclusions:", content)
        for exclusion in (
            "- skill triggers, invocation boilerplate, and default prompts",
            "- assistant text, tool output, quoted source text, and section templates",
            "- commands, identifiers, paths, and URLs",
        ):
            self.assertIn(exclusion, content)

        self.assertIn("Output language boundaries:", content)
        self.assertNotIn("Keep section headings from `Briefing Structure` in English", content)
        for boundary in (
            "- Write narrative prose in the selected language.",
            "- Do not translate commands, code, identifiers, branch names, commit hashes, and issue IDs.",
            "- Do not translate file paths, URLs, package names, tool names, and API names.",
            "- Do not translate quoted source text, error text, log excerpts, and terminal output.",
        ):
            self.assertIn(boundary, content)


if __name__ == "__main__":
    unittest.main()
