#!/usr/bin/env python3
"""
Quake WAD Tools - Image to WAD conversion utility
Converts images to Quake WAD format with various dithering and alpha options
"""

import argparse
import sys
import os
import glob
import time
from functools import lru_cache
from pathlib import Path
from typing import List, Tuple, Optional
import struct

try:
    from PIL import Image, ImageChops
except ImportError:
    print("Error: PIL/Pillow is required. Install with: pip install Pillow")
    sys.exit(1)

# Quake palette (256 colors)
QUAKE_PALETTE = [
    0x00, 0x00, 0x00, 0x0f, 0x0f, 0x0f, 0x1f, 0x1f, 0x1f, 0x2f, 0x2f, 0x2f,
    0x3f, 0x3f, 0x3f, 0x4b, 0x4b, 0x4b, 0x5b, 0x5b, 0x5b, 0x6b, 0x6b, 0x6b,
    0x7b, 0x7b, 0x7b, 0x8b, 0x8b, 0x8b, 0x9b, 0x9b, 0x9b, 0xab, 0xab, 0xab,
    0xbb, 0xbb, 0xbb, 0xcb, 0xcb, 0xcb, 0xdb, 0xdb, 0xdb, 0xeb, 0xeb, 0xeb,
    0x0f, 0x0b, 0x07, 0x17, 0x0f, 0x0b, 0x1f, 0x17, 0x0b, 0x27, 0x1b, 0x0f,
    0x2f, 0x23, 0x13, 0x37, 0x2b, 0x17, 0x3f, 0x2f, 0x17, 0x4b, 0x37, 0x1b,
    0x53, 0x3b, 0x1b, 0x5b, 0x43, 0x1f, 0x63, 0x4b, 0x1f, 0x6b, 0x53, 0x1f,
    0x73, 0x57, 0x1f, 0x7b, 0x5f, 0x23, 0x83, 0x67, 0x23, 0x8f, 0x6f, 0x23,
    0x0b, 0x0b, 0x0f, 0x13, 0x13, 0x1b, 0x1b, 0x1b, 0x27, 0x27, 0x27, 0x33,
    0x2f, 0x2f, 0x3f, 0x37, 0x37, 0x4b, 0x3f, 0x3f, 0x57, 0x47, 0x47, 0x67,
    0x4f, 0x4f, 0x73, 0x5b, 0x5b, 0x7f, 0x63, 0x63, 0x8b, 0x6b, 0x6b, 0x97,
    0x73, 0x73, 0xa3, 0x7b, 0x7b, 0xaf, 0x83, 0x83, 0xbb, 0x8b, 0x8b, 0xcb,
    0x00, 0x00, 0x00, 0x07, 0x07, 0x00, 0x0b, 0x0b, 0x00, 0x13, 0x13, 0x00,
    0x1b, 0x1b, 0x00, 0x23, 0x23, 0x00, 0x2b, 0x2b, 0x07, 0x2f, 0x2f, 0x07,
    0x37, 0x37, 0x07, 0x3f, 0x3f, 0x07, 0x47, 0x47, 0x07, 0x4b, 0x4b, 0x0b,
    0x53, 0x53, 0x0b, 0x5b, 0x5b, 0x0b, 0x63, 0x63, 0x0b, 0x6b, 0x6b, 0x0f,
    0x07, 0x00, 0x00, 0x0f, 0x00, 0x00, 0x17, 0x00, 0x00, 0x1f, 0x00, 0x00,
    0x27, 0x00, 0x00, 0x2f, 0x00, 0x00, 0x37, 0x00, 0x00, 0x3f, 0x00, 0x00,
    0x47, 0x00, 0x00, 0x4f, 0x00, 0x00, 0x57, 0x00, 0x00, 0x5f, 0x00, 0x00,
    0x67, 0x00, 0x00, 0x6f, 0x00, 0x00, 0x77, 0x00, 0x00, 0x7f, 0x00, 0x00,
    0x13, 0x13, 0x00, 0x1b, 0x1b, 0x00, 0x23, 0x23, 0x00, 0x2f, 0x2b, 0x07,
    0x37, 0x2f, 0x07, 0x43, 0x37, 0x07, 0x4b, 0x3b, 0x07, 0x57, 0x43, 0x07,
    0x5f, 0x47, 0x07, 0x6b, 0x4b, 0x0b, 0x77, 0x53, 0x0f, 0x83, 0x57, 0x13,
    0x8b, 0x5b, 0x13, 0x97, 0x5f, 0x1b, 0xa3, 0x63, 0x1f, 0xaf, 0x67, 0x23,
    0x23, 0x13, 0x07, 0x2f, 0x17, 0x0b, 0x3b, 0x1f, 0x0f, 0x4b, 0x23, 0x13,
    0x57, 0x2b, 0x17, 0x63, 0x2f, 0x1f, 0x73, 0x37, 0x23, 0x7f, 0x3b, 0x2b,
    0x8f, 0x43, 0x33, 0x9f, 0x4f, 0x33, 0xaf, 0x63, 0x2f, 0xbf, 0x77, 0x2f,
    0xcf, 0x8f, 0x2f, 0xdf, 0xab, 0x27, 0xef, 0xcb, 0x1f, 0xff, 0xf3, 0x1b,
    0x0b, 0x07, 0x00, 0x1b, 0x13, 0x00, 0x2b, 0x23, 0x0f, 0x37, 0x2b, 0x13,
    0x47, 0x33, 0x1b, 0x53, 0x37, 0x23, 0x63, 0x3f, 0x2b, 0x6f, 0x47, 0x33,
    0x7f, 0x53, 0x3f, 0x8b, 0x5f, 0x47, 0x9b, 0x6b, 0x53, 0xa7, 0x7b, 0x5f,
    0xb7, 0x87, 0x6b, 0xc3, 0x93, 0x7b, 0xd3, 0xa3, 0x8b, 0xe3, 0xb3, 0x97,
    0xab, 0x8b, 0xa3, 0x9f, 0x7f, 0x97, 0x93, 0x73, 0x87, 0x8b, 0x67, 0x7b,
    0x7f, 0x5b, 0x6f, 0x77, 0x53, 0x63, 0x6b, 0x4b, 0x57, 0x5f, 0x3f, 0x4b,
    0x57, 0x37, 0x43, 0x4b, 0x2f, 0x37, 0x43, 0x27, 0x2f, 0x37, 0x1f, 0x23,
    0x2b, 0x17, 0x1b, 0x23, 0x13, 0x13, 0x17, 0x0b, 0x0b, 0x0f, 0x07, 0x07,
    0xbb, 0x73, 0x9f, 0xaf, 0x6b, 0x8f, 0xa3, 0x5f, 0x83, 0x97, 0x57, 0x77,
    0x8b, 0x4f, 0x6b, 0x7f, 0x4b, 0x5f, 0x73, 0x43, 0x53, 0x6b, 0x3b, 0x4b,
    0x5f, 0x33, 0x3f, 0x53, 0x2b, 0x37, 0x47, 0x23, 0x2b, 0x3b, 0x1f, 0x23,
    0x2f, 0x17, 0x1b, 0x23, 0x13, 0x13, 0x17, 0x0b, 0x0b, 0x0f, 0x07, 0x07,
    0xdb, 0xc3, 0xbb, 0xcb, 0xb3, 0xa7, 0xbf, 0xa3, 0x9b, 0xaf, 0x97, 0x8b,
    0xa3, 0x87, 0x7b, 0x97, 0x7b, 0x6f, 0x87, 0x6f, 0x5f, 0x7b, 0x63, 0x53,
    0x6b, 0x57, 0x47, 0x5f, 0x4b, 0x3b, 0x53, 0x3f, 0x33, 0x43, 0x33, 0x27,
    0x37, 0x2b, 0x1f, 0x27, 0x1f, 0x17, 0x1b, 0x13, 0x0f, 0x0f, 0x0b, 0x07,
    0x6f, 0x83, 0x7b, 0x67, 0x7b, 0x6f, 0x5f, 0x73, 0x67, 0x57, 0x6b, 0x5f,
    0x4f, 0x63, 0x57, 0x47, 0x5b, 0x4f, 0x3f, 0x53, 0x47, 0x37, 0x4b, 0x3f,
    0x2f, 0x43, 0x37, 0x27, 0x3b, 0x2f, 0x1f, 0x33, 0x27, 0x17, 0x2b, 0x1f,
    0x0f, 0x23, 0x17, 0x07, 0x1b, 0x0f, 0x00, 0x13, 0x0b, 0x00, 0x0b, 0x07,
    0xff, 0xf3, 0x1b, 0xef, 0xdf, 0x17, 0xdb, 0xcb, 0x13, 0xcb, 0xb7, 0x0f,
    0xbb, 0xa7, 0x0f, 0xab, 0x97, 0x0b, 0x9b, 0x83, 0x07, 0x8b, 0x73, 0x07,
    0x7b, 0x63, 0x07, 0x6b, 0x53, 0x00, 0x5b, 0x47, 0x00, 0x4b, 0x37, 0x00,
    0x3b, 0x2b, 0x00, 0x2b, 0x1f, 0x00, 0x1b, 0x0f, 0x00, 0x0b, 0x07, 0x00,
    0x00, 0x00, 0xff, 0x0b, 0x0b, 0xef, 0x13, 0x13, 0xdf, 0x1b, 0x1b, 0xcf,
    0x23, 0x23, 0xbf, 0x2b, 0x2b, 0xaf, 0x2f, 0x2f, 0x9f, 0x2f, 0x2f, 0x8f,
    0x2f, 0x2f, 0x7f, 0x2f, 0x2f, 0x6f, 0x2f, 0x2f, 0x5f, 0x2b, 0x2b, 0x4f,
    0x23, 0x23, 0x3f, 0x1b, 0x1b, 0x2f, 0x13, 0x13, 0x1f, 0x0b, 0x0b, 0x0f,
    0x2b, 0x00, 0x00, 0x3b, 0x00, 0x00, 0x4b, 0x07, 0x00, 0x5f, 0x07, 0x00,
    0x6f, 0x0f, 0x00, 0x7f, 0x17, 0x07, 0x93, 0x1f, 0x07, 0xa3, 0x27, 0x0b,
    0xb7, 0x33, 0x0f, 0xc3, 0x4b, 0x1b, 0xcf, 0x63, 0x2b, 0xdb, 0x7f, 0x3b,
    0xe3, 0x97, 0x4f, 0xe7, 0xab, 0x5f, 0xef, 0xbf, 0x77, 0xf7, 0xd3, 0x8b,
    0xa7, 0x7b, 0x3b, 0xb7, 0x9b, 0x37, 0xc7, 0xc3, 0x37, 0xe7, 0xe3, 0x57,
    0x7f, 0xbf, 0xff, 0xab, 0xe7, 0xff, 0xd7, 0xff, 0xff, 0x67, 0x00, 0x00,
    0x8b, 0x00, 0x00, 0xb3, 0x00, 0x00, 0xd7, 0x00, 0x00, 0xff, 0x00, 0x00,
    0xff, 0xf3, 0x93, 0xff, 0xf7, 0xc7, 0xff, 0xff, 0xff, 0x9f, 0x5b, 0x53,
]

