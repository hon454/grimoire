from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "plugins"
    / "grimoire"
    / "skills"
    / "magical-translation"
    / "scripts"
    / "resolve_translation_locale.py"
)


class ResolveTranslationLocaleTests(unittest.TestCase):
    def run_script(
        self,
        *args: str,
        cwd: Path,
        grimoire_home: Path,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["GRIMOIRE_HOME"] = str(grimoire_home)
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--cwd", str(cwd), *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

    def test_reads_locale_from_project_session_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            repo = tmp / "repo"
            repo.mkdir()
            (repo / ".git").mkdir()
            grimoire_home = tmp / "grimoire"
            digest = hashlib.sha256(str(repo.resolve()).encode("utf-8")).hexdigest()[:12]
            cache_path = grimoire_home / "cache" / "sessions" / digest / "config.toml"
            cache_path.parent.mkdir(parents=True)
            cache_path.write_text(
                '\n'.join(
                    [
                        'schema_version = 1',
                        '',
                        '[output]',
                        'configured_locale = "ko-KR"',
                        'locale = "ko-KR"',
                        'locale_source = "config:user"',
                    ]
                )
                + '\n',
                encoding="utf-8",
            )

            result = self.run_script("--format", "json", cwd=repo, grimoire_home=grimoire_home)

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("ko-KR", payload["locale"])
            self.assertEqual("config:user", payload["locale_source"])
            self.assertEqual(str(cache_path), payload["cache_path"])
            self.assertEqual(str(repo.resolve()), payload["project_root"])

    def test_fails_when_cache_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            repo = tmp / "repo"
            repo.mkdir()
            (repo / ".git").mkdir()

            result = self.run_script("--format", "json", cwd=repo, grimoire_home=tmp / "grimoire")

            self.assertNotEqual(0, result.returncode)
            self.assertIn("session config cache not found", result.stderr)


if __name__ == "__main__":
    unittest.main()
