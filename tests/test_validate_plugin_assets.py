from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate-plugin-assets.py"
spec = importlib.util.spec_from_file_location("validate_plugin_assets", SCRIPT)
validate_plugin_assets = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["validate_plugin_assets"] = validate_plugin_assets
spec.loader.exec_module(validate_plugin_assets)


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return len(data).to_bytes(4, "big") + chunk_type + data + b"\x00\x00\x00\x00"


def png_bytes(width: int, height: int, *, idat: bytes = b"not-zlib-data") -> bytes:
    ihdr = (
        width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + bytes([8, 6, 0, 0, 0])
    )
    return (
        validate_plugin_assets.PNG_SIGNATURE
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", idat)
        + png_chunk(b"IEND", b"")
    )


def valid_asset_png(width: int, height: int) -> bytes:
    row_length = width * 4
    min_x = width // 4
    max_x = width - min_x
    min_y = height // 4
    max_y = height - min_y
    rows = []
    for y in range(height):
        row = bytearray(row_length)
        for x in range(width):
            offset = x * 4
            if min_x <= x < max_x and min_y <= y < max_y:
                row[offset : offset + 4] = bytes([192, 32, 64, 255])
        rows.append(b"\x00" + bytes(row))
    return png_bytes(width, height, idat=zlib.compress(b"".join(rows)))


