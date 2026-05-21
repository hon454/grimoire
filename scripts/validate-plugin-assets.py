#!/usr/bin/env python3
"""Validate Codex plugin visual assets for Grimoire."""

from __future__ import annotations

import json
import struct
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins"

EXPECTED_ASSETS = {
    "logo": (512, 512),
    "composerIcon": (256, 256),
}

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_PNG_FILE_BYTES = 2 * 1024 * 1024
MIN_MARGIN_RATIO = 0.08
MAX_MARGIN_RATIO = 0.40


@dataclass(frozen=True)
class PngImage:
    width: int
    height: int
    bit_depth: int
    color_type: int
    interlace: int
    rows: list[bytes]


def iter_chunks(data: bytes):
    offset = len(PNG_SIGNATURE)
    while offset < len(data):
        if offset + 8 > len(data):
            raise ValueError("truncated PNG chunk header")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_start = offset + 8
        chunk_end = chunk_start + length
        crc_end = chunk_end + 4
        if crc_end > len(data):
            raise ValueError(f"truncated PNG chunk {chunk_type.decode('ascii', 'replace')}")
        yield chunk_type, data[chunk_start:chunk_end]
        offset = crc_end


def paeth(left: int, up: int, upper_left: int) -> int:
    predictor = left + up - upper_left
    left_distance = abs(predictor - left)
    up_distance = abs(predictor - up)
    upper_left_distance = abs(predictor - upper_left)
    if left_distance <= up_distance and left_distance <= upper_left_distance:
        return left
    if up_distance <= upper_left_distance:
        return up
    return upper_left