# Keep the embedded palette as a fallback in case external palette files are unavailable.
LEGACY_QUAKE_PALETTE_FULL = list(QUAKE_PALETTE)
NO_FULLBRIGHT_COLOR_COUNT = 224


def _create_palette_image(palette: List[int]) -> Image.Image:
    """Create a PIL palette image suitable for fast quantization."""
    palette_img = Image.new('P', (1, 1))
    # PIL expects exactly 256 RGB entries (768 values).
    pil_palette = list(palette[:768])
    if len(pil_palette) < 768:
        pil_palette.extend([0] * (768 - len(pil_palette)))
    palette_img.putpalette(pil_palette)
    return palette_img


def _normalize_palette(palette_values: List[int], color_count: int) -> Tuple[List[int], int]:
    """Normalize a palette to 256 RGB entries while preserving active color count."""
    normalized_count = max(1, min(256, color_count))
    normalized = list(palette_values[:normalized_count * 3])

    if len(normalized) < normalized_count * 3:
        normalized.extend([0] * ((normalized_count * 3) - len(normalized)))

    filler = normalized[(normalized_count - 1) * 3: normalized_count * 3]
    if not filler:
        filler = [0, 0, 0]

    while len(normalized) < 768:
        normalized.extend(filler)

    return normalized[:768], normalized_count


