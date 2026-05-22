from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def markdown_section(content: str, heading: str) -> str:
    marker = f"\n## {heading}\n"
    start = content.index(marker) + 1
    next_heading = content.find("\n## ", start + len(marker))
    end = next_heading if next_heading != -1 else len(content)
    return content[start:end].strip()


class RepositoryDocsTests(unittest.TestCase):
    def test_readmes_list_shared_book_asset_directory(self) -> None:
        for readme in ("README.md", "README.ko.md"):
            with self.subTest(readme=readme):
                content = (ROOT / readme).read_text()

                self.assertIn("`assets/book-of/`", content)

    def test_work_briefing_uses_documented_language_baseline(self) -> None:
        maintenance = (ROOT / "docs" / "maintaining-grimoire.md").read_text()
        work_briefing = (
            ROOT / "plugins" / "book-of-engineering" / "skills" / "work-briefing" / "SKILL.md"
        ).read_text()
        baseline_match = re.search(r"```markdown\n(## Language\n.*?)\n```", maintenance, re.S)

        self.assertIsNotNone(baseline_match)
        assert baseline_match is not None
        self.assertEqual(baseline_match.group(1).strip(), markdown_section(work_briefing, "Language"))
        self.assertLess(work_briefing.index("## Language"), work_briefing.index("## Invocation"))

    def test_work_briefing_allows_language_check_before_start_message(self) -> None:
        content = (
            ROOT / "plugins" / "book-of-engineering" / "skills" / "work-briefing" / "SKILL.md"
        ).read_text()

        self.assertIn("read-only command to check the host OS preferred language", content)
        self.assertIn("when `Language` has no substantive user-language signal", content)


if __name__ == "__main__":
    unittest.main()
