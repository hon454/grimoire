from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RepositoryDocsTests(unittest.TestCase):
    def test_readmes_describe_single_grimoire_plugin(self) -> None:
        for readme in ("README.md", "README.ko.md"):
            with self.subTest(readme=readme):
                content = (ROOT / readme).read_text()

                self.assertIn("`plugins/grimoire/`", content)
                self.assertNotIn("`plugins/archmage/`", content)
                self.assertNotIn("`plugins/book-of-engineering/`", content)
                self.assertNotIn("`plugins/book-of-git/`", content)


if __name__ == "__main__":
    unittest.main()
