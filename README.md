# Quake WAD Tools

FCWADTool is a Python toolkit for converting images to Quake-compatible WAD textures, extracting textures from WAD and BSP files, merging WAD archives, exporting Quake sprites, and editing texture archives in a Tkinter application.

The command-line tool is `fcwadtool.py`. The graphical editor is `fcwadeditor.py`.

## Overview

This toolset can:
- convert image files into Quake-compatible WAD textures
- extract textures from WAD and BSP files to PNGs
- merge multiple WAD inputs into a single output archive
- export selected WAD textures and `+Nname` frame sequences as Quake `.spr` files
- open and edit multiple WAD files and BSP-derived WAD tabs in a Tkinter editor
- edit, reorder, resize, rename, reimport, sort, copy, paste, and delete textures
- remove original Quake and mission-pack textures from user-made WADs
- preview and edit Quake palettes, including raw 768-byte `palette.lmp` files

## Tools Included

### fcwadtool.py - Command-Line Tool
A command-line utility for converting images to/from WAD format and extracting textures from BSP files.

### fcwadeditor.py - Graphical Editor
A tabbed graphical application for viewing and editing WAD files, images, palettes, and BSP-derived texture collections.

## Project Files

- `fcwadtool.py`: command-line converter, extractor, merger, and sprite writer
- `fcwadeditor.py`: Tkinter-based WAD and palette editor
- `palette_no_fb.tga`: default 224-color import palette with the fullbright range excluded
- `palette_full.tga`: full 256-color Quake palette used for original/fullbright processing
- `requirements.txt`: Python package dependencies
- `options.cfg`: editor preferences created beside the scripts at first launch; ignored by git

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
- **Wildcard input support**: Process shell-expanded paths or patterns passed to `--input`
- **Deduplicating WAD merge**: Keep the first texture for each case-insensitive 15-character name

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
- **Sprite export**: Export one texture or selected `+Nname` frames as Quake `.spr` files
- **Edit textures**: Copy, paste, resize, and reimport textures from image files
- **Cleanup**: Remove names found in the original Quake WAD collection while preserving utility textures
- **Unsaved changes tracking**: Visual indicators for modified files
- **Multiple file support**: Load and edit multiple WAD files at once

## Installation

1. Install Python 3.9 or newer.
2. Make sure Tkinter is installed. On Debian/Ubuntu systems this is usually provided by `python3-tk`.
3. Install the Python dependency:

```bash
pip install -r requirements.txt
```

The only package dependency is Pillow. Tkinter is a system Python module and is not installed by `requirements.txt`.

For an isolated environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

Run the editor and CLI from the project directory so the bundled palette files are found reliably.

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
- **Export**: Export the current WAD file as WAD2 or WAD3
- **Export Image or Sequence as Sprite**: Export selected textures as Quake `.spr` files. Names such as `+1button`, `+2button`, and `+3button` are grouped and ordered as one sequence. Multiple unrelated selections can be exported as separate files. The dialog lets you choose the sprite orientation and a positive frame interval.
- **Close Tab** (Ctrl+W): Close the current tab
- **Exit**: Close the application (prompts to save unsaved changes)

**Edit Menu:**
- **Copy Texture** (Ctrl+C): Copy the currently selected texture to clipboard
- **Paste Texture** (Ctrl+V): Paste clipboard texture into current WAD (auto-renames if duplicate)
- **Delete**: Remove selected texture(s)
- **Remove ID Textures**: Remove names found in the original Quake WAD collection while preserving `skip`, `clip`, `trigger`, and every `sky*` texture
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

Thumbnail view also supports Ctrl-click for non-contiguous selections, Shift-click for a range, Delete or Backspace for deletion, and right-click for a context menu containing the common texture actions. Resize applies to every selected texture.

`Edit -> Remove ID Textures` scans the fixed directory `/mnt/userdata/Games/Quake/wads/original/`. Every `.wad` below that directory is read from its directory entries, so image decoding is not needed for the scan. Name matching is case-insensitive. The operation asks for confirmation, marks the WAD modified, and should be used with a backup if the source archive must be preserved.

#### Tab Management

- Each WAD file or image opens in its own tab
- Tabs show an asterisk (*) before the name when there are unsaved changes
- Close tabs with Ctrl+W, the Close Tab menu option, middle-click, or the tab context menu
- Switch between tabs by clicking on them

Opening a `.bsp` creates an in-memory WAD tab named after the map. It is treated as unsaved until explicitly saved. Opening multiple files creates one tab per file.

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

Input folders are scanned for supported image files in that folder only; the image scan is not recursive. A quoted wildcard can also be expanded by the tool itself.

