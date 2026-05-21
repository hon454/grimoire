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


if __name__ == "__main__":
    unittest.main()
