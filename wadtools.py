#!/usr/bin/env python3
"""
Quake WAD Tools - Image to WAD conversion utility
Converts images to Quake WAD format with various dithering and alpha options
"""

import argparse
import sys
import os
from pathlib import Path
from typing import List, Tuple, Optional
import struct

try:
    from PIL import Image
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


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color string to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def find_closest_color(rgb: Tuple[int, int, int], palette: List[int]) -> int:
    """Find the closest color index in the palette"""
    min_distance = float('inf')
    closest_index = 0
    
    r, g, b = rgb
    for i in range(256):
        pr = palette[i * 3]
        pg = palette[i * 3 + 1]
        pb = palette[i * 3 + 2]
        
        # Euclidean distance in RGB space
        distance = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        
        if distance < min_distance:
            min_distance = distance
            closest_index = i
    
    return closest_index


def floyd_steinberg_dither(image: Image.Image, palette: List[int]) -> Image.Image:
    """Apply Floyd-Steinberg dithering to an image"""
    img = image.convert('RGB')
    pixels = img.load()
    width, height = img.size
    
    # Create error diffusion buffer
    errors = [[(0, 0, 0) for _ in range(width)] for _ in range(height)]
    
    for y in range(height):
        for x in range(width):
            old_pixel = pixels[x, y]
            
            # Add accumulated error
            r = max(0, min(255, old_pixel[0] + errors[y][x][0]))
            g = max(0, min(255, old_pixel[1] + errors[y][x][1]))
            b = max(0, min(255, old_pixel[2] + errors[y][x][2]))
            
            # Find closest palette color
            index = find_closest_color((r, g, b), palette)
            new_pixel = (palette[index * 3], palette[index * 3 + 1], palette[index * 3 + 2])
            pixels[x, y] = new_pixel
            
            # Calculate quantization error
            err_r = r - new_pixel[0]
            err_g = g - new_pixel[1]
            err_b = b - new_pixel[2]
            
            # Distribute error to neighboring pixels
            if x + 1 < width:
                errors[y][x + 1] = (
                    errors[y][x + 1][0] + err_r * 7 / 16,
                    errors[y][x + 1][1] + err_g * 7 / 16,
                    errors[y][x + 1][2] + err_b * 7 / 16
                )
            if y + 1 < height:
                if x > 0:
                    errors[y + 1][x - 1] = (
                        errors[y + 1][x - 1][0] + err_r * 3 / 16,
                        errors[y + 1][x - 1][1] + err_g * 3 / 16,
                        errors[y + 1][x - 1][2] + err_b * 3 / 16
                    )
                errors[y + 1][x] = (
                    errors[y + 1][x][0] + err_r * 5 / 16,
                    errors[y + 1][x][1] + err_g * 5 / 16,
                    errors[y + 1][x][2] + err_b * 5 / 16
                )
                if x + 1 < width:
                    errors[y + 1][x + 1] = (
                        errors[y + 1][x + 1][0] + err_r * 1 / 16,
                        errors[y + 1][x + 1][1] + err_g * 1 / 16,
                        errors[y + 1][x + 1][2] + err_b * 1 / 16
                    )
    
    return img


def ordered_dither(image: Image.Image, palette: List[int]) -> Image.Image:
    """Apply ordered (Bayer matrix) dithering to an image"""
    # 4x4 Bayer matrix
    bayer_matrix = [
        [0, 8, 2, 10],
        [12, 4, 14, 6],
        [3, 11, 1, 9],
        [15, 7, 13, 5]
    ]
    
    img = image.convert('RGB')
    pixels = img.load()
    width, height = img.size
    
    for y in range(height):
        for x in range(width):
            old_pixel = pixels[x, y]
            
            # Apply threshold from Bayer matrix
            threshold = (bayer_matrix[y % 4][x % 4] - 7.5) / 16.0 * 255
            
            r = max(0, min(255, old_pixel[0] + threshold))
            g = max(0, min(255, old_pixel[1] + threshold))
            b = max(0, min(255, old_pixel[2] + threshold))
            
            # Find closest palette color
            index = find_closest_color((int(r), int(g), int(b)), palette)
            new_pixel = (palette[index * 3], palette[index * 3 + 1], palette[index * 3 + 2])
            pixels[x, y] = new_pixel
    
    return img