def unfilter_scanlines(raw: bytes, width: int, height: int) -> list[bytes]:
    bytes_per_pixel = 4
    row_length = width * bytes_per_pixel
    expected_length = height * (row_length + 1)
    if len(raw) != expected_length:
        raise ValueError(f"unexpected decompressed data length {len(raw)}")

    rows: list[bytes] = []
    offset = 0
    previous = bytes(row_length)
    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        encoded = raw[offset : offset + row_length]
        offset += row_length
        decoded = bytearray(row_length)

        for index, value in enumerate(encoded):
            left = decoded[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
            up = previous[index]
            upper_left = previous[index - bytes_per_pixel] if index >= bytes_per_pixel else 0

            if filter_type == 0:
                decoded[index] = value
            elif filter_type == 1:
                decoded[index] = (value + left) & 0xFF
            elif filter_type == 2:
                decoded[index] = (value + up) & 0xFF
            elif filter_type == 3:
                decoded[index] = (value + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                decoded[index] = (value + paeth(left, up, upper_left)) & 0xFF
            else:
                raise ValueError(f"unsupported PNG filter type {filter_type}")

        previous = bytes(decoded)
        rows.append(previous)

    return rows


def bounded_zlib_decompress(chunks: list[bytes], expected_length: int) -> bytes:
    decompressor = zlib.decompressobj()
    raw = bytearray()

    try:
        for chunk in chunks:
            limit = expected_length + 1 - len(raw)
            if limit <= 0:
                raise ValueError(f"unexpected decompressed data length greater than {expected_length}")
            raw.extend(decompressor.decompress(chunk, limit))
            if len(raw) > expected_length:
                raise ValueError(f"unexpected decompressed data length {len(raw)}")

        limit = expected_length + 1 - len(raw)
        if limit <= 0:
            raise ValueError(f"unexpected decompressed data length greater than {expected_length}")
        raw.extend(decompressor.flush(limit))
    except zlib.error as exc:
        raise ValueError(f"invalid PNG image data: {exc}") from exc

    if len(raw) != expected_length:
        raise ValueError(f"unexpected decompressed data length {len(raw)}")
    if not decompressor.eof:
        raise ValueError("incomplete PNG image data")
    return bytes(raw)


def load_png(path: Path, expected_size: tuple[int, int] | None = None) -> PngImage:
    file_size = path.stat().st_size
    if file_size > MAX_PNG_FILE_BYTES:
        raise ValueError(f"PNG file size {file_size} exceeds maximum {MAX_PNG_FILE_BYTES}")

    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG file")

    width = height = bit_depth = color_type = interlace = None
    idat_parts: list[bytes] = []

    for chunk_type, chunk_data in iter_chunks(data):
        if chunk_type == b"IHDR":
            if len(chunk_data) != 13:
                raise ValueError(f"invalid IHDR chunk length {len(chunk_data)}")
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(
                ">IIBBBBB", chunk_data
            )
        elif chunk_type == b"IDAT":
            idat_parts.append(chunk_data)
        elif chunk_type == b"IEND":
            break

    if width is None or height is None or bit_depth is None or color_type is None or interlace is None:
        raise ValueError("missing IHDR")
    if bit_depth != 8:
        raise ValueError(f"expected 8-bit PNG, found bit depth {bit_depth}")
    if color_type != 6:
        raise ValueError(f"expected RGBA PNG color type 6, found {color_type}")
    if interlace != 0:
        raise ValueError("interlaced PNGs are not supported")
    if expected_size is not None and (width, height) != expected_size:
        raise ValueError(
            f"expected {expected_size[0]}x{expected_size[1]}, found {width}x{height}"
        )

    row_length = width * 4
    raw = bounded_zlib_decompress(idat_parts, height * (row_length + 1))
    rows = unfilter_scanlines(raw, width, height)
    return PngImage(width, height, bit_depth, color_type, interlace, rows)


def alpha_at(image: PngImage, x: int, y: int) -> int:
    return image.rows[y][x * 4 + 3]


def opaque_bbox(image: PngImage) -> tuple[int, int, int, int] | None:
    min_x = image.width
    min_y = image.height
    max_x = -1
    max_y = -1
    for y, row in enumerate(image.rows):
        for x in range(image.width):
            if row[x * 4 + 3] > 0:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    if max_x < 0:
        return None
    return min_x, min_y, max_x, max_y


def greenish_visible_pixels(image: PngImage) -> int:
    count = 0
    for row in image.rows:
        for offset in range(0, len(row), 4):
            red, green, blue, alpha = row[offset : offset + 4]
            if alpha > 0 and red < 32 and green > 180 and blue < 96:
                count += 1
    return count


def validate_asset(plugin_dir: Path, manifest_path: Path, key: str, rel_path: str) -> list[str]:
    errors: list[str] = []
    expected_size = EXPECTED_ASSETS[key]

    if not isinstance(rel_path, str) or not rel_path.startswith("./"):
        return [f"{manifest_path}: interface.{key} must be a ./ relative path"]

    asset_path = (plugin_dir / rel_path).resolve()
    try:
        asset_path.relative_to(plugin_dir.resolve())
    except ValueError:
        return [f"{manifest_path}: interface.{key} escapes plugin directory"]

    if not asset_path.exists():
        return [f"{manifest_path}: interface.{key} target does not exist: {rel_path}"]
    if asset_path.suffix.lower() != ".png":
        errors.append(f"{asset_path}: expected PNG file extension")

    try:
        image = load_png(asset_path, expected_size)
    except ValueError as exc:
        return errors + [f"{asset_path}: {exc}"]

    corner_alpha = [
        alpha_at(image, 0, 0),
        alpha_at(image, image.width - 1, 0),
        alpha_at(image, 0, image.height - 1),
        alpha_at(image, image.width - 1, image.height - 1),
    ]
    if any(corner_alpha):
        errors.append(f"{asset_path}: expected fully transparent corners, found {corner_alpha}")

    bbox = opaque_bbox(image)
    if bbox is None:
        errors.append(f"{asset_path}: image has no visible pixels")
    else:
        min_x, min_y, max_x, max_y = bbox
        margins = [
            min_x / image.width,
            min_y / image.height,
            (image.width - max_x - 1) / image.width,
            (image.height - max_y - 1) / image.height,
        ]
        if min(margins) < MIN_MARGIN_RATIO:
            errors.append(f"{asset_path}: visible mark has too little transparent padding: {bbox}")
        if min_x > image.width * MAX_MARGIN_RATIO or min_y > image.height * MAX_MARGIN_RATIO:
            errors.append(f"{asset_path}: visible mark appears too small or off-center: {bbox}")

    greenish_count = greenish_visible_pixels(image)
    if greenish_count:
        errors.append(f"{asset_path}: found {greenish_count} visible chroma-key green pixels")

    return errors


def validate_manifest(manifest_path: Path) -> list[str]:
    errors: list[str] = []
    plugin_dir = manifest_path.parents[1]
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        return [f"{manifest_path}: invalid JSON: {exc}"]

    if not isinstance(manifest, dict):
        return [f"{manifest_path}: manifest must be a JSON object"]
    if "interface" not in manifest:
        return errors
    interface = manifest["interface"]
    if not isinstance(interface, dict):
        return [f"{manifest_path}: missing interface object"]

    if not any(key in interface for key in EXPECTED_ASSETS):
        return []

    for key in EXPECTED_ASSETS:
        if key not in interface:
            continue
        rel_path = interface[key]
        errors.extend(validate_asset(plugin_dir, manifest_path, key, rel_path))

    return errors


def main() -> int:
    manifests = sorted(PLUGIN_ROOT.glob("*/.codex-plugin/plugin.json"))
    errors: list[str] = []

    for manifest_path in manifests:
        errors.extend(validate_manifest(manifest_path))

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Validated plugin asset fields for {len(manifests)} Codex plugin manifest(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
