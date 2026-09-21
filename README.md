# Quake WAD Tools

A Python utility for creating, editing, and exporting Quake WAD (Where's All the Data) files. The project includes both a command-line converter and a graphical editor for working with WAD2/WAD3 texture archives.

## Overview

This toolset can:
- convert image files into Quake-compatible WAD textures
- extract textures from WAD and BSP files to PNGs
- merge multiple WAD inputs into a single output archive
- open and edit WAD files in a tabbed Tkinter editor
- preview texture palettes and export edited WAD files

## Tools Included

### fcwadtool.py - Command-Line Tool
A command-line utility for converting images to/from WAD format and extracting textures from BSP files.

### fcwadeditor.py - Graphical Editor (NEW!)
A full-featured graphical application for viewing and editing WAD files with a user-friendly interface.

## Features

### Command-Line Tool (fcwadtool.py)
- **Convert images to WAD**: PNG, JPG, BMP, TGA, and other image formats to Quake WAD format
- **Extract textures from WAD**: Export all textures from WAD files to lossless PNG images
- **Extract textures from BSP**: Extract embedded textures from Quake/Half-Life BSP files (BSP2 and classic BSP 29/30)
- **WAD2 and WAD3 support**: Create Quake (WAD2) or Half-Life (WAD3) format files
- **QPIC support**: Extract UI graphics (type 0x42) from WAD files
- **Dithering options**: Error diffusion (Floyd-Steinberg), ordered (Bayer), random, halftone, and closest-color mapping
- **No-fullbright default**: Image conversion defaults to a no-fullbright Quake palette to avoid accidental glowing texels in-game
- **Alpha channel handling**: Multiple modes (clipped, dithered, or color replacement)
- **Automatic mipmap generation**: For texture WAD files
- **Batch processing**: Process entire folders of images

### Graphical Editor (fcwadeditor.py)
- **Tab-based interface**: Open and work with multiple WAD files and BSP-derived texture tabs simultaneously
- **Visual texture browser**: View all textures in a WAD file with thumbnails
- **Image viewer**: Double-click any texture to view it as a default 3x3 tiled preview
- **Quake palette editor**: Edit all 256 palette colors in a dedicated tab with direct color picking
- **Palette gradient helper**: Apply left/right multi-step fades from a selected palette color down to 10% brightness
- **Display palette override**: Preview all loaded textures/images using a custom `palette.lmp` without modifying texture data
- **Multi-select editing**: Shift-click ranges and Ctrl-click non-contiguous texture sets
- **Reordering support**: Drag and drop thumbnails to reorder texture order in the WAD
- **Import progress tab**: Non-blocking import status with per-file telemetry and progress bars
- **Zoom and pan**: Use mouse wheel or Ctrl+/- to zoom, click and drag to pan
- **Import/Export**: Import textures from other WAD files or export to different formats (WAD2/WAD3)
- **Edit textures**: Copy, paste, resize, and reimport textures from image files
- **Unsaved changes tracking**: Visual indicators for modified files
- **Multiple file support**: Load and edit multiple WAD files at once

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

### Graphical Editor (fcwadeditor.py)

Launch the graphical editor:
```bash
python3 fcwadeditor.py
```

#### Menu Options

**File Menu:**
- **New** (Ctrl+N): Create a new WAD file (WAD2 or WAD3)
- **Open** (Ctrl+O): Load one or more `.wad` or `.bsp` files; opening a BSP creates a new unsaved WAD tab from its embedded textures
- **Save** (Ctrl+S): Save the current WAD file in-place
- **Save As**: Save the current WAD file with a new name
- **Preferences**: Configure default import palette and dithering options
- **Import from WAD**: Load textures from another WAD file into the current one
- **Import Image(s)**: Import one or more image files as textures into the current WAD
- **Export**: Export the current WAD file in a specific format (BSP2/BSP3)
- **Export Image or Sequence as Sprite**: Export the selected texture(s) as a Quake `.spr` sprite file. Animated textures (`+1name`, `+2name`, ...) are grouped into sequences and exported as animated sprites; multiple selections export one `.spr` per sequence. The dialog lets you choose the sprite orientation (VP Parallel, Facing Upright, etc.) and the animation frame interval.
- **Close Tab** (Ctrl+W): Close the current tab
- **Exit**: Close the application (prompts to save unsaved changes)

**Edit Menu:**
- **Copy Texture** (Ctrl+C): Copy the currently selected texture to clipboard
- **Paste Texture** (Ctrl+V): Paste clipboard texture into current WAD (auto-renames if duplicate)
- **Delete**: Remove selected texture(s)
- **Rename Texture**: Rename the selected texture (with WAD naming constraints)
- **Resize Texture**: Resize the currently selected texture to new dimensions
- **Reimport Texture**: Replace the selected texture with a new image from file
- **Sort Textures Alphabetically**: Sort current WAD texture list by name
- **Edit Quake Palette**: Open a dedicated palette tab to edit colors and export/load Quake `palette.lmp` files
  - Color edit dialog supports optional gradient fade tools:
    - **Fade this color** checkbox
    - **Fade Right** / **Fade Left** direction
    - **Steps** textbox (default `15`), producing source color plus 15 progressively darker entries down to 10% brightness

**View Menu:**
- **Zoom In / Zoom Out**: Scale thumbnail icon size in texture tabs and zoom image viewer tabs
- **Set Icon Size**: Set a specific thumbnail icon size in pixels
- **Set Image Zoom Level** (image tabs): Choose a fixed zoom level from `25%`, `50%`, `75%`, `100%`, `200%`, or `400%`
- **View Original Image** (image tabs): Show a single 1x1 copy of the image for close inspection
- **View Tiled Image** (image tabs): Show the image as a tiled 3x3 preview
- **Display Using Custom Palette**: Load a `.lmp` palette and display all currently loaded WAD textures and image tabs using that palette
- **Clear Custom Palette**: Revert display rendering back to each texture's original palette
- **View in Separate Tab**: Open selected texture in an image viewer tab
- When a custom display palette is active, the status bar shows the palette filename

**Preferences (File -> Preferences...):**
- Choose import palette mode: original Quake, no-fullbrights, or custom palette
- Select a custom `.lmp` palette file used for imports when custom mode is selected
- Toggle **Include fullbrights in this import** for custom palette mode
  - Unchecked (default): importer remaps away from fullbright indices `224-255`
  - Checked: importer keeps fullbright range available

#### Working with the Editor

1. **Open a WAD or BSP file**: Use File → Open or press Ctrl+O
2. **Browse textures**: Scroll through the thumbnail grid
3. **Select a texture**: Click once on any texture to select it
4. **View a texture**: Double-click any texture to open it in a 3x3 tiled viewer tab
5. **Switch display mode**: Use View → View Original Image or View → View Tiled Image while on an image tab
6. **Zoom in/out**: 
   - Use mouse wheel while viewing an image
   - Press Ctrl+ to zoom in, Ctrl- to zoom out
7. **Pan an image**: Click and drag to move around a zoomed image
8. **Copy/Paste**: Select a texture, press Ctrl+C to copy, switch to another WAD tab, press Ctrl+V to paste
9. **Import textures**: Use File → Import from WAD to select textures from another file
10. **Import image files**: Use File → Import Image(s) to convert and add new textures from PNG/JPG/BMP/TGA/TIFF files
11. **Reorder textures**: Drag and drop thumbnails to change WAD texture order
12. **Save changes**: Press Ctrl+S or use File → Save

#### Tab Management

- Each WAD file or image opens in its own tab
- Tabs show an asterisk (*) before the name when there are unsaved changes
- Close tabs with Ctrl+W or the Close Tab menu option
- Switch between tabs by clicking on them

### Command-Line Tool (fcwadtool.py)

#### Basic Usage

**Convert images to WAD:**

Convert a single image:
```bash
python3 fcwadtool.py --input texture.png
```

Convert all images in a folder:
```bash
python3 fcwadtool.py --input /path/to/textures/
```

**Extract textures from WAD:**

Extract all textures from a WAD file to PNG images:
```bash
python3 fcwadtool.py --input textures.wad
```

Extract to a custom directory:
```bash
python3 fcwadtool.py --input textures.wad --output custom_folder
```

**Extract textures from BSP:**

Extract textures from a BSP file:
```bash
python3 fcwadtool.py --input map.bsp
```

**Merge multiple WAD files into one deduplicated WAD:**

```bash
python3 fcwadtool.py -i /path/to/wads/*.wad -o merged.wad
```

**Process multiple BSP files in one command:**

```bash
python3 fcwadtool.py -i /path/to/maps/*.bsp
```

The `--input` option accepts multiple files, directories, BSPs, and shell-expanded wildcard patterns. In bash/zsh, wildcards expand before the script runs; if you are using a different shell or passing patterns programmatically, make sure the pattern resolves to files before invoking the tool.

### Command Line Options

**Required:**
- `-i, --input`: Input file or folder (images/WAD/BSP)

**Optional:**
- `-o, --output`: Output filename or directory
  - For image→WAD: Output WAD filename (auto-generated if not specified)
  - For WAD→PNG: Output directory (defaults to WAD filename without extension)
  - For multiple WAD inputs: Output merged WAD filename (deduplicated by texture name)
- `--type`: WAD format type (for image→WAD conversion)
  - `2`: WAD2 format for Quake (default)
  - `3`: WAD3 format for Half-Life (includes palette data)
- `--dithering`: Dithering mode (for image→WAD conversion)
  - `0`: Error Diffusion (Floyd-Steinberg, default)
  - `1`: Ordered (Bayer matrix) dithering
  - `2`: Random dithering
  - `3`: Halftone dithering
  - `4`: Closest Color Available (no dithering)
- `--alpha`: Alpha channel handling mode
  - `0`: Clipped alpha - only fully transparent pixels (alpha = 0) become index 255 (default)
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
python3 fcwadtool.py --input textures/ --type 3
```

Convert with ordered dithering:
```bash
python3 fcwadtool.py --input textures/ --dithering 1
```

Convert with dithered alpha:
```bash
python3 fcwadtool.py --input logo.png --alpha 1 --alphadither 0
```

Convert with custom alpha color:
```bash
python3 fcwadtool.py --input texture.png --alpha 2 --alphacolor #FF00FF
```

Specify output filename:
```bash
python3 fcwadtool.py --input textures/ --output custom.wad
```

Merge and deduplicate all textures from multiple WAD files:
```bash
python3 fcwadtool.py -i /mnt/userdata/Games/Quake/mg3/maps/*.wad -o mg3.wad
```

## How It Works

1. **Image Loading**: Loads images using PIL/Pillow
2. **Alpha Processing**: Handles transparency according to selected mode
3. **Dithering**: Applies the selected mode (error diffusion, ordered, random, halftone, or closest-color mapping) to reduce colors to Quake's 256-color palette
  - Random dithering uses a fast noise+quantize path to avoid slow per-pixel Python loops on large textures
  - Default conversion uses [palette_no_fb.tga](palette_no_fb.tga) so generated indices stay below Quake's fullbright range
  - [palette_full.tga](palette_full.tga) remains available as the full reference palette
4. **Palette Conversion**: Maps RGB colors to closest Quake palette indices
5. **Mipmap Generation**: Creates 4 mipmap levels for each texture
6. **WAD Creation**: Writes textures to WAD2 or WAD3 output, depending on selected mode

## Supported Image Formats

- PNG (recommended for alpha channel support)
- JPEG/JPG
- BMP
- TGA
- TIFF
- And other formats supported by PIL/Pillow

## WAD Format

This tool creates WAD2 (Quake) and WAD3 (Half-Life) format files compatible with:
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
- Only fully transparent pixels (alpha = 0) are forced to palette index 255 in clipped mode; non-zero alpha pixels are quantized normally
- Transparent textures should be named with a leading { for Quake-compatible masked rendering behavior
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
- Try different dithering modes (`--dithering 0` through `--dithering 4`)
- For images with transparency, experiment with alpha modes

## License

This tool is provided as-is for use with Quake and compatible games.

## References

- Quake palette specification
- WAD3 file format
- ericw-tools (Quake compilation tools)