def process_alpha_channel(image: Image.Image, alpha_mode: int, alpha_dither: int, 
                         alpha_color: Tuple[int, int, int], palette: List[int]) -> Image.Image:
    """Process alpha channel according to specified mode"""
    if image.mode != 'RGBA':
        return image.convert('RGB')
    
    rgb_img = Image.new('RGB', image.size)
    pixels = image.load()
    new_pixels = rgb_img.load()
    width, height = image.size
    
    if alpha_mode == 0:  # Clipped alpha
        for y in range(height):
            for x in range(width):
                r, g, b, a = pixels[x, y]
                if a < 128:  # Transparent
                    new_pixels[x, y] = (0, 0, 255)  # Blue (index 255 in Quake palette is transparent)
                else:
                    new_pixels[x, y] = (r, g, b)
    
    elif alpha_mode == 1:  # Dithered alpha
        # Create error diffusion buffer for alpha channel
        if alpha_dither == 0:  # Floyd-Steinberg for alpha
            errors = [[0 for _ in range(width)] for _ in range(height)]
            
            for y in range(height):
                for x in range(width):
                    r, g, b, a = pixels[x, y]
                    
                    # Add accumulated error
                    a_adjusted = max(0, min(255, a + errors[y][x]))
                    
                    # Threshold with error diffusion
                    if a_adjusted >= 128:
                        new_pixels[x, y] = (r, g, b)
                        error = a_adjusted - 255
                    else:
                        new_pixels[x, y] = (0, 0, 255)
                        error = a_adjusted
                    
                    # Distribute error
                    if x + 1 < width:
                        errors[y][x + 1] += error * 7 / 16
                    if y + 1 < height:
                        if x > 0:
                            errors[y + 1][x - 1] += error * 3 / 16
                        errors[y + 1][x] += error * 5 / 16
                        if x + 1 < width:
                            errors[y + 1][x + 1] += error * 1 / 16
        else:  # Ordered dithering for alpha
            bayer_matrix = [
                [0, 8, 2, 10],
                [12, 4, 14, 6],
                [3, 11, 1, 9],
                [15, 7, 13, 5]
            ]
            
            for y in range(height):
                for x in range(width):
                    r, g, b, a = pixels[x, y]
                    threshold = (bayer_matrix[y % 4][x % 4] / 16.0) * 255
                    
                    if a >= threshold:
                        new_pixels[x, y] = (r, g, b)
                    else:
                        new_pixels[x, y] = (0, 0, 255)
    
    elif alpha_mode == 2:  # Replace alpha with color
        for y in range(height):
            for x in range(width):
                r, g, b, a = pixels[x, y]
                if a < 128:
                    new_pixels[x, y] = alpha_color
                else:
                    new_pixels[x, y] = (r, g, b)
    
    return rgb_img


def convert_to_palette(image: Image.Image, palette: List[int]) -> bytes:
    """Convert RGB image to palette indices"""
    img = image.convert('RGB')
    pixels = img.load()
    width, height = img.size
    
    indices = bytearray()
    for y in range(height):
        for x in range(width):
            rgb = pixels[x, y]
            index = find_closest_color(rgb, palette)
            indices.append(index)
    
    return bytes(indices)


def create_wad_header(num_textures: int, directory_offset: int) -> bytes:
    """Create WAD file header"""
    # WAD3 format: magic (4 bytes), num_textures (4 bytes), directory_offset (4 bytes)
    return struct.pack('<4sII', b'WAD3', num_textures, directory_offset)


def create_texture_entry(name: str, width: int, height: int, data: bytes, offset: int) -> Tuple[bytes, bytes]:
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
    
    # Palette data (2 bytes for palette size + palette)
    palette_size = struct.pack('<H', 256)
    palette_data = bytes(QUAKE_PALETTE)
    
    # Complete texture data
    texture_data = texture_header + mip0 + mip1 + mip2 + mip3 + palette_size + palette_data
    
    # Directory entry (WAD3 format)
    # Offset (4), DiskSize (4), Size (4), Type (1), Compression (1), Padding (2), Name (16)
    directory_entry = struct.pack('<IIIBBB',
        offset,  # File position
        len(texture_data),  # Size on disk
        len(texture_data),  # Size when uncompressed
        0x43,  # Type (0x43 = miptex)
        0,     # Compression (0 = none)
        0      # Padding byte 1
    ) + struct.pack('<B', 0) + texture_name  # Padding byte 2 + texture name
    
    return texture_data, directory_entry


def create_wad(textures: List[Tuple[str, int, int, bytes]], output_path: str):
    """Create a WAD file from texture data"""
    # Calculate offsets
    header_size = 12
    current_offset = header_size
    
    texture_data_list = []
    directory_entries = []
    
    for name, width, height, data in textures:
        texture_data, directory_entry = create_texture_entry(name, width, height, data, current_offset)
        texture_data_list.append(texture_data)
        directory_entries.append(directory_entry)
        current_offset += len(texture_data)
    
    # Directory starts after all texture data
    directory_offset = current_offset
    
    # Write WAD file
    with open(output_path, 'wb') as f:
        # Write header
        f.write(create_wad_header(len(textures), directory_offset))
        
        # Write texture data
        for texture_data in texture_data_list:
            f.write(texture_data)
        
        # Write directory
        for directory_entry in directory_entries:
            f.write(directory_entry)
    
    print(f"Created WAD file: {output_path} with {len(textures)} texture(s)")