class ValidatePluginAssetsTests(unittest.TestCase):
    def validate_temp_manifest(self, manifest: object) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp)
            manifest_path = plugin_dir / ".codex-plugin" / "plugin.json"
            manifest_path.parent.mkdir()
            manifest_path.write_text(json.dumps(manifest))
            return validate_plugin_assets.validate_manifest(manifest_path)

    def validate_temp_asset(self, asset_bytes: bytes, *, key: str = "logo") -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp)
            manifest_path = plugin_dir / ".codex-plugin" / "plugin.json"
            manifest_path.parent.mkdir()
            asset_path = plugin_dir / "asset.png"
            asset_path.write_bytes(asset_bytes)
            return validate_plugin_assets.validate_asset(
                plugin_dir,
                manifest_path,
                key,
                "./asset.png",
            )

    def test_manifest_visual_assets_are_optional(self) -> None:
        errors = self.validate_temp_manifest({"name": "plugin", "interface": {}})

        self.assertEqual([], errors)

    def test_manifest_without_interface_has_no_asset_errors(self) -> None:
        errors = self.validate_temp_manifest({"name": "plugin"})

        self.assertEqual([], errors)

    def test_manifest_must_be_json_object(self) -> None:
        for manifest in ([], None, 1, "plugin"):
            with self.subTest(manifest=manifest):
                errors = self.validate_temp_manifest(manifest)

                self.assertTrue(
                    any("manifest must be a JSON object" in error for error in errors),
                    errors,
                )

    def test_null_manifest_interface_is_rejected(self) -> None:
        errors = self.validate_temp_manifest({"name": "plugin", "interface": None})

        self.assertTrue(any("missing interface object" in error for error in errors), errors)

    def test_null_manifest_visual_asset_is_rejected_when_present(self) -> None:
        errors = self.validate_temp_manifest({"name": "plugin", "interface": {"logo": None}})

        self.assertTrue(
            any("interface.logo must be a ./ relative path" in error for error in errors),
            errors,
        )

    def test_present_manifest_logo_is_validated(self) -> None:
        errors = self.validate_temp_manifest(
            {"name": "plugin", "interface": {"logo": "./missing.png"}}
        )

        self.assertTrue(any("interface.logo target does not exist" in error for error in errors))

    def test_present_manifest_composer_icon_is_validated(self) -> None:
        errors = self.validate_temp_manifest(
            {"name": "plugin", "interface": {"composerIcon": "./missing.png"}}
        )

        self.assertTrue(
            any("interface.composerIcon target does not exist" in error for error in errors)
        )

    def test_dimension_mismatch_is_rejected_before_decompression(self) -> None:
        errors = self.validate_temp_asset(png_bytes(1, 1, idat=b"not-zlib-data"))

        self.assertTrue(
            any("expected 512x512, found 1x1" in error for error in errors),
            errors,
        )

    def test_malformed_ihdr_returns_diagnostic_instead_of_traceback(self) -> None:
        malformed = (
            validate_plugin_assets.PNG_SIGNATURE
            + png_chunk(b"IHDR", b"\x00")
            + png_chunk(b"IEND", b"")
        )

        errors = self.validate_temp_asset(malformed)

        self.assertTrue(any("IHDR" in error for error in errors), errors)

    def test_oversized_png_file_is_rejected(self) -> None:
        oversized = validate_plugin_assets.PNG_SIGNATURE + (
            b"\x00" * (validate_plugin_assets.MAX_PNG_FILE_BYTES + 1)
        )

        errors = self.validate_temp_asset(oversized)

        self.assertTrue(any("exceeds maximum" in error for error in errors), errors)

    def test_decompression_is_bounded_to_expected_image_size(self) -> None:
        row_length = 512 * 4
        oversized_raw = b"\x00" * ((row_length + 1) * 512 + 1)

        original_decompress = validate_plugin_assets.zlib.decompress
        try:
            validate_plugin_assets.zlib.decompress = lambda _: (_ for _ in ()).throw(
                AssertionError("unbounded zlib.decompress was called")
            )
            errors = self.validate_temp_asset(png_bytes(512, 512, idat=zlib.compress(oversized_raw)))
        finally:
            validate_plugin_assets.zlib.decompress = original_decompress

        self.assertTrue(
            any("unexpected decompressed data length" in error for error in errors),
            errors,
        )

    def test_manifest_without_visual_asset_fields_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp)
            manifest_path = plugin_dir / ".codex-plugin" / "plugin.json"
            manifest_path.parent.mkdir()
            manifest_path.write_text('{"interface": {"displayName": "No Assets"}}')

            self.assertEqual(validate_plugin_assets.validate_manifest(manifest_path), [])

    def test_manifest_with_partial_visual_asset_fields_requires_the_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp)
            manifest_path = plugin_dir / ".codex-plugin" / "plugin.json"
            manifest_path.parent.mkdir()
            manifest_path.write_text(
                '{"interface": {"displayName": "Partial Assets", "logo": "./logo.png"}}'
            )

            errors = validate_plugin_assets.validate_manifest(manifest_path)

        self.assertTrue(any("missing interface.composerIcon" in error for error in errors), errors)

    def test_manifest_with_composer_icon_only_requires_logo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp)
            manifest_path = plugin_dir / ".codex-plugin" / "plugin.json"
            manifest_path.parent.mkdir()
            manifest_path.write_text(
                '{"interface": {"displayName": "Partial Assets", "composerIcon": "./icon.png"}}'
            )

            errors = validate_plugin_assets.validate_manifest(manifest_path)

        self.assertTrue(any("missing interface.logo" in error for error in errors), errors)

    def test_manifest_with_paired_visual_asset_fields_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp)
            manifest_path = plugin_dir / ".codex-plugin" / "plugin.json"
            manifest_path.parent.mkdir()
            (plugin_dir / "logo.png").write_bytes(valid_asset_png(512, 512))
            (plugin_dir / "icon.png").write_bytes(valid_asset_png(256, 256))
            manifest_path.write_text(
                '{"interface": {"displayName": "Full Assets", "logo": "./logo.png", "composerIcon": "./icon.png"}}'
            )

            self.assertEqual(validate_plugin_assets.validate_manifest(manifest_path), [])

    def test_grimoire_plugin_assets_are_valid(self) -> None:
        manifest_path = ROOT / "plugins" / "grimoire" / ".codex-plugin" / "plugin.json"

        self.assertEqual(validate_plugin_assets.validate_manifest(manifest_path), [])


if __name__ == "__main__":
    unittest.main()
