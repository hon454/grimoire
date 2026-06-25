from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins" / "archmage" / "hooks" / "resolve_grimoire_config.py"


spec = importlib.util.spec_from_file_location("resolve_grimoire_config", SCRIPT)
assert spec is not None
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def empty_runner(command: Sequence[str]) -> Optional[str]:
    return None


class ResolveGrimoireConfigTests(unittest.TestCase):
    def test_normalizes_locale_tags(self) -> None:
        self.assertEqual("ko-KR", module.normalize_locale("ko_KR.UTF-8"))
        self.assertEqual("zh-Hant-TW", module.normalize_locale("zh_Hant_TW"))
        self.assertIsNone(module.normalize_locale("C.UTF-8"))
        self.assertIsNone(module.normalize_locale("POSIX"))

    def test_project_config_overlays_user_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            user_config = tmp / "user.toml"
            project_config = tmp / "project.toml"
            cache_path = tmp / "cache" / "config.toml"
            user_config.write_text(
                "\n".join(
                    [
                        "schema_version = 1",
                        "[output]",
                        'locale = "ja-JP"',
                        "[tracker]",
                        'primary = "github"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            project_config.write_text(
                "\n".join(
                    [
                        "schema_version = 1",
                        "[output]",
                        'locale = "ko-KR"',
                        "[tracker]",
                        'primary = "linear"',
                        "[tracker.linear]",
                        'team_identifier = "ENG"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = module.resolve_config(
                cwd=tmp,
                user_config=user_config,
                project_config=project_config,
                cache_path=cache_path,
                environ={"LANG": "fr_FR.UTF-8"},
                system_name="Linux",
                runner=empty_runner,
                generated_at="2026-01-01T00:00:00+00:00",
            )

            self.assertEqual("ko-KR", result["output"]["locale"])
            self.assertEqual("config:project", result["output"]["locale_source"])
            self.assertEqual("linear", result["tracker"]["primary"])
            self.assertEqual("ENG", result["tracker"]["linear"]["team_identifier"])

    def test_missing_user_locale_bootstraps_os_preference(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            user_config = tmp / "user.toml"
            user_config.write_text(
                "schema_version = 1\n[tracker]\nprimary = \"github\"\n",
                encoding="utf-8",
            )

            result = module.resolve_config(
                cwd=tmp,
                user_config=user_config,
                project_config=tmp / "missing.toml",
                cache_path=tmp / "cache.toml",
                bootstrap_user_config=True,
                environ={"LC_ALL": "C", "LC_MESSAGES": "POSIX", "LANG": "fr_FR.UTF-8"},
                system_name="Linux",
                runner=empty_runner,
            )

            self.assertEqual("fr-FR", result["output"]["locale"])
            self.assertEqual("config:user", result["output"]["locale_source"])
            self.assertIn('locale = "fr-FR"', user_config.read_text(encoding="utf-8"))

    def test_bootstrap_creates_missing_user_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            user_config = tmp / "user" / "config.toml"

            result = module.resolve_config(
                cwd=tmp,
                user_config=user_config,
                project_config=tmp / "missing.toml",
                cache_path=tmp / "cache.toml",
                bootstrap_user_config=True,
                environ={"LANG": "ja_JP.UTF-8"},
                system_name="Linux",
                runner=empty_runner,
            )

            self.assertEqual("ja-JP", result["output"]["locale"])
            self.assertEqual("config:user", result["output"]["locale_source"])
            self.assertTrue(user_config.exists())
            text = user_config.read_text(encoding="utf-8")
            self.assertIn("schema_version = 1", text)
            self.assertIn('locale = "ja-JP"', text)

    def test_auto_locale_value_is_not_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            user_config = tmp / "config.toml"
            user_config.write_text(
                "schema_version = 1\n[output]\nlocale = \"auto\"\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--cwd",
                    str(tmp),
                    "--user-config",
                    str(user_config),
                    "--project-config",
                    str(tmp / "missing.toml"),
                    "--strict",
                ],
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(2, result.returncode)
            self.assertIn("output.locale must be a valid locale tag", result.stderr)

    def test_valid_explicit_locale_tag_overrides_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            user_config = tmp / "config.toml"
            user_config.write_text(
                "schema_version = 1\n[output]\nlocale = \"ja-JP\"\n",
                encoding="utf-8",
            )

            result = module.resolve_config(
                cwd=tmp,
                user_config=user_config,
                project_config=tmp / "missing.toml",
                cache_path=tmp / "cache.toml",
                explicit_locale="ko-kr",
                environ={"LANG": "fr_FR.UTF-8"},
                system_name="Linux",
                runner=empty_runner,
            )

            self.assertEqual("ko-KR", result["output"]["locale"])
            self.assertEqual("explicit", result["output"]["locale_source"])
            self.assertEqual([], result.get("errors", []))

    def test_invalid_explicit_locale_falls_back_to_os_preference(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            result = module.resolve_config(
                cwd=tmp,
                user_config=tmp / "missing-user.toml",
                project_config=tmp / "missing-project.toml",
                cache_path=tmp / "cache.toml",
                explicit_locale="Please answer in Korean",
                environ={"LANG": "fr_FR.UTF-8"},
                system_name="Linux",
                runner=empty_runner,
            )

            self.assertEqual("fr-FR", result["output"]["locale"])
            self.assertEqual("env:LANG", result["output"]["locale_source"])
            self.assertEqual([], result.get("errors", []))

    def test_cli_writes_cache_as_toml(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            user_config = tmp / "config.toml"
            cache_path = tmp / "session.toml"
            user_config.write_text(
                "schema_version = 1\n[output]\nlocale = \"ko-KR\"\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--cwd",
                    str(tmp),
                    "--user-config",
                    str(user_config),
                    "--project-config",
                    str(tmp / "missing.toml"),
                    "--cache-path",
                    str(cache_path),
                    "--cache",
                    "--format",
                    "json",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            payload = json.loads(result.stdout)
            self.assertEqual("ko-KR", payload["output"]["locale"])
            self.assertTrue(cache_path.exists())
            cache = cache_path.read_text(encoding="utf-8")
            self.assertIn("[output]", cache)
            self.assertIn('locale = "ko-KR"', cache)

    def test_strict_rejects_invalid_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            user_config = tmp / "config.toml"
            user_config.write_text(
                "schema_version = 1\n[tracker]\nprimary = \"jira\"\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--cwd",
                    str(tmp),
                    "--user-config",
                    str(user_config),
                    "--project-config",
                    str(tmp / "missing.toml"),
                    "--strict",
                ],
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(2, result.returncode)
            self.assertIn("tracker.primary", result.stderr)

    def test_linear_team_id_is_not_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            user_config = tmp / "config.toml"
            user_config.write_text(
                "\n".join(
                    [
                        "schema_version = 1",
                        "[tracker.linear]",
                        'team_id = "9cfb482a-81e3-4154-b5b9-2c805e70a02d"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--cwd",
                    str(tmp),
                    "--user-config",
                    str(user_config),
                    "--project-config",
                    str(tmp / "missing.toml"),
                    "--strict",
                ],
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(2, result.returncode)
            self.assertIn("tracker.linear.team_id is not supported", result.stderr)

    def test_issue_patterns_and_github_repo_are_not_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            user_config = tmp / "config.toml"
            user_config.write_text(
                "\n".join(
                    [
                        "schema_version = 1",
                        "[tracker]",
                        'issue_patterns = ["#\\\\d+"]',
                        "[tracker.github]",
                        'repo = "{owner}/{repo}"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--cwd",
                    str(tmp),
                    "--user-config",
                    str(user_config),
                    "--project-config",
                    str(tmp / "missing.toml"),
                    "--strict",
                ],
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(2, result.returncode)
            self.assertIn("tracker.issue_patterns is not supported", result.stderr)
            self.assertIn("tracker.github is not supported", result.stderr)


if __name__ == "__main__":
    unittest.main()
