from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "plugins"
    / "book-of-engineering"
    / "skills"
    / "issue-preflight"
    / "scripts"
    / "detect_os_preferred_locale.py"
)


spec = importlib.util.spec_from_file_location("detect_os_preferred_locale", SCRIPT)
assert spec is not None
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def empty_runner(command: Sequence[str]) -> Optional[str]:
    return None


class DetectOsPreferredLocaleScriptTests(unittest.TestCase):
    def test_normalizes_locale_tags(self) -> None:
        self.assertEqual("ko-KR", module.normalize_locale("ko_KR.UTF-8"))
        self.assertEqual("zh-Hant-TW", module.normalize_locale("zh_Hant_TW"))
        self.assertIsNone(module.normalize_locale("C.UTF-8"))
        self.assertIsNone(module.normalize_locale("POSIX"))

    def test_explicit_locale_wins(self) -> None:
        result = module.detect_os_preferred_locale(
            explicit_locale="ja_JP.UTF-8",
            environ={"LANG": "ko_KR.UTF-8"},
            system_name="Linux",
            runner=empty_runner,
        )

        self.assertEqual("ja-JP", result.locale)
        self.assertEqual("explicit", result.source)

    def test_macos_apple_languages_precedes_environment(self) -> None:
        def runner(command: Sequence[str]) -> Optional[str]:
            if command == ["defaults", "read", "-g", "AppleLanguages"]:
                return '(\n    "ko-KR",\n    "en-KR"\n)'
            return None

        result = module.detect_os_preferred_locale(
            environ={"LANG": "en_US.UTF-8"},
            system_name="Darwin",
            runner=runner,
        )

        self.assertEqual("ko-KR", result.locale)
        self.assertEqual("macos:AppleLanguages", result.source)

    def test_macos_apple_locale_fallback(self) -> None:
        def runner(command: Sequence[str]) -> Optional[str]:
            if command == ["defaults", "read", "-g", "AppleLocale"]:
                return "ko_KR"
            return None

        result = module.detect_os_preferred_locale(
            environ={},
            system_name="Darwin",
            runner=runner,
        )

        self.assertEqual("ko-KR", result.locale)
        self.assertEqual("macos:AppleLocale", result.source)

    def test_environment_ignores_c_and_posix_values(self) -> None:
        result = module.detect_os_preferred_locale(
            environ={"LC_ALL": "C", "LC_MESSAGES": "POSIX", "LANG": "fr_FR.UTF-8"},
            system_name="Linux",
            runner=empty_runner,
        )

        self.assertEqual("fr-FR", result.locale)
        self.assertEqual("env:LANG", result.source)

    def test_cli_json_output(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--explicit-locale",
                "ko_KR.UTF-8",
                "--format",
                "json",
            ],
            check=True,
            text=True,
            capture_output=True,
        )

        payload = json.loads(result.stdout)
        self.assertEqual(
            {"locale": "ko-KR", "raw": "ko_KR.UTF-8", "source": "explicit"},
            payload,
        )


if __name__ == "__main__":
    unittest.main()