def process_image(image_path: str, dithering: int, alpha_mode: int, 
                 alpha_dither: int, alpha_color: Tuple[int, int, int]) -> Tuple[str, int, int, bytes]:
    """Process a single image file"""
    try:
        img = Image.open(image_path)
        
        # Get texture name from filename (without extension)
        texture_name = Path(image_path).stem
        
        # Process alpha channel if present
        if img.mode == 'RGBA':
            img = process_alpha_channel(img, alpha_mode, alpha_dither, alpha_color, QUAKE_PALETTE)
        else:
            img = img.convert('RGB')
        
        # Apply dithering
        if dithering == 0:
            img = floyd_steinberg_dither(img, QUAKE_PALETTE)
        elif dithering == 1:
            img = ordered_dither(img, QUAKE_PALETTE)
        
        # Convert to palette indices
        width, height = img.size
        palette_data = convert_to_palette(img, QUAKE_PALETTE)
        
        return (texture_name, width, height, palette_data)
    
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return None


def extract_textures_from_bsp(bsp_path: str) -> List[Tuple[str, int, int, bytes]]:
    """Extract textures from a Quake/Half-Life BSP file"""
    textures = []
    
    try:
        with open(bsp_path, 'rb') as f:
            # Read BSP version
            version = struct.unpack('<I', f.read(4))[0]
            
            # Support for BSP versions 29 (Quake) and 30 (Half-Life/GoldSrc)
            if version not in [29, 30]:
                print(f"Warning: Unknown BSP version {version}, attempting to parse anyway...")
            
            # Read texture lump info (lump 2 for Quake, varies for Half-Life)
            # For GoldSrc BSP30, texture lump is at offset 4 + lump_index * 8
            # Lump 2 is textures for BSP29, lump 2 is also textures for BSP30
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


def main():
    parser = argparse.ArgumentParser(
        description='Quake WAD Tools - Convert images to Quake WAD format',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('-i', '--input', required=True,
                       help='Input file, folder, or file list')
    parser.add_argument('--output', default='',
                       help='Output WAD filename (optional, auto-generated if not specified)')
    parser.add_argument('--dithering', type=int, choices=[0, 1], default=0,
                       help='Dithering mode: 0=Floyd-Steinberg (default), 1=Ordered')
    parser.add_argument('--alpha', type=int, choices=[0, 1, 2], default=0,
                       help='Alpha mode: 0=Clipped (default), 1=Dithered, 2=Replace with color')
    parser.add_argument('--alphadither', type=int, choices=[0, 1], default=0,
                       help='Alpha dithering (for --alpha 1): 0=Floyd-Steinberg (default), 1=Ordered')
    parser.add_argument('--alphacolor', default='#000000',
                       help='Alpha replacement color (for --alpha 2): hex format #RRGGBB (default: #000000)')
    
    args = parser.parse_args()
    
    # Parse alpha color
    try:
        alpha_color = hex_to_rgb(args.alphacolor)
    except:
        print(f"Error: Invalid alpha color format: {args.alphacolor}")
        return 1
    
    # Check if input is a BSP file
    input_path = Path(args.input)
    textures = []
    
    if input_path.is_file() and input_path.suffix.lower() == '.bsp':
        # Extract textures from BSP file
        print(f"Extracting textures from BSP file: {args.input}")
        textures = extract_textures_from_bsp(args.input)
    else:
        # Find input images
        image_files = find_images(args.input)
        
        if not image_files:
            print(f"Error: No images found in {args.input}")
            return 1
        
        print(f"Found {len(image_files)} image(s) to process")
        
        # Process images
        for image_file in image_files:
            print(f"Processing: {image_file}")
            result = process_image(image_file, args.dithering, args.alpha, args.alphadither, alpha_color)
            if result:
                textures.append(result)
    
    if not textures:
        print("Error: No textures were successfully processed")
        return 1
    
    # Determine output filename
    if args.output:
        output_path = args.output
    else:
        input_path = Path(args.input)
        if input_path.is_dir():
            output_path = f"{input_path.name}.wad"
        else:
            output_path = f"{input_path.stem}.wad"
    
    # Ensure .wad extension
    if not output_path.endswith('.wad'):
        output_path += '.wad'
    
    # Create WAD file
    create_wad(textures, output_path)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
