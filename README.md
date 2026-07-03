# Quake WAD Tools

A Python utility for converting images to/from Quake WAD (Where's All the Data) format.

## Features

- **Convert images to WAD**: PNG, JPG, BMP, TGA, and other image formats to Quake WAD format
- **Extract textures from WAD**: Export all textures from WAD files to lossless PNG images
- **Extract textures from BSP**: Extract embedded textures from Quake/Half-Life BSP files (BSP versions 29 and 30)
- **WAD2 and WAD3 support**: Create Quake (WAD2) or Half-Life (WAD3) format files
- **QPIC support**: Extract UI graphics (type 0x42) from WAD files
- **Dithering options**: Floyd-Steinberg and ordered (Bayer matrix) dithering
- **Alpha channel handling**: Multiple modes (clipped, dithered, or color replacement)
- **Automatic mipmap generation**: For texture WAD files
- **Batch processing**: Process entire folders of images

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

**Convert images to WAD:**

Convert a single image:
```bash
python3 wadtools.py --input texture.png
```

Convert all images in a folder:
```bash
python3 wadtools.py --input /path/to/textures/
```

**Extract textures from WAD:**

Extract all textures from a WAD file to PNG images:
```bash
python3 wadtools.py --input textures.wad
```

Extract to a custom directory:
```bash
python3 wadtools.py --input textures.wad --output custom_folder
```

**Extract textures from BSP:**

Extract textures from a BSP file:
```bash
python3 wadtools.py --input map.bsp
```

### Command Line Options

**Required:**
- `-i, --input`: Input file or folder (images/WAD/BSP)

**Optional:**
- `--output`: Output filename or directory
  - For image→WAD: Output WAD filename (auto-generated if not specified)
  - For WAD→PNG: Output directory (defaults to WAD filename without extension)
- `--type`: WAD format type (for image→WAD conversion)
  - `2`: WAD2 format for Quake (default)
  - `3`: WAD3 format for Half-Life (includes palette data)
- `--dithering`: Dithering mode (for image→WAD conversion)
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

Create a WAD3 file for Half-Life:
```bash
python3 wadtools.py --input textures/ --type 3
```

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
