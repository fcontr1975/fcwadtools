# Quake WAD Tools

A Python utility for converting images to Quake WAD (Where's All the Data) format and extracting textures from BSP files.

## Features

- Convert PNG, JPG, BMP, TGA, and other image formats to Quake WAD format
- Extract textures from Quake/Half-Life BSP files (BSP versions 29 and 30)
- Support for Floyd-Steinberg and ordered (Bayer matrix) dithering
- Multiple alpha channel handling modes (clipped, dithered, or color replacement)
- Automatic mipmap generation
- Batch processing of folders

## Installation

1. Install Python 3.6 or higher
2. Install dependencies:

```bash
pip install -r requirements.txt
```

Or install Pillow directly:

```bash
pip install Pillow
```

## Usage

### Basic Usage

Convert a single image:
```bash
python3 wadtools.py --input texture.png
```

Convert all images in a folder:
```bash
python3 wadtools.py --input /path/to/textures/
```

Extract textures from a BSP file:
```bash
python3 wadtools.py --input map.bsp
```

### Command Line Options

**Required:**
- `-i, --input`: Input file, folder, or BSP file

**Optional:**
- `--output`: Output WAD filename (auto-generated if not specified)
- `--dithering`: Dithering mode
  - `0`: Floyd-Steinberg dithering (default)
  - `1`: Ordered (Bayer matrix) dithering
- `--alpha`: Alpha channel handling mode
  - `0`: Clipped alpha - transparent pixels become index 255 (default)
  - `1`: Dithered alpha - apply dithering to alpha channel
  - `2`: Replace alpha with color
- `--alphadither`: Alpha dithering mode (used with `--alpha 1`)
  - `0`: Floyd-Steinberg (default)
  - `1`: Ordered
- `--alphacolor`: Alpha replacement color (used with `--alpha 2`)
  - Format: `#RRGGBB` (default: `#000000`)

### Examples

Convert with ordered dithering:
```bash
python3 wadtools.py --input textures/ --dithering 1
```

Convert with dithered alpha:
```bash
python3 wadtools.py --input logo.png --alpha 1 --alphadither 0
```

Convert with custom alpha color:
```bash
python3 wadtools.py --input texture.png --alpha 2 --alphacolor #FF00FF
```

Specify output filename:
```bash
python3 wadtools.py --input textures/ --output custom.wad
```

## How It Works

1. **Image Loading**: Loads images using PIL/Pillow
2. **Alpha Processing**: Handles transparency according to selected mode
3. **Dithering**: Applies Floyd-Steinberg or ordered dithering to reduce colors to Quake's 256-color palette
4. **Palette Conversion**: Maps RGB colors to closest Quake palette indices
5. **Mipmap Generation**: Creates 4 mipmap levels for each texture
6. **WAD Creation**: Writes textures to WAD3 format file

## Supported Image Formats

- PNG (recommended for alpha channel support)
- JPEG/JPG
- BMP
- TGA
- TIFF
- And other formats supported by PIL/Pillow

## WAD Format

This tool creates WAD3 format files compatible with:
- Quake
- Half-Life
- Other GoldSrc engine games

Each texture includes:
- 4 mipmap levels (full size, 1/2, 1/4, 1/8)
- 256-color palette
- Texture name (derived from filename)

## Notes

- Texture names are limited to 15 characters (derived from filename)
- Images are automatically converted to Quake's 256-color palette
- Transparent pixels (alpha < 128) are handled according to alpha mode
- For best results with transparency, use PNG format with alpha channel

## Troubleshooting

**Import Error: PIL/Pillow not found**
```bash
pip install Pillow
```

**No images found**
- Check that the input path is correct
- Ensure images have supported extensions (.png, .jpg, etc.)

**Texture quality issues**
- Try different dithering modes (`--dithering 0` vs `--dithering 1`)
- For images with transparency, experiment with alpha modes

## License

This tool is provided as-is for use with Quake and compatible games.

## References

- Quake palette specification
- WAD3 file format
- ericw-tools (Quake compilation tools)
