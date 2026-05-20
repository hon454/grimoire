from __future__ import annotations

import importlib.util
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


class ValidatePluginAssetsTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