#### Input and output dispatch

The input suffix determines the operation:

| Input | Operation | `--output` meaning | Default output |
| --- | --- | --- | --- |
| Image file | Convert one image to a WAD | WAD filename | `<image-stem>.wad` |
| Image folder | Convert all supported images in the folder | WAD filename | `<folder-name>.wad` |
| One `.wad` file | Extract entries to PNG | Output directory | Directory named after the WAD stem |
| One `.bsp` file | Extract embedded textures and write a WAD | WAD filename | `<map-stem>.wad` |
| Multiple `.wad` files plus `--output` | Merge and deduplicate | Merged WAD filename | Not applicable |
| Multiple other inputs | Process each independently | Not allowed with multiple inputs | One auto-named output per input |

When a WAD is extracted, QPIC entries and miptex entries that can be decoded are written as PNG files. Failed entries are reported and do not prevent other entries from being extracted.

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

The CLI always uses the default no-fullbright processing palette. Custom `.lmp` import palettes are configured in the graphical editor; there is no CLI option for selecting a custom import palette.

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
python3 fcwadtool.py --input texture.png --alpha 2 --alphacolor '#FF00FF'
```

Specify output filename:
```bash
python3 fcwadtool.py --input textures/ --output custom.wad
```

Merge and deduplicate all textures from multiple WAD files:
```bash
python3 fcwadtool.py -i /mnt/userdata/Games/Quake/mg3/maps/*.wad -o mg3.wad
```

Extract every WAD in a folder into separate directories:
```bash
python3 fcwadtool.py -i /path/to/wads/*.wad
```

## Palette and Image Conversion

### Processing palettes

Image conversion defaults to [palette_no_fb.tga](palette_no_fb.tga), which contains the first 224 Quake colors. Quantized results are remapped so indices `224` through `255` are not introduced accidentally. This is the safest default for world textures because Quake treats the upper palette range as fullbright colors.

Use `--type 3` when a WAD3 consumer expects an embedded palette. WAD2 entries do not carry an embedded palette and are interpreted with the target engine's Quake palette.

The editor exposes three import palette modes in `File -> Preferences...`:

- **Original Quake palette**: all 256 Quake colors, including fullbrights
- **Custom No-Fullbrights palette**: the bundled safe palette; this is the default
- **Custom Palette (.lmp / Palette Editor)**: a raw 768-byte RGB palette edited or loaded by the user

Custom palette imports also exclude indices `224` through `255` unless **Include fullbrights in this import** is enabled.

### Dithering modes

| Value | Name | Behavior |
| --- | --- | --- |
| `0` | Error Diffusion | Floyd-Steinberg quantization; default and generally the best starting point for photographic or shaded images |
| `1` | Ordered | Repeating Bayer threshold pattern |
| `2` | Random | Pillow noise generation followed by no-pattern palette quantization |
| `3` | Halftone | Clustered-dot threshold pattern |
| `4` | Closest Color Available | No pattern dithering; choose the nearest available palette color |

The optimized paths use Pillow image operations rather than a Python nearest-color loop for every pixel. The editor's import progress tab reports open, decode, alpha, dither, palette, and total timings for each file.

### Alpha and transparency

- `--alpha 0` (clipped, default): only pixels with alpha exactly `0` are forced to palette index `255`; pixels with any non-zero alpha are quantized normally
- `--alpha 1` (dithered): convert the alpha channel to an opaque/transparent mask using Floyd-Steinberg or ordered dithering, selected by `--alphadither`
- `--alpha 2` (replace): replace fully transparent pixels with the RGB color from `--alphacolor` before palette conversion

The tool warns when transparent pixels are found in a texture whose name does not start with `{`. Quake's masked-texture convention requires the leading `{`; the importer does not rename the texture automatically.

## How It Works

1. **Image loading**: Pillow opens the source and eagerly decodes it so import timing can be measured separately.
2. **Alpha processing**: Apply clipped, dithered, or replacement handling to RGBA images.
3. **Dithering and quantization**: Reduce RGB data to the selected Quake palette using one of the five modes above.
4. **Transparency remapping**: In clipped or dithered-alpha modes, force the transparent mask to index `255` after quantization.
5. **WAD writing**: Write the texture name, dimensions, pixel data, four mip levels, and the WAD directory entry.

The bundled [palette_no_fb.tga](palette_no_fb.tga) is the normal processing palette. [palette_full.tga](palette_full.tga) is available for fullbright-aware processing and reference work. If an external palette file cannot be loaded, the code has an embedded fallback palette.

## Supported Image Formats

- PNG (recommended for alpha channel support)
- JPEG/JPG
- BMP
- TGA
- TIFF
- And other formats supported by PIL/Pillow

## WAD Format

The writer supports two related formats:

- **WAD2**: Quake format, selected with `--type 2` and used by default. Miptex entries do not contain an embedded palette.
- **WAD3**: Half-Life/GoldSrc-style format, selected with `--type 3`. Miptex entries include a 256-color palette after the mip data.

Texture entries contain a 15-character maximum ASCII name, dimensions, four mip levels, and palette-indexed pixel data. WAD extraction also understands QPIC entries (directory type `0x42`) for UI graphics.

The output should be checked in the target editor or engine, especially when moving WAD3 data into a WAD2-only workflow.

## Notes

- Texture names are limited to 15 characters (derived from filename)
- Keep texture names ASCII and avoid relying on characters outside the WAD name field.
- Images are automatically converted to the selected Quake-compatible palette
- Only fully transparent pixels (alpha = 0) are forced to palette index 255 in clipped mode; non-zero alpha pixels are quantized normally
- Transparent textures should be named with a leading { for Quake-compatible masked rendering behavior
- For best results with transparency, use PNG format with alpha channel
- WAD readers validate dimensions up to 4096 x 4096 and skip malformed entries with warnings; BSP extraction reports incomplete or missing mip data but does not apply the same dimension limit.
- Multiple-WAD merge compares names case-insensitively after truncating them to 15 characters. The first occurrence wins; exact duplicates and conflicting data are reported separately.
- `File -> Remove ID Textures` depends on `/mnt/userdata/Games/Quake/wads/original/`. If that directory is not present, the command reports an error instead of deleting anything.
- The editor's `options.cfg` stores import preferences, the last file-dialog folder, the last ten edited paths, and the in-memory custom palette. It is local user state and is ignored by git.

### Palette editor

`Edit -> Edit Quake Palette` opens a 16 x 16 grid containing all 256 palette colors. Clicking a color opens a picker. The color dialog can also apply a left or right fade over a configurable number of steps, defaulting to 15 steps down to 10 percent brightness. The editor can load and export raw Quake `palette.lmp` files; valid files are exactly 768 bytes containing 256 RGB triples.

### Sprite export details

`File -> Export Image or Sequence as Sprite...` writes the id Software `IDSP` sprite header and palette-indexed frame data. Selected names matching `+<number><base-name>` are sorted by frame number and written in sequence order; ordinary texture names become single-frame sprites. The dialog validates a positive frame interval, but the current writer emits `SPR_SINGLE` records rather than timed frame groups, so game-side frame timing remains the responsibility of the consuming entity or code.

## Troubleshooting

**Import Error: PIL/Pillow not found**
```bash
pip install Pillow
```

**No images found**
- Check that the input path is correct
- Ensure images have supported extensions (`.png`, `.jpg`, `.jpeg`, `.bmp`, `.tga`, `.tif`, or `.tiff`)
- Remember that image-folder scanning is not recursive

**The shell reports unrecognized arguments for a wildcard command**
- Use one `-i` followed by all paths, for example `python3 fcwadtool.py -i /path/to/maps/*.bsp`
- Do not repeat `-i` for every expanded path
- If using `--output` with multiple inputs, all inputs must be WAD files so the command is unambiguously a merge

**A WAD extracts fewer textures than expected**
- The extractor skips malformed, unsupported, or incomplete directory entries and prints a warning for each skipped entry
- QPIC and miptex entries have different layouts; verify the source WAD type and entry types in a WAD inspection tool

**The editor cannot remove ID textures**
- Verify that `/mnt/userdata/Games/Quake/wads/original/` exists and contains the original `.wad` files
- The cleanup scans WAD directory names and preserves `skip`, `clip`, `trigger`, and all `sky*` names

**Texture quality issues**
- Try different dithering modes (`--dithering 0` through `--dithering 4`)
- For images with transparency, experiment with alpha modes

## License

This tool is provided as-is for use with Quake and compatible games.

## References

- Quake palette specification
- WAD3 file format
- ericw-tools (Quake compilation tools)

## Development Checks

Run these quick checks from the project directory before committing changes:

```bash
python3 -m py_compile fcwadtool.py fcwadeditor.py
python3 fcwadtool.py --help
git diff --check
```

For an end-to-end smoke test, convert a small image to WAD, extract it to PNG, and inspect the result in the editor or a Quake WAD browser:

```bash
python3 fcwadtool.py -i texture.png -o smoke-test.wad
python3 fcwadtool.py -i smoke-test.wad -o smoke-test-extracted
python3 fcwadeditor.py
```