def _load_palette_from_tga(palette_path: Path) -> Optional[Tuple[List[int], int]]:
    """Load palette RGB values from a palette image file."""
    try:
        with Image.open(palette_path) as palette_image:
            palette_values = palette_image.getpalette()
    except Exception as exc:
        print(f"Warning: Could not load palette file {palette_path.name}: {exc}")
        return None

    if not palette_values:
        print(f"Warning: Palette file {palette_path.name} has no palette table")
        return None

    color_count = min(256, len(palette_values) // 3)
    if color_count <= 0:
        print(f"Warning: Palette file {palette_path.name} has no RGB entries")
        return None

    normalized, _ = _normalize_palette(palette_values, color_count)
    return normalized, color_count


def _load_default_palettes() -> Tuple[List[int], int, List[int], int]:
    """Load full and no-fullbright palettes, preferring local palette files."""
    script_dir = Path(__file__).resolve().parent

    full_palette, full_color_count = _normalize_palette(LEGACY_QUAKE_PALETTE_FULL, 256)
    loaded_full = _load_palette_from_tga(script_dir / 'palette_full.tga')
    if loaded_full is not None:
        full_palette, full_color_count = loaded_full

    fallback_no_fb_count = min(NO_FULLBRIGHT_COLOR_COUNT, full_color_count)
    fallback_no_fb_values = full_palette[:fallback_no_fb_count * 3]
    no_fb_palette, no_fb_color_count = _normalize_palette(fallback_no_fb_values, fallback_no_fb_count)

    loaded_no_fb = _load_palette_from_tga(script_dir / 'palette_no_fb.tga')
    if loaded_no_fb is not None:
        loaded_no_fb_palette, loaded_no_fb_count = loaded_no_fb
        # Fullbright colors are 224-255 in Quake; keep quantization strictly below that range.
        effective_no_fb_count = min(NO_FULLBRIGHT_COLOR_COUNT, loaded_no_fb_count)
        no_fb_palette, no_fb_color_count = _normalize_palette(
            loaded_no_fb_palette,
            effective_no_fb_count
        )

    return full_palette, full_color_count, no_fb_palette, no_fb_color_count


(
    QUAKE_FULL_PALETTE,
    QUAKE_FULL_COLOR_COUNT,
    QUAKE_NO_FULLBRIGHT_PALETTE,
    QUAKE_NO_FULLBRIGHT_COLOR_COUNT,
) = _load_default_palettes()

# Backward-compatible palette name used by readers/display paths.
QUAKE_PALETTE = QUAKE_FULL_PALETTE

# Default processing palette used by CLI/editor image conversion paths.
QUAKE_PROCESS_PALETTE = QUAKE_NO_FULLBRIGHT_PALETTE
QUAKE_PROCESS_COLOR_COUNT = QUAKE_NO_FULLBRIGHT_COLOR_COUNT

PALETTE_MODE_ORIGINAL = 'original'
PALETTE_MODE_NO_FULLBRIGHTS = 'no_fullbrights'
PALETTE_MODE_CUSTOM = 'custom'

DITHERING_INDEX_ERROR_DIFFUSION = 0
DITHERING_INDEX_ORDERED = 1
DITHERING_INDEX_RANDOM = 2
DITHERING_INDEX_HALFTONE = 3
DITHERING_INDEX_CLOSEST_COLOR = 4

DITHERING_LABELS = {
    DITHERING_INDEX_ERROR_DIFFUSION: 'Error Diffusion',
    DITHERING_INDEX_ORDERED: 'Ordered Dithering',
    DITHERING_INDEX_RANDOM: 'Random Dithering',
    DITHERING_INDEX_HALFTONE: 'Halftone Dithering',
    DITHERING_INDEX_CLOSEST_COLOR: 'Closest Color Available',
}

ORDERED_BAYER_MATRIX = (
    0, 8, 2, 10,
    12, 4, 14, 6,
    3, 11, 1, 9,
    15, 7, 13, 5,
)
HALFTONE_CLUSTER_MATRIX = (
    24, 10, 12, 26, 35, 47, 49, 37,
    8, 0, 2, 14, 45, 59, 61, 51,
    22, 6, 4, 16, 43, 57, 63, 53,
    30, 20, 18, 28, 33, 41, 55, 39,
    34, 46, 48, 36, 25, 11, 13, 27,
    44, 58, 60, 50, 9, 1, 3, 15,
    42, 56, 62, 52, 23, 7, 5, 17,
    32, 40, 54, 38, 31, 21, 19, 29,
)

RANDOM_NOISE_STRENGTH = 32
RANDOM_NOISE_LUT = [
    max(0, min(255, int(128 + (value - 128) * (RANDOM_NOISE_STRENGTH / 128.0))))
    for value in range(256)
]

ALPHA_TRANSPARENT_MASK_LUT = [255 if value < 128 else 0 for value in range(256)]
ORDERED_ALPHA_DITHER = getattr(Image.Dither, 'ORDERED', Image.Dither.FLOYDSTEINBERG)

QUAKE_FULL_PALETTE_IMAGE = _create_palette_image(QUAKE_FULL_PALETTE)
QUAKE_NO_FULLBRIGHT_PALETTE_IMAGE = _create_palette_image(QUAKE_NO_FULLBRIGHT_PALETTE)

# Backward-compatible alias for existing fast quantization call sites.
QUAKE_PALETTE_IMAGE = QUAKE_NO_FULLBRIGHT_PALETTE_IMAGE

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color string to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def find_closest_color(rgb: Tuple[int, int, int], palette: List[int], max_colors: Optional[int] = None) -> int:
    """Find the closest color index in the palette"""
    min_distance = float('inf')
    closest_index = 0
    palette_size = min(256, len(palette) // 3)
    if max_colors is not None:
        palette_size = min(palette_size, max_colors)
    
    r, g, b = rgb
    for i in range(palette_size):
        pr = palette[i * 3]
        pg = palette[i * 3 + 1]
        pb = palette[i * 3 + 2]
        
        # Euclidean distance in RGB space
        distance = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        
        if distance < min_distance:
            min_distance = distance
            closest_index = i
    
    return closest_index


def _build_index_remap_table(palette: List[int], allowed_color_count: int) -> bytes:
    """Build a byte translation table that remaps disallowed indices into allowed range."""
    allowed = max(1, min(256, allowed_color_count, len(palette) // 3))
    remap = list(range(256))

    for index in range(allowed, 256):
        rgb = (
            palette[index * 3],
            palette[index * 3 + 1],
            palette[index * 3 + 2],
        )
        remap[index] = find_closest_color(rgb, palette, max_colors=allowed)

    return bytes(remap)


QUAKE_FULL_INDEX_REMAP_TABLE: Optional[bytes] = None

QUAKE_NO_FULLBRIGHT_INDEX_REMAP_TABLE: Optional[bytes] = None
if QUAKE_NO_FULLBRIGHT_COLOR_COUNT < 256:
    QUAKE_NO_FULLBRIGHT_INDEX_REMAP_TABLE = _build_index_remap_table(
        QUAKE_NO_FULLBRIGHT_PALETTE,
        QUAKE_NO_FULLBRIGHT_COLOR_COUNT
    )

# Backward-compatible alias for existing processing call sites.
QUAKE_PROCESS_INDEX_REMAP_TABLE = QUAKE_NO_FULLBRIGHT_INDEX_REMAP_TABLE


def resolve_process_palette(
    palette_mode: Optional[str],
    custom_palette: Optional[List[int]] = None,
    include_fullbrights: bool = False,
) -> Tuple[str, List[int], int, Image.Image, Optional[bytes]]:
    """Resolve palette resources based on palette mode."""
    normalized_mode = (palette_mode or '').strip().lower()

    if normalized_mode == PALETTE_MODE_CUSTOM:
        if custom_palette and len(custom_palette) >= 3:
            custom_palette_size = min(256, len(custom_palette) // 3)
            normalized_custom_palette, custom_color_count = _normalize_palette(
                custom_palette,
                custom_palette_size,
            )

            if include_fullbrights:
                allowed_color_count = custom_color_count
            else:
                # Preserve no-fullbright safety by default for custom import palettes.
                allowed_color_count = min(NO_FULLBRIGHT_COLOR_COUNT, custom_color_count)

            allowed_color_count = max(1, allowed_color_count)
            custom_palette_image, custom_index_remap_table = _resolve_palette_quantization_resources(
                normalized_custom_palette,
                max_colors=custom_color_count,
            )

            if allowed_color_count < custom_color_count:
                custom_index_remap_table = _build_index_remap_table(
                    normalized_custom_palette,
                    allowed_color_count,
                )

            return (
                PALETTE_MODE_CUSTOM,
                normalized_custom_palette,
                allowed_color_count,
                custom_palette_image,
                custom_index_remap_table,
            )

        # Invalid custom palette input falls back to safe no-fullbright mode.
        normalized_mode = PALETTE_MODE_NO_FULLBRIGHTS

    if normalized_mode in {'full', 'original', 'quake', 'fullbright', 'fullbrights'}:
        return (
            PALETTE_MODE_ORIGINAL,
            QUAKE_FULL_PALETTE,
            QUAKE_FULL_COLOR_COUNT,
            QUAKE_FULL_PALETTE_IMAGE,
            QUAKE_FULL_INDEX_REMAP_TABLE,
        )

    # Default to no-fullbright processing to avoid accidental fullbright pixels.
    return (
        PALETTE_MODE_NO_FULLBRIGHTS,
        QUAKE_NO_FULLBRIGHT_PALETTE,
        QUAKE_NO_FULLBRIGHT_COLOR_COUNT,
        QUAKE_NO_FULLBRIGHT_PALETTE_IMAGE,
        QUAKE_NO_FULLBRIGHT_INDEX_REMAP_TABLE,
    )


def resolve_dithering_index(dithering: int) -> int:
    """Normalize a dithering mode index to a supported value."""
    try:
        mode_index = int(dithering)
    except Exception:
        mode_index = DITHERING_INDEX_ERROR_DIFFUSION

    if mode_index not in DITHERING_LABELS:
        mode_index = DITHERING_INDEX_ERROR_DIFFUSION

    return mode_index


def _build_threshold_lut(
    matrix_values: Tuple[int, ...],
    center: float,
    divisor: float,
    amplitude: float,
) -> Tuple[int, ...]:
    """Create a centered [0..255] LUT from a dithering threshold matrix."""
    lut_values = []
    for value in matrix_values:
        offset = ((float(value) - center) / divisor) * amplitude
        lut_values.append(max(0, min(255, int(round(128 + offset)))))
    return tuple(lut_values)


ORDERED_THRESHOLD_LUT = _build_threshold_lut(ORDERED_BAYER_MATRIX, center=7.5, divisor=16.0, amplitude=255.0)
HALFTONE_THRESHOLD_LUT = _build_threshold_lut(HALFTONE_CLUSTER_MATRIX, center=31.5, divisor=64.0, amplitude=96.0)


@lru_cache(maxsize=24)
def _build_tiled_threshold_pattern(
    width: int,
    height: int,
    tile_size: int,
    threshold_lut: Tuple[int, ...],
) -> Image.Image:
    """Build and cache a tiled threshold pattern image."""
    tile = Image.new('L', (tile_size, tile_size))
    tile.putdata(list(threshold_lut))

    pattern = Image.new('L', (width, height))
    for y in range(0, height, tile_size):
        for x in range(0, width, tile_size):
            pattern.paste(tile, (x, y))

    return pattern


def _apply_threshold_pattern(image: Image.Image, tile_size: int, threshold_lut: Tuple[int, ...]) -> Image.Image:
    """Apply a tiled threshold pattern in RGB space using Pillow image ops."""
    img = image.convert('RGB')
    width, height = img.size
    if width <= 0 or height <= 0:
        return img

    pattern = _build_tiled_threshold_pattern(width, height, tile_size, threshold_lut)
    pattern_rgb = Image.merge('RGB', (pattern, pattern, pattern))
    return ImageChops.add(img, pattern_rgb, scale=1.0, offset=-128)


@lru_cache(maxsize=32)
def _get_palette_quantization_resources(
    palette_bytes: bytes,
    palette_size: int,
) -> Tuple[Image.Image, Optional[bytes]]:
    """Cache palette images and remap tables for quantization."""
    palette_values = list(palette_bytes)
    palette_image = _create_palette_image(palette_values)
    index_remap = None

    if palette_size < 256:
        index_remap = _build_index_remap_table(palette_values, palette_size)

    return palette_image, index_remap


def _resolve_palette_quantization_resources(
    palette: List[int],
    max_colors: Optional[int] = None,
) -> Tuple[Image.Image, Optional[bytes]]:
    """Resolve cached quantization resources for a palette/max-colors pair."""
    palette_size = min(256, len(palette) // 3)
    if max_colors is not None:
        palette_size = min(palette_size, max_colors)
    palette_size = max(1, palette_size)

    normalized_palette, _ = _normalize_palette(palette, palette_size)
    return _get_palette_quantization_resources(bytes(normalized_palette), palette_size)


def _palette_bytes_from_quantized_image(quantized: Image.Image, index_remap_table: Optional[bytes]) -> bytes:
    """Extract palette indices from a quantized image with optional index remapping."""
    palette_data = quantized.tobytes()
    if index_remap_table is not None:
        palette_data = palette_data.translate(index_remap_table)
    return palette_data


def floyd_steinberg_dither(image: Image.Image, palette: List[int], max_colors: Optional[int] = None) -> Image.Image:
    """Apply Floyd-Steinberg dithering to an image"""
    palette_image, _index_remap = _resolve_palette_quantization_resources(palette, max_colors=max_colors)
    quantized = image.convert('RGB').quantize(
        palette=palette_image,
        dither=Image.Dither.FLOYDSTEINBERG,
    )
    return quantized.convert('RGB')


def ordered_dither(image: Image.Image, palette: List[int], max_colors: Optional[int] = None) -> Image.Image:
    """Apply ordered (Bayer matrix) dithering to an image"""
    # Keep signature compatible with earlier implementation.
    del palette, max_colors
    return _apply_threshold_pattern(image, tile_size=4, threshold_lut=ORDERED_THRESHOLD_LUT)


def random_dither(image: Image.Image, palette: List[int], max_colors: Optional[int] = None) -> Image.Image:
    """Apply random-noise dithering before palette matching."""
    # Keep signature consistent with other dithering helpers.
    del palette, max_colors

    img = image.convert('RGB')
    width, height = img.size
    if width <= 0 or height <= 0:
        return img

    # Generate independent channel noise in C-level Pillow code.
    noise_r = Image.effect_noise((width, height), 64.0).convert('L').point(RANDOM_NOISE_LUT)
    noise_g = Image.effect_noise((width, height), 64.0).convert('L').point(RANDOM_NOISE_LUT)
    noise_b = Image.effect_noise((width, height), 64.0).convert('L').point(RANDOM_NOISE_LUT)
    noise_rgb = Image.merge('RGB', (noise_r, noise_g, noise_b))

    # Add centered noise to the source image: (img + noise - 128), clamped.
    return ImageChops.add(img, noise_rgb, scale=1.0, offset=-128)


def halftone_dither(image: Image.Image, palette: List[int], max_colors: Optional[int] = None) -> Image.Image:
    """Apply clustered-dot halftone dithering using an 8x8 threshold matrix."""
    # Keep signature compatible with earlier implementation.
    del palette, max_colors
    return _apply_threshold_pattern(image, tile_size=8, threshold_lut=HALFTONE_THRESHOLD_LUT)


def process_alpha_channel(image: Image.Image, alpha_mode: int, alpha_dither: int, 
                         alpha_color: Tuple[int, int, int], palette: List[int]) -> Image.Image:
    """Process alpha channel according to specified mode"""
    # Alpha conversion is palette-independent; keep signature compatibility.
    del palette

    if image.mode != 'RGBA':
        return image.convert('RGB')

    rgb_img = image.convert('RGB')
    alpha_channel = image.getchannel('A')
    transparent_img = Image.new('RGB', image.size, (0, 0, 255))

    if alpha_mode == 0:  # Clipped alpha
        transparent_mask = alpha_channel.point(ALPHA_TRANSPARENT_MASK_LUT)
        return Image.composite(transparent_img, rgb_img, transparent_mask)
    
    elif alpha_mode == 1:  # Dithered alpha
        if alpha_dither == 0:  # Floyd-Steinberg for alpha
            opaque_mask = alpha_channel.convert('1', dither=Image.Dither.FLOYDSTEINBERG).convert('L')
        else:  # Ordered dithering for alpha
            opaque_mask = alpha_channel.convert('1', dither=ORDERED_ALPHA_DITHER).convert('L')
        return Image.composite(rgb_img, transparent_img, opaque_mask)
    
    elif alpha_mode == 2:  # Replace alpha with color
        replacement_img = Image.new('RGB', image.size, alpha_color)
        transparent_mask = alpha_channel.point(ALPHA_TRANSPARENT_MASK_LUT)
        return Image.composite(replacement_img, rgb_img, transparent_mask)

    return rgb_img


def convert_to_palette(image: Image.Image, palette: List[int], max_colors: Optional[int] = None) -> bytes:
    """Convert RGB image to palette indices"""
    img = image.convert('RGB')
    palette_image, index_remap_table = _resolve_palette_quantization_resources(
        palette,
        max_colors=max_colors,
    )
    quantized = img.quantize(palette=palette_image, dither=Image.Dither.NONE)
    return _palette_bytes_from_quantized_image(quantized, index_remap_table)


def create_wad_header(num_textures: int, directory_offset: int, wad_type: int = 2) -> bytes:
    """Create WAD file header"""
    # WAD2 format (Quake): magic (4 bytes), num_textures (4 bytes), directory_offset (4 bytes)
    # WAD3 format (Half-Life): same structure but different magic and includes palettes
    magic = b'WAD2' if wad_type == 2 else b'WAD3'
    return struct.pack('<4sII', magic, num_textures, directory_offset)


def create_texture_entry(name: str, width: int, height: int, data: bytes, offset: int, wad_type: int = 2) -> Tuple[bytes, bytes]:
    """Create texture data and directory entry"""
    # Ensure name is 16 bytes (null-padded)
    texture_name = name[:15].encode('ascii')
    texture_name = texture_name + b'\x00' * (16 - len(texture_name))
    
    # Mipmap data
    mip0_size = width * height
    mip1_size = (width // 2) * (height // 2)
    mip2_size = (width // 4) * (height // 4)
    mip3_size = (width // 8) * (height // 8)
    
    # Create mipmap levels (simplified - just using scaled versions)
    mip0 = data
    mip1 = data[:mip1_size] if len(data) >= mip1_size else data * (mip1_size // len(data) + 1)
    mip1 = mip1[:mip1_size]
    mip2 = data[:mip2_size] if len(data) >= mip2_size else data * (mip2_size // len(data) + 1)
    mip2 = mip2[:mip2_size]
    mip3 = data[:mip3_size] if len(data) >= mip3_size else data * (mip3_size // len(data) + 1)
    mip3 = mip3[:mip3_size]
    
    # Texture header
    header_size = 40  # Size of miptex header
    mip0_offset = header_size
    mip1_offset = mip0_offset + mip0_size
    mip2_offset = mip1_offset + mip1_size
    mip3_offset = mip2_offset + mip2_size
    
    texture_header = struct.pack('<16sIIIIII',
        texture_name,
        width,
        height,
        mip0_offset,
        mip1_offset,
        mip2_offset,
        mip3_offset
    )
    
    # WAD2 (Quake) doesn't include palette data with each texture
    # WAD3 (Half-Life) includes palette data after the mipmaps
    if wad_type == 3:
        # For WAD3, add palette data (2 bytes for palette size + palette)
        palette_size = struct.pack('<H', 256)
        palette_data = bytes(QUAKE_PROCESS_PALETTE)
        texture_data = texture_header + mip0 + mip1 + mip2 + mip3 + palette_size + palette_data
        type_byte = 0x43  # Type for WAD3 miptex
    else:
        # For WAD2, no palette data
        texture_data = texture_header + mip0 + mip1 + mip2 + mip3
        type_byte = 0x44  # Type for WAD2 miptex
    
    # Directory entry
    # Offset (4), DiskSize (4), Size (4), Type (1), Compression (1), Padding (2), Name (16)
    directory_entry = struct.pack('<IIIBBB',
        offset,  # File position
        len(texture_data),  # Size on disk
        len(texture_data),  # Size when uncompressed
        type_byte,  # Type (0x44 for WAD2, 0x43 for WAD3)
        0,     # Compression (0 = none)
        0      # Padding byte 1
    ) + struct.pack('<B', 0) + texture_name  # Padding byte 2 + texture name
    
    return texture_data, directory_entry


def create_wad(textures: List[Tuple[str, int, int, bytes]], output_path: str, wad_type: int = 2):
    """Create a WAD file from texture data"""
    # Calculate offsets
    header_size = 12
    current_offset = header_size
    
    texture_data_list = []
    directory_entries = []
    
    for name, width, height, data in textures:
        texture_data, directory_entry = create_texture_entry(name, width, height, data, current_offset, wad_type)
        texture_data_list.append(texture_data)
        directory_entries.append(directory_entry)
        current_offset += len(texture_data)
    
    # Directory starts after all texture data
    directory_offset = current_offset
    
    # Write WAD file
    with open(output_path, 'wb') as f:
        # Write header
        f.write(create_wad_header(len(textures), directory_offset, wad_type))
        
        # Write texture data
        for texture_data in texture_data_list:
            f.write(texture_data)
        
        # Write directory
        for directory_entry in directory_entries:
            f.write(directory_entry)
    
    wad_format = "WAD2 (Quake)" if wad_type == 2 else "WAD3 (Half-Life)"
    print(f"Created {wad_format} file: {output_path} with {len(textures)} texture(s)")


def process_image(image_path: str, dithering: int, alpha_mode: int,
                 alpha_dither: int, alpha_color: Tuple[int, int, int],
                 telemetry: Optional[dict] = None,
                 palette_mode: Optional[str] = PALETTE_MODE_NO_FULLBRIGHTS,
                 custom_palette: Optional[List[int]] = None,
                 include_fullbrights: bool = False) -> Tuple[str, int, int, bytes]:
    """Process a single image file"""
    texture_name = Path(image_path).stem
    timings = {
        'open_seconds': 0.0,
        'decode_seconds': 0.0,
        'alpha_seconds': 0.0,
        'dither_seconds': 0.0,
        'palette_seconds': 0.0,
        'total_seconds': 0.0,
    }
    total_start = time.perf_counter()

    try:
        stage_start = time.perf_counter()
        img = Image.open(image_path)
        timings['open_seconds'] = time.perf_counter() - stage_start

        # Force eager decode so file IO/decompression can be timed separately.
        stage_start = time.perf_counter()
        img.load()
        timings['decode_seconds'] = time.perf_counter() - stage_start
        
        (
            resolved_palette_mode,
            process_palette,
            process_color_count,
            process_palette_image,
            process_index_remap_table,
        ) = resolve_process_palette(
            palette_mode,
            custom_palette=custom_palette,
            include_fullbrights=include_fullbrights,
        )
        dithering_index = resolve_dithering_index(dithering)

        # Process alpha channel if present
        stage_start = time.perf_counter()
        if img.mode == 'RGBA':
            img = process_alpha_channel(img, alpha_mode, alpha_dither, alpha_color, process_palette)
        else:
            img = img.convert('RGB')
        timings['alpha_seconds'] = time.perf_counter() - stage_start

        # Apply dithering/quantization and produce palette indices.
        width, height = img.size
        if dithering_index == DITHERING_INDEX_ERROR_DIFFUSION:
            # Fast C-level quantization with Quake palette + Floyd-Steinberg.
            stage_start = time.perf_counter()
            quantized = img.quantize(palette=process_palette_image, dither=Image.Dither.FLOYDSTEINBERG)
            timings['dither_seconds'] = time.perf_counter() - stage_start

            stage_start = time.perf_counter()
            palette_data = quantized.tobytes()
            if process_index_remap_table is not None:
                palette_data = palette_data.translate(process_index_remap_table)
            timings['palette_seconds'] = time.perf_counter() - stage_start
        elif dithering_index == DITHERING_INDEX_CLOSEST_COLOR:
            # No dithering: map each pixel to the closest available palette entry.
            stage_start = time.perf_counter()
            quantized = img.quantize(palette=process_palette_image, dither=Image.Dither.NONE)
            timings['dither_seconds'] = time.perf_counter() - stage_start

            stage_start = time.perf_counter()
            palette_data = quantized.tobytes()
            if process_index_remap_table is not None:
                palette_data = palette_data.translate(process_index_remap_table)
            timings['palette_seconds'] = time.perf_counter() - stage_start
        elif dithering_index == DITHERING_INDEX_RANDOM:
            # Fast random dithering: add noise in RGB space, then quantize with no pattern dither.
            stage_start = time.perf_counter()
            noisy_img = random_dither(img, process_palette, max_colors=process_color_count)
            timings['dither_seconds'] = time.perf_counter() - stage_start

            stage_start = time.perf_counter()
            quantized = noisy_img.quantize(palette=process_palette_image, dither=Image.Dither.NONE)
            palette_data = quantized.tobytes()
            if process_index_remap_table is not None:
                palette_data = palette_data.translate(process_index_remap_table)
            timings['palette_seconds'] = time.perf_counter() - stage_start
        else:
            stage_start = time.perf_counter()
            if dithering_index == DITHERING_INDEX_ORDERED:
                img = ordered_dither(img, process_palette, max_colors=process_color_count)
            elif dithering_index == DITHERING_INDEX_HALFTONE:
                img = halftone_dither(img, process_palette, max_colors=process_color_count)
            else:
                img = ordered_dither(img, process_palette, max_colors=process_color_count)
            timings['dither_seconds'] = time.perf_counter() - stage_start

            stage_start = time.perf_counter()
            quantized = img.quantize(palette=process_palette_image, dither=Image.Dither.NONE)
            palette_data = _palette_bytes_from_quantized_image(quantized, process_index_remap_table)
            timings['palette_seconds'] = time.perf_counter() - stage_start

        timings['total_seconds'] = time.perf_counter() - total_start

        if telemetry is not None:
            telemetry.clear()
            telemetry.update(timings)
            telemetry.update({
                'image_path': image_path,
                'texture_name': texture_name,
                'width': width,
                'height': height,
                'pixel_count': width * height,
                'dithering_mode': dithering_index,
                'dithering_label': DITHERING_LABELS.get(dithering_index, 'Error Diffusion'),
                'alpha_mode': alpha_mode,
                'palette_mode': resolved_palette_mode,
                'include_fullbrights': bool(include_fullbrights),
            })
        
        return (texture_name, width, height, palette_data)
    
    except Exception as e:
        timings['total_seconds'] = time.perf_counter() - total_start
        if telemetry is not None:
            telemetry.clear()
            telemetry.update(timings)
            telemetry.update({
                'image_path': image_path,
                'texture_name': texture_name,
                'dithering_mode': resolve_dithering_index(dithering),
                'alpha_mode': alpha_mode,
                'palette_mode': palette_mode,
                'include_fullbrights': bool(include_fullbrights),
                'error': str(e),
            })
        print(f"Error processing {image_path}: {e}")
        return None


def extract_textures_from_bsp(bsp_path: str) -> List[Tuple[str, int, int, bytes]]:
    """Extract textures from a Quake/Half-Life BSP file"""
    textures = []
    
    try:
        with open(bsp_path, 'rb') as f:
            # Read first 4 bytes to check format
            magic = f.read(4)
            
            # Check if it's BSP2 format (modern extended format)
            if magic == b'BSP2':
                # BSP2 files store the lump table directly after the 4-byte magic.
                # They do not include a separate numeric version field.
                print("BSP2 format detected")
                # Lump 2 is the texture lump (same index as classic Quake BSP).
                lump_offset = 4 + 2 * 8
                f.seek(lump_offset)
                tex_offset = struct.unpack('<I', f.read(4))[0]
                tex_length = struct.unpack('<I', f.read(4))[0]
            else:
                # Traditional BSP format (BSP29/BSP30) - first 4 bytes are version number
                f.seek(0)
                version = struct.unpack('<I', f.read(4))[0]
                
                # Support for BSP versions 29 (Quake) and 30 (Half-Life/GoldSrc)
                if version not in [29, 30]:
                    print(f"Warning: Unknown BSP version {version}, attempting to parse anyway...")
                
                # Read texture lump info (lump 2 for Quake/Half-Life)
                lump_offset = 4 + 2 * 8  # Version (4 bytes) + lump index (2) * 8 bytes per lump entry
                f.seek(lump_offset)
                
                tex_offset = struct.unpack('<I', f.read(4))[0]
                tex_length = struct.unpack('<I', f.read(4))[0]
            
            if tex_offset == 0 or tex_length == 0:
                print(f"No texture data found in BSP file")
                return textures
            
            # Read texture data
            f.seek(tex_offset)
            num_textures = struct.unpack('<I', f.read(4))[0]
            
            print(f"Found {num_textures} texture(s) in BSP file")
            
            # Read texture offsets
            tex_offsets = []
            for i in range(num_textures):
                offset = struct.unpack('<I', f.read(4))[0]
                tex_offsets.append(offset)
            
            # Read each texture
            for i, offset in enumerate(tex_offsets):
                if offset == -1 or offset == 0xFFFFFFFF:
                    # External texture reference
                    continue
                
                f.seek(tex_offset + offset)
                
                # Read texture header (miptex structure)
                name_bytes = f.read(16)
                name = name_bytes.split(b'\x00')[0].decode('ascii', errors='ignore')
                
                width = struct.unpack('<I', f.read(4))[0]
                height = struct.unpack('<I', f.read(4))[0]
                
                mip0_offset = struct.unpack('<I', f.read(4))[0]
                mip1_offset = struct.unpack('<I', f.read(4))[0]
                mip2_offset = struct.unpack('<I', f.read(4))[0]
                mip3_offset = struct.unpack('<I', f.read(4))[0]
                
                # Read mipmap 0 data (full resolution)
                if mip0_offset > 0:
                    f.seek(tex_offset + offset + mip0_offset)
                    data_size = width * height
                    palette_data = f.read(data_size)
                    
                    if len(palette_data) == data_size:
                        textures.append((name, width, height, palette_data))
                        print(f"  Extracted: {name} ({width}x{height})")
                    else:
                        print(f"  Warning: Incomplete data for texture {name}")
                else:
                    print(f"  Warning: No mipmap data for texture {name}")
    
    except Exception as e:
        print(f"Error reading BSP file: {e}")
        import traceback
        traceback.print_exc()
    
    return textures


def find_images(input_path: str) -> List[str]:
    """Find all image files in the input path"""
    image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tga', '.tif', '.tiff'}
    image_files = []
    
    path = Path(input_path)
    
    if path.is_file():
        if path.suffix.lower() in image_extensions:
            image_files.append(str(path))
    elif path.is_dir():
        for ext in image_extensions:
            image_files.extend([str(f) for f in path.glob(f'*{ext}')])
            image_files.extend([str(f) for f in path.glob(f'*{ext.upper()}')])
    
    return sorted(image_files)


def palette_to_image(width: int, height: int, palette_data: bytes, palette: List[int], has_embedded_palette: bool = False) -> Image.Image:
    """Convert palette indices to RGB image"""
    # If the texture has an embedded palette (WAD3), use it instead
    if has_embedded_palette and len(palette_data) > width * height:
        # Extract embedded palette from the end of the data
        embedded_palette_start = width * height
        embedded_palette = list(palette_data[embedded_palette_start:embedded_palette_start + 768])
        palette = embedded_palette if len(embedded_palette) == 768 else palette
        # Use only the texture data
        palette_data = palette_data[:width * height]

    expected_size = width * height
    if len(palette_data) < expected_size:
        palette_data = palette_data + (b'\x00' * (expected_size - len(palette_data)))
    elif len(palette_data) > expected_size:
        palette_data = palette_data[:expected_size]

    paletted = Image.frombytes('P', (width, height), palette_data)
    pil_palette, _ = _normalize_palette(palette, 256)
    paletted.putpalette(pil_palette)
    return paletted.convert('RGB')


def read_textures_from_wad(wad_path: str) -> List[Tuple[str, int, int, bytes]]:
    """Read mip textures from a WAD file and return raw texture entries."""
    textures: List[Tuple[str, int, int, bytes]] = []

    try:
        with open(wad_path, 'rb') as f:
            magic = f.read(4)
            if magic not in [b'WAD2', b'WAD3']:
                print(f"Error: Not a valid WAD file (magic: {magic}) in {wad_path}")
                return textures

            num_textures = struct.unpack('<I', f.read(4))[0]
            directory_offset = struct.unpack('<I', f.read(4))[0]

            f.seek(directory_offset)
            entries = []

            for _ in range(num_textures):
                offset = struct.unpack('<I', f.read(4))[0]
                disk_size = struct.unpack('<I', f.read(4))[0]
                _size = struct.unpack('<I', f.read(4))[0]
                type_byte = struct.unpack('<B', f.read(1))[0]
                _compression = struct.unpack('<B', f.read(1))[0]
                _padding = struct.unpack('<H', f.read(2))[0]
                name_bytes = f.read(16)
                name = name_bytes.split(b'\x00')[0].decode('ascii', errors='ignore')
                entries.append((name, offset, disk_size, type_byte))

            for dir_name, offset, disk_size, type_byte in entries:
                # Merge mode only considers miptex entries.
                if type_byte not in [0x43, 0x44]:
                    continue

                try:
                    f.seek(offset)

                    name_bytes = f.read(16)
                    header_name = name_bytes.split(b'\x00')[0].decode('ascii', errors='ignore')
                    name = header_name if header_name else dir_name

                    width = struct.unpack('<I', f.read(4))[0]
                    height = struct.unpack('<I', f.read(4))[0]

                    mip0_offset = struct.unpack('<I', f.read(4))[0]
                    _mip1_offset = struct.unpack('<I', f.read(4))[0]
                    _mip2_offset = struct.unpack('<I', f.read(4))[0]
                    _mip3_offset = struct.unpack('<I', f.read(4))[0]

                    if width <= 0 or height <= 0 or width > 4096 or height > 4096:
                        print(f"  Warning: Skipping invalid texture dimensions for {name} ({width}x{height})")
                        continue

                    if mip0_offset == 0 or mip0_offset > disk_size:
                        print(f"  Warning: Skipping invalid mipmap offset for {name}")
                        continue

                    data_size = width * height
                    f.seek(offset + mip0_offset)
                    palette_data = f.read(data_size)

                    if len(palette_data) != data_size:
                        print(f"  Warning: Incomplete data for texture {name}")
                        continue

                    textures.append((name, width, height, palette_data))
                except Exception as e:
                    print(f"  Warning: Could not read texture {dir_name}: {e}")
                    continue

    except Exception as e:
        print(f"Error reading WAD file {wad_path}: {e}")

    return textures


def merge_wad_inputs(input_wads: List[str], output_path: str, wad_type: int = 2) -> int:
    """Merge multiple WAD files into a single deduplicated WAD."""
    deduped_textures: dict[str, Tuple[str, int, int, bytes]] = {}
    scanned_count = 0
    duplicate_count = 0
    conflict_count = 0

    for index, wad_path in enumerate(input_wads, 1):
        print(f"\n[{index}/{len(input_wads)}] Reading WAD: {wad_path}")
        textures = read_textures_from_wad(wad_path)
        print(f"  Found {len(textures)} texture(s) in mergeable format")

        for name, width, height, palette_data in textures:
            scanned_count += 1
            normalized_name = name[:15].lower()
            normalized_entry_name = name[:15]

            existing = deduped_textures.get(normalized_name)
            if existing is None:
                deduped_textures[normalized_name] = (
                    normalized_entry_name,
                    width,
                    height,
                    palette_data,
                )
                continue

            existing_name, existing_w, existing_h, existing_data = existing
            if existing_w == width and existing_h == height and existing_data == palette_data:
                duplicate_count += 1
            else:
                conflict_count += 1
                print(
                    f"  Warning: Name conflict for texture '{normalized_entry_name}' in {wad_path}; "
                    f"keeping first occurrence '{existing_name}'"
                )

    if not deduped_textures:
        print("Error: No mergeable textures were found in the provided WAD files")
        return 1

    if not output_path.endswith('.wad'):
        output_path += '.wad'

    merged_textures = list(deduped_textures.values())
    create_wad(merged_textures, output_path, wad_type)

    print("\nMerge summary:")
    print(f"  Input WAD files: {len(input_wads)}")
    print(f"  Textures scanned: {scanned_count}")
    print(f"  Unique textures written: {len(merged_textures)}")
    print(f"  Exact duplicates skipped: {duplicate_count}")
    print(f"  Name conflicts skipped: {conflict_count}")

    return 0


def extract_textures_from_wad(wad_path: str, output_dir: str = None) -> int:
    """Extract textures from a WAD file and save as PNG images"""
    if output_dir is None:
        # Default to WAD filename without extension
        output_dir = Path(wad_path).stem
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    extracted_count = 0
    
    try:
        with open(wad_path, 'rb') as f:
            # Read WAD header
            magic = f.read(4)
            if magic not in [b'WAD2', b'WAD3']:
                print(f"Error: Not a valid WAD file (magic: {magic})")
                return 0
            
            wad_type = 2 if magic == b'WAD2' else 3
            print(f"Reading {magic.decode('ascii')} file: {wad_path}")
            
            num_textures = struct.unpack('<I', f.read(4))[0]
            directory_offset = struct.unpack('<I', f.read(4))[0]
            
            print(f"Found {num_textures} texture(s)")
            
            # Read directory entries
            f.seek(directory_offset)
            textures = []
            
            for i in range(num_textures):
                offset = struct.unpack('<I', f.read(4))[0]
                disk_size = struct.unpack('<I', f.read(4))[0]
                size = struct.unpack('<I', f.read(4))[0]
                type_byte = struct.unpack('<B', f.read(1))[0]
                compression = struct.unpack('<B', f.read(1))[0]
                padding = struct.unpack('<H', f.read(2))[0]
                name_bytes = f.read(16)
                name = name_bytes.split(b'\x00')[0].decode('ascii', errors='ignore')
                
                textures.append((name, offset, disk_size, type_byte))
            
            # Extract each texture
            for name, offset, disk_size, type_byte in textures:
                try:
                    f.seek(offset)
                    
                    # Check texture type
                    if type_byte == 0x42:
                        # QPIC format (UI graphics) - different structure
                        # QPIC: width (4), height (4), data (width*height)
                        width = struct.unpack('<I', f.read(4))[0]
                        height = struct.unpack('<I', f.read(4))[0]
                        
                        # Validate dimensions
                        if width <= 0 or height <= 0 or width > 4096 or height > 4096:
                            print(f"  Skipped: {name} (invalid QPIC dimensions: {width}x{height})")
                            continue
                        
                        data_size = width * height
                        texture_data = f.read(data_size)
                        palette = QUAKE_PALETTE
                        
                    elif type_byte in [0x43, 0x44]:
                        # Miptex format (textures) - standard mipmap structure
                        # Read texture header
                        name_bytes = f.read(16)
                        width = struct.unpack('<I', f.read(4))[0]
                        height = struct.unpack('<I', f.read(4))[0]
                        
                        # Validate dimensions
                        if width <= 0 or height <= 0 or width > 4096 or height > 4096:
                            print(f"  Skipped: {name} (invalid dimensions: {width}x{height})")
                            continue
                        
                        mip0_offset = struct.unpack('<I', f.read(4))[0]
                        mip1_offset = struct.unpack('<I', f.read(4))[0]
                        mip2_offset = struct.unpack('<I', f.read(4))[0]
                        mip3_offset = struct.unpack('<I', f.read(4))[0]
                        
                        # Validate mipmap offset
                        if mip0_offset == 0 or mip0_offset > disk_size:
                            print(f"  Skipped: {name} (invalid mipmap offset)")
                            continue
                        
                        # Read mipmap 0 data (full resolution)
                        f.seek(offset + mip0_offset)
                        data_size = width * height
                        
                        # For WAD3, also read palette if present
                        if type_byte == 0x43:  # WAD3 format
                            # Calculate position of palette (after all mipmaps)
                            mip1_size = (width // 2) * (height // 2)
                            mip2_size = (width // 4) * (height // 4)
                            mip3_size = (width // 8) * (height // 8)
                            palette_pos = offset + mip3_offset + mip3_size
                            
                            # Read texture data
                            texture_data = f.read(data_size)
                            
                            # Read embedded palette
                            f.seek(palette_pos)
                            palette_size_marker = struct.unpack('<H', f.read(2))[0]
                            if palette_size_marker == 256:
                                embedded_palette = list(f.read(768))
                                palette = embedded_palette
                            else:
                                palette = QUAKE_PALETTE
                        else:
                            texture_data = f.read(data_size)
                            palette = QUAKE_PALETTE
                    else:
                        print(f"  Skipped: {name} (unknown type: 0x{type_byte:02x})")
                        continue
                    
                    # Convert to image
                    img = palette_to_image(width, height, texture_data, palette)
                    
                    # Save as PNG
                    output_file = output_path / f"{name}.png"
                    img.save(output_file, 'PNG')
                    print(f"  Saved: {output_file} ({width}x{height})")
                    extracted_count += 1
                    
                except Exception as e:
                    print(f"  Error extracting {name}: {e}")
                    continue
    
    except Exception as e:
        print(f"Error extracting from WAD file: {e}")
        import traceback
        traceback.print_exc()
        return extracted_count
    
    print(f"\nExtracted {extracted_count} texture(s) to: {output_path}")
    return extracted_count


def expand_input_paths(input_args: List[str]) -> Tuple[List[str], List[str]]:
    """Expand wildcard patterns and return unique input paths plus unmatched patterns."""
    expanded: List[str] = []
    unmatched_patterns: List[str] = []

    for input_arg in input_args:
        if any(char in input_arg for char in '*?[]'):
            matches = sorted(glob.glob(input_arg))
            if matches:
                expanded.extend(matches)
            else:
                unmatched_patterns.append(input_arg)
        else:
            expanded.append(input_arg)

    unique_inputs: List[str] = []
    seen = set()
    for input_path in expanded:
        normalized = str(Path(input_path))
        if normalized not in seen:
            seen.add(normalized)
            unique_inputs.append(normalized)

    return unique_inputs, unmatched_patterns


def process_single_input(input_value: str, args: argparse.Namespace,
                         alpha_color: Tuple[int, int, int],
                         output_override: Optional[str] = None) -> int:
    """Process one input item and either extract or create a WAD."""
    input_path = Path(input_value)

    if input_path.is_file() and input_path.suffix.lower() == '.wad':
        # Extract textures from WAD file to PNG images.
        output_dir = output_override if output_override else None
        extracted = extract_textures_from_wad(input_value, output_dir)
        return 0 if extracted > 0 else 1

    textures = []

    if input_path.is_file() and input_path.suffix.lower() == '.bsp':
        # Extract textures from BSP file.
        print(f"Extracting textures from BSP file: {input_value}")
        textures = extract_textures_from_bsp(input_value)
    else:
        # Find input images from a file or directory.
        image_files = find_images(input_value)

        if not image_files:
            print(f"Error: No images found in {input_value}")
            return 1

        print(f"Found {len(image_files)} image(s) to process")

        for image_file in image_files:
            print(f"Processing: {image_file}")
            result = process_image(
                image_file,
                args.dithering,
                args.alpha,
                args.alphadither,
                alpha_color
            )
            if result:
                textures.append(result)

    if not textures:
        print("Error: No textures were successfully processed")
        return 1

    if output_override:
        output_path = output_override
    else:
        if input_path.is_dir():
            output_path = f"{input_path.name}.wad"
        else:
            output_path = f"{input_path.stem}.wad"

    if not output_path.endswith('.wad'):
        output_path += '.wad'

    create_wad(textures, output_path, args.type)
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Quake WAD Tools - Convert images to/from Quake WAD format',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('-i', '--input', required=True, nargs='+',
                       help='Input file(s), folder(s), or wildcard pattern(s) (images/WAD/BSP)')
    parser.add_argument('-o', '--output', default='',
                       help='Output filename or directory (optional, auto-generated if not specified). Use with multiple WAD inputs to create one merged WAD.')
    parser.add_argument('--dithering', type=int, choices=[0, 1, 2, 3, 4], default=0,
                       help='Dithering mode: 0=Error Diffusion (Floyd-Steinberg, default), 1=Ordered, 2=Random, 3=Halftone, 4=Closest Color Available')
    parser.add_argument('--alpha', type=int, choices=[0, 1, 2], default=0,
                       help='Alpha mode: 0=Clipped (default), 1=Dithered, 2=Replace with color')
    parser.add_argument('--alphadither', type=int, choices=[0, 1], default=0,
                       help='Alpha dithering (for --alpha 1): 0=Floyd-Steinberg (default), 1=Ordered')
    parser.add_argument('--alphacolor', default='#000000',
                       help='Alpha replacement color (for --alpha 2): hex format #RRGGBB (default: #000000)')
    parser.add_argument('--type', type=int, choices=[2, 3], default=2,
                       help='WAD format type: 2=WAD2/Quake (default), 3=WAD3/Half-Life')
    
    args = parser.parse_args()
    
    # Parse alpha color
    try:
        alpha_color = hex_to_rgb(args.alphacolor)
    except:
        print(f"Error: Invalid alpha color format: {args.alphacolor}")
        return 1
    
    input_values, unmatched_patterns = expand_input_paths(args.input)

    if unmatched_patterns:
        for pattern in unmatched_patterns:
            print(f"Error: Input pattern did not match any files: {pattern}")
        return 1

    if not input_values:
        print("Error: No input files or folders were provided")
        return 1

    all_inputs_are_wad_files = (
        len(input_values) > 1 and
        all(Path(value).is_file() and Path(value).suffix.lower() == '.wad' for value in input_values)
    )

    if all_inputs_are_wad_files and args.output:
        merge_output_path = args.output if args.output.endswith('.wad') else f"{args.output}.wad"
        output_resolved = str(Path(merge_output_path).resolve())
        merge_inputs = [
            value for value in input_values
            if str(Path(value).resolve()) != output_resolved
        ]

        if len(merge_inputs) != len(input_values):
            print(f"Note: Skipping output file from input set: {merge_output_path}")

        if not merge_inputs:
            print("Error: No merge inputs remain after excluding output file")
            return 1

        return merge_wad_inputs(merge_inputs, merge_output_path, args.type)

    if len(input_values) > 1 and args.output:
        print("Error: --output with multiple --input values is only supported when all inputs are WAD files")
        print("Tip: use .wad inputs to merge into one output, or omit --output for per-input auto naming")
        return 1

    failures = 0
    for index, input_value in enumerate(input_values, 1):
        if len(input_values) > 1:
            print(f"\n[{index}/{len(input_values)}] Processing: {input_value}")

        output_override = args.output if len(input_values) == 1 else None
        result = process_single_input(input_value, args, alpha_color, output_override)
        if result != 0:
            failures += 1

    if len(input_values) > 1:
        succeeded = len(input_values) - failures
        print(f"\nCompleted: {succeeded} succeeded, {failures} failed")

    return 0 if failures == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
