#!/usr/bin/env python3
"""
Quake WAD Editor - Graphical WAD file editor
A graphical application for viewing and editing Quake WAD files
"""

import sys
import os
import re
import struct
import io
import json
import threading
import queue
import time
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from tkinter import *
from tkinter import ttk, filedialog, messagebox, simpledialog, colorchooser
from PIL import Image, ImageTk, ImageDraw, ImageFont

# Import WAD handling functions from fcwadtool
import fcwadtool

OPTIONS_FILENAME = 'options.cfg'
BLACKLIST_DIRECTORY = Path(__file__).resolve().parent / 'blacklists'
BLACKLIST_PATH = BLACKLIST_DIRECTORY / 'blacklist.txt'
UTILITY_TEXTURE_NAMES = frozenset({'skip', 'clip', 'trigger', 'sky'})
UTILITY_TEXTURE_PREFIXES = ('sky',)

PALETTE_OPTION_ITEMS = [
    ('Use Original Quake palette', fcwadtool.PALETTE_MODE_ORIGINAL),
    ('Use Custom No-Fullbrights palette', fcwadtool.PALETTE_MODE_NO_FULLBRIGHTS),
    ('Use Custom Palette (.lmp / Palette Editor)', fcwadtool.PALETTE_MODE_CUSTOM),
]
PALETTE_LABEL_TO_MODE = {label: mode for label, mode in PALETTE_OPTION_ITEMS}
PALETTE_MODE_TO_LABEL = {mode: label for label, mode in PALETTE_OPTION_ITEMS}

DITHERING_OPTION_ITEMS = [
    (
        'Use Ordered Dithering: Uses a fixed threshold matrix (e.g., Bayer matrix) to create regular, dispersed patterns; fast and suitable for animations but may show visible artifacts.',
        fcwadtool.DITHERING_INDEX_ORDERED,
    ),
    (
        'Error Diffusion: Distributes quantization error to neighboring pixels for finer detail; includes algorithms like Floyd-Steinberg (standard) and Sierra (faster).',
        fcwadtool.DITHERING_INDEX_ERROR_DIFFUSION,
    ),
    (
        'Random Dithering: Adds random noise before thresholding; reduces artifacts but is computationally intensive and less common in modern real-time applications.',
        fcwadtool.DITHERING_INDEX_RANDOM,
    ),
    (
        'Halftone Dithering: Clusters dots to mimic newspaper printing; useful for offset printing and laser printers.',
        fcwadtool.DITHERING_INDEX_HALFTONE,
    ),
    (
        'Closest Color Available: Wadtool will select the closest color in the Quake palette for each pixel in the image.',
        fcwadtool.DITHERING_INDEX_CLOSEST_COLOR,
    ),
]
DITHERING_LABEL_TO_INDEX = {label: index for label, index in DITHERING_OPTION_ITEMS}
DITHERING_INDEX_TO_LABEL = {index: label for label, index in DITHERING_OPTION_ITEMS}

DEFAULT_EDITOR_OPTIONS = {
    'palette_mode': fcwadtool.PALETTE_MODE_NO_FULLBRIGHTS,
    'dithering_mode': fcwadtool.DITHERING_INDEX_ERROR_DIFFUSION,
    'custom_palette_file': '',
    'custom_palette_include_fullbrights': False,
    'custom_palette_data': [],
    'last_folder': '',
    'recent_files': [],
}

PALETTE_LMP_BYTE_COUNT = 768
PALETTE_GRID_COLUMNS = 16
PALETTE_GRID_COLOR_COUNT = 256


def is_utility_texture_name(name: str) -> bool:
    """Return whether a texture name should be preserved during ID cleanup."""
    normalized_name = name.casefold()
    return normalized_name in UTILITY_TEXTURE_NAMES or any(
        normalized_name.startswith(prefix) for prefix in UTILITY_TEXTURE_PREFIXES
    )

class TextureData:
    """Represents a single texture in a WAD file"""
    display_palette_override: Optional[List[int]] = None

    def __init__(self, name: str, width: int, height: int, data: bytes, palette: List[int] = None):
        self.name = name
        self.width = width
        self.height = height
        self.data = data
        self.palette = palette if palette else fcwadtool.QUAKE_PALETTE
        self.image = None
        self._generate_image()

    @classmethod
    def set_display_palette_override(cls, palette: Optional[List[int]]):
        """Set optional palette used for display-only preview rendering."""
        if palette is None:
            cls.display_palette_override = None
            return

        normalized = []
        for value in list(palette)[:PALETTE_LMP_BYTE_COUNT]:
            try:
                channel = int(value)
            except Exception:
                channel = 0
            normalized.append(max(0, min(255, channel)))

        if len(normalized) < PALETTE_LMP_BYTE_COUNT:
            normalized.extend([0] * (PALETTE_LMP_BYTE_COUNT - len(normalized)))

        cls.display_palette_override = normalized[:PALETTE_LMP_BYTE_COUNT]
    
    def _generate_image(self):
        """Generate PIL Image from palette data"""
        display_palette = self.display_palette_override if self.display_palette_override else self.palette
        self.image = fcwadtool.palette_to_image(self.width, self.height, self.data, display_palette)
    
    def get_thumbnail(self, size: int = 64) -> ImageTk.PhotoImage:
        """Get thumbnail of texture scaled to exactly the specified size"""
        # Always resize to exactly size x size, scaling up or down as needed
        thumb = self.image.resize((size, size), Image.Resampling.NEAREST)
        return ImageTk.PhotoImage(thumb)
    
    def get_display_image(self, zoom: float = 1.0) -> ImageTk.PhotoImage:
        """Get display image at specified zoom level"""
        if zoom == 1.0:
            return ImageTk.PhotoImage(self.image)
        
        new_size = (int(self.width * zoom), int(self.height * zoom))
        if zoom < 1.0:
            resized = self.image.resize(new_size, Image.Resampling.NEAREST)
        else:
            resized = self.image.resize(new_size, Image.Resampling.NEAREST)
        return ImageTk.PhotoImage(resized)


class WADFile:
    """Represents an open WAD file"""
    def __init__(self, filepath: str = None, wad_type: int = 2):
        self.filepath = filepath
        self.display_name: Optional[str] = None
        self.wad_type = wad_type  # 2 = WAD2 (Quake), 3 = WAD3 (Half-Life)
        self.textures: List[TextureData] = []
        self.modified = False
        
        if filepath:
            self._load_from_file()
    
    def _load_from_file(self):
        """Load WAD file from disk"""
        try:
            with open(self.filepath, 'rb') as f:
                # Read WAD header
                magic = f.read(4)
                if magic not in [b'WAD2', b'WAD3']:
                    raise ValueError(f"Not a valid WAD file (magic: {magic})")
                
                self.wad_type = 2 if magic == b'WAD2' else 3
                
                num_textures = struct.unpack('<I', f.read(4))[0]
                directory_offset = struct.unpack('<I', f.read(4))[0]
                
                # Read directory entries
                f.seek(directory_offset)
                entries = []
                
                for i in range(num_textures):
                    offset = struct.unpack('<I', f.read(4))[0]
                    disk_size = struct.unpack('<I', f.read(4))[0]
                    size = struct.unpack('<I', f.read(4))[0]
                    type_byte = struct.unpack('<B', f.read(1))[0]
                    compression = struct.unpack('<B', f.read(1))[0]
                    padding = struct.unpack('<H', f.read(2))[0]
                    name_bytes = f.read(16)
                    name = name_bytes.split(b'\x00')[0].decode('ascii', errors='ignore')
                    
                    entries.append((name, offset, disk_size, type_byte))
                
                # Read each texture
                for name, offset, disk_size, type_byte in entries:
                    try:
                        f.seek(offset)
                        
                        if type_byte == 0x42:  # QPIC format
                            width = struct.unpack('<I', f.read(4))[0]
                            height = struct.unpack('<I', f.read(4))[0]
                            
                            if width <= 0 or height <= 0 or width > 4096 or height > 4096:
                                continue
                            
                            data_size = width * height
                            texture_data = f.read(data_size)
                            palette = fcwadtool.QUAKE_PALETTE
                            
                        elif type_byte in [0x43, 0x44]:  # Miptex format
                            name_bytes = f.read(16)
                            width = struct.unpack('<I', f.read(4))[0]
                            height = struct.unpack('<I', f.read(4))[0]
                            
                            if width <= 0 or height <= 0 or width > 4096 or height > 4096:
                                continue
                            
                            mip0_offset = struct.unpack('<I', f.read(4))[0]
                            mip1_offset = struct.unpack('<I', f.read(4))[0]
                            mip2_offset = struct.unpack('<I', f.read(4))[0]
                            mip3_offset = struct.unpack('<I', f.read(4))[0]
                            
                            if mip0_offset == 0 or mip0_offset > disk_size:
                                continue
                            
                            f.seek(offset + mip0_offset)
                            data_size = width * height
                            
                            if type_byte == 0x43:  # WAD3 with embedded palette
                                texture_data = f.read(data_size)
                                
                                mip1_size = (width // 2) * (height // 2)
                                mip2_size = (width // 4) * (height // 4)
                                mip3_size = (width // 8) * (height // 8)
                                palette_pos = offset + mip3_offset + mip3_size
                                
                                f.seek(palette_pos)
                                palette_size_marker = struct.unpack('<H', f.read(2))[0]
                                if palette_size_marker == 256:
                                    palette = list(f.read(768))
                                else:
                                    palette = fcwadtool.QUAKE_PALETTE
                            else:
                                texture_data = f.read(data_size)
                                palette = fcwadtool.QUAKE_PALETTE
                        else:
                            continue
                        
                        texture = TextureData(name, width, height, texture_data, palette)
                        self.textures.append(texture)
                        
                    except Exception as e:
                        print(f"Error loading texture {name}: {e}")
                        continue
        
        except Exception as e:
            raise Exception(f"Error loading WAD file: {e}")
    
    def save(self, filepath: str = None):
        """Save WAD file to disk"""
        if filepath:
            self.filepath = filepath
        
        if not self.filepath:
            raise ValueError("No filepath specified for save")
        
        # Prepare texture data for writing
        textures = [(t.name, t.width, t.height, t.data) for t in self.textures]
        
        # Use fcwadtool to create the WAD file
        fcwadtool.create_wad(textures, self.filepath, self.wad_type)
        self.modified = False
    
    def add_texture(self, texture: TextureData):
        """Add a texture to the WAD"""
        # Check for duplicate names and rename if necessary
        original_name = texture.name
        counter = 1
        while any(t.name == texture.name for t in self.textures):
            texture.name = f"{original_name}{counter}"
            counter += 1
        
        self.textures.append(texture)
        self.modified = True
    
    def remove_texture(self, index: int):
        """Remove a texture from the WAD"""
        if 0 <= index < len(self.textures):
            del self.textures[index]
            self.modified = True
    
    def get_name(self) -> str:
        """Get display name for this WAD"""
        if self.filepath:
            return Path(self.filepath).name
        if self.display_name:
            return self.display_name
        return "Untitled.wad"


class ImageViewerTab(Frame):
    """Tab for viewing a single image with zoom and pan"""
    def __init__(self, parent, texture: TextureData):
        super().__init__(parent)
        self.texture = texture
        self.default_tile_columns = 3
        self.default_tile_rows = 3
        self.tile_columns = self.default_tile_columns
        self.tile_rows = self.default_tile_rows
        self.is_tiled_view = True
        self.zoom = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 16.0
        self.pan_x = 0
        self.pan_y = 0
        self.drag_start = None
        
        # Create canvas with scrollbars
        self.canvas = Canvas(self, bg='#2b2b2b', highlightthickness=0)
        self.h_scrollbar = Scrollbar(self, orient=HORIZONTAL, command=self.canvas.xview)
        self.v_scrollbar = Scrollbar(self, orient=VERTICAL, command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.h_scrollbar.set, yscrollcommand=self.v_scrollbar.set)
        
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.h_scrollbar.grid(row=1, column=0, sticky='ew')
        self.v_scrollbar.grid(row=0, column=1, sticky='ns')
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Info label
        self.info_label = Label(self, text=f"{texture.name} - {texture.width}x{texture.height} - Zoom: {int(self.zoom*100)}%",
                               bg='#1e1e1e', fg='white', anchor='w', padx=5)
        self.info_label.grid(row=2, column=0, columnspan=2, sticky='ew')
        
        # Bind events
        self.canvas.bind('<MouseWheel>', self.on_mousewheel)
        self.canvas.bind('<Button-4>', self.on_mousewheel)  # Linux scroll up
        self.canvas.bind('<Button-5>', self.on_mousewheel)  # Linux scroll down
        self.canvas.bind('<Control-plus>', self.zoom_in)
        self.canvas.bind('<Control-minus>', self.zoom_out)
        self.canvas.bind('<Control-equal>', self.zoom_in)  # For keyboards where + requires shift
        self.canvas.bind('<ButtonPress-1>', self.on_drag_start)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_drag_end)
        
        self.canvas.focus_set()
        
        self.photo_image = None
        self.image_ids: List[int] = []
        self.update_image()
    
    def update_image(self):
        """Update the displayed image"""
        # Get one zoomed tile image and render based on current view mode.
        self.photo_image = self.texture.get_display_image(self.zoom)
        tile_width = self.photo_image.width()
        tile_height = self.photo_image.height()
        
        # Update canvas
        for image_id in self.image_ids:
            self.canvas.delete(image_id)
        self.image_ids = []

        for row in range(self.tile_rows):
            for col in range(self.tile_columns):
                image_id = self.canvas.create_image(
                    col * tile_width,
                    row * tile_height,
                    anchor='nw',
                    image=self.photo_image,
                )
                self.image_ids.append(image_id)
        
        # Update scroll region
        img_width = tile_width * self.tile_columns
        img_height = tile_height * self.tile_rows
        self.canvas.configure(scrollregion=(0, 0, img_width, img_height))
        
        # Update info label
        if self.is_tiled_view:
            view_mode_text = f"Tiled {self.tile_columns}x{self.tile_rows}"
        else:
            view_mode_text = "Original"

        self.info_label.configure(
            text=(
                f"{self.texture.name} - {self.texture.width}x{self.texture.height} "
                f"- {view_mode_text} - Zoom: {int(self.zoom*100)}%"
            )
        )

    def set_tiled_view(self, enabled: bool):
        """Toggle between tiled (3x3) and original (1x1) image view."""
        if enabled:
            self.tile_columns = self.default_tile_columns
            self.tile_rows = self.default_tile_rows
            self.is_tiled_view = True
        else:
            self.tile_columns = 1
            self.tile_rows = 1
            self.is_tiled_view = False

        self.update_image()
    
    def zoom_in(self, event=None):
        """Zoom in"""
        old_zoom = self.zoom
        self.zoom = min(self.zoom * 1.5, self.max_zoom)
        if old_zoom != self.zoom:
            self.update_image()
    
    def zoom_out(self, event=None):
        """Zoom out"""
        old_zoom = self.zoom
        self.zoom = max(self.zoom / 1.5, self.min_zoom)
        if old_zoom != self.zoom:
            self.update_image()

    def set_zoom_percent(self, zoom_percent: int):
        """Set zoom directly from a percent value."""
        try:
            normalized_zoom = float(zoom_percent) / 100.0
        except Exception:
            return

        normalized_zoom = max(self.min_zoom, min(self.max_zoom, normalized_zoom))
        if abs(normalized_zoom - self.zoom) < 1e-9:
            return

        self.zoom = normalized_zoom
        self.update_image()
    
    def on_mousewheel(self, event):
        """Handle mouse wheel for zooming"""
        if event.num == 4 or event.delta > 0:
            self.zoom_in()
        elif event.num == 5 or event.delta < 0:
            self.zoom_out()
    
    def on_drag_start(self, event):
        """Start panning"""
        self.drag_start = (event.x, event.y)
        self.canvas.config(cursor='fleur')
    
    def on_drag(self, event):
        """Pan the image"""
        if self.drag_start:
            dx = event.x - self.drag_start[0]
            dy = event.y - self.drag_start[1]
            # Reduce sensitivity for smoother panning (divide by 3)
            self.canvas.xview_scroll(int(-dx / 3), 'units')
            self.canvas.yview_scroll(int(-dy / 3), 'units')
            self.drag_start = (event.x, event.y)
    
    def on_drag_end(self, event):
        """End panning"""
        self.drag_start = None
        self.canvas.config(cursor='')

    def destroy(self):
        """Release image references before destroying this tab."""
        self.photo_image = None
        self.image_ids = []
        self.texture = None
        super().destroy()


class WADViewerTab(Frame):
    """Tab for viewing textures in a WAD file"""
    def __init__(self, parent, wad: WADFile, on_texture_double_click, editor=None):
        super().__init__(parent)
        self.wad = wad
        self.on_texture_double_click = on_texture_double_click
        self.editor = editor  # Reference to parent WADEditor
        self.selected_indices = set()  # Changed to set for multi-select
        self.last_selected_index = None  # For shift-click range selection
        self.icon_size = 128  # Default icon size
        
        # Create scrollable frame
        self.canvas = Canvas(self, bg='#2b2b2b', highlightthickness=0)
        self.scrollbar = Scrollbar(self, orient=VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = Frame(self.canvas, bg='#2b2b2b')
        
        self.scrollable_frame.bind(
            '<Configure>',
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor='nw')
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self.scrollbar.pack(side=RIGHT, fill=Y)
        
        # Bind wheel events only inside this tab to avoid global callback leaks.
        self._bind_mousewheel(self.canvas)
        self._bind_mousewheel(self.scrollable_frame)
        
        # Bind window resize to refresh layout
        self.bind('<Configure>', self._on_resize)
        self.last_width = 0
        
        # Bind Delete and Backspace keys for deleting textures
        self.bind('<Delete>', self.on_delete_key)
        self.bind('<BackSpace>', self.on_delete_key)
        # Make sure the frame can receive keyboard focus
        self.bind('<FocusIn>', lambda e: None)
        self.canvas.bind('<Button-1>', lambda e: self.focus_set())
        
        self.texture_frames = []
        self.widget_to_index = {}
        self.drag_source_index = None
        self.drag_target_index = None
        self.drag_start_pos = None
        self.drag_in_progress = False
        self.drag_threshold = 8
        self.refresh()

    def _bind_mousewheel(self, widget):
        """Bind mousewheel handlers to a widget local to this tab."""
        widget.bind('<MouseWheel>', self._on_mousewheel)
        widget.bind('<Button-4>', self._on_mousewheel)
        widget.bind('<Button-5>', self._on_mousewheel)
    
    def _on_mousewheel(self, event):
        """Handle mousewheel scrolling"""
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, 'units')
        elif event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, 'units')
        return 'break'
    
    def _on_resize(self, event):
        """Handle window resize to recalculate columns"""
        # Only refresh if width changed significantly
        if abs(event.width - self.last_width) > 50:
            self.last_width = event.width
            self.refresh()
    
    def zoom_icons_in(self):
        """Increase icon size by 25%"""
        self.icon_size = int(self.icon_size * 1.25)
        self.icon_size = min(self.icon_size, 512)  # Cap at 512
        self.refresh()
    
    def zoom_icons_out(self):
        """Decrease icon size by 25%"""
        self.icon_size = int(self.icon_size / 1.25)
        self.icon_size = max(self.icon_size, 32)  # Minimum 32
        self.refresh()
    
    def set_icon_size(self, size: int):
        """Set icon size to specific value"""
        self.icon_size = max(32, min(512, size))
        self.refresh()
    
    def refresh(self):
        """Refresh the texture display"""
        # Clear existing frames
        for frame in self.texture_frames:
            frame.destroy()
        self.texture_frames = []
        self.widget_to_index = {}
        
        # Calculate number of columns based on window width
        # Force update to get accurate width
        self.canvas.update_idletasks()
        canvas_width = self.canvas.winfo_width()
        
        # If still too small, use the parent frame width
        if canvas_width < 100:
            self.update_idletasks()
            canvas_width = self.winfo_width()
            if canvas_width < 100:
                canvas_width = 800  # Fallback default
        
        # Subtract scrollbar width (approximately 20px)
        usable_width = canvas_width - 25
        
        # Each icon needs: icon_size + padding (10) + frame border (4) + margins (10)
        item_width = self.icon_size + 24
        columns = max(1, usable_width // item_width)
        
        # Create grid of textures
        for i, texture in enumerate(self.wad.textures):
            row = i // columns
            col = i % columns
            
            frame = Frame(self.scrollable_frame, bg='#3b3b3b', relief=RAISED, borderwidth=2)
            frame.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')
            
            # Texture thumbnail
            try:
                photo = texture.get_thumbnail(self.icon_size)
                label = Label(frame, image=photo, bg='#3b3b3b')
                label.image = photo  # Keep a reference
                label.pack(pady=5)
            except Exception as e:
                label = Label(frame, text="Error", bg='#3b3b3b', fg='red')
                label.pack(pady=5)
            
            # Texture name and info
            info_text = f"{texture.name}\n{texture.width}x{texture.height}"
            info_label = Label(frame, text=info_text, bg='#3b3b3b', fg='white', font=('Arial', 8))
            info_label.pack()
            
            # Bind double-click
            def make_double_click_handler(idx):
                return lambda e: self.on_texture_double_click(idx)
            
            frame.bind('<Double-Button-1>', make_double_click_handler(i))
            label.bind('<Double-Button-1>', make_double_click_handler(i))
            info_label.bind('<Double-Button-1>', make_double_click_handler(i))

            self._bind_mousewheel(frame)
            self._bind_mousewheel(label)
            self._bind_mousewheel(info_label)
            
            # Bind single click for selection
            def make_press_handler(idx, frm):
                return lambda e: self.on_texture_press(idx, frm, e)

            def make_drag_handler(idx):
                return lambda e: self.on_texture_drag(idx, e)

            def make_release_handler(idx):
                return lambda e: self.on_texture_release(idx, e)
            
            frame.bind('<ButtonPress-1>', make_press_handler(i, frame))
            label.bind('<ButtonPress-1>', make_press_handler(i, frame))
            info_label.bind('<ButtonPress-1>', make_press_handler(i, frame))

            frame.bind('<B1-Motion>', make_drag_handler(i))
            label.bind('<B1-Motion>', make_drag_handler(i))
            info_label.bind('<B1-Motion>', make_drag_handler(i))

            frame.bind('<ButtonRelease-1>', make_release_handler(i))
            label.bind('<ButtonRelease-1>', make_release_handler(i))
            info_label.bind('<ButtonRelease-1>', make_release_handler(i))
            
            # Bind right-click for context menu
            def make_right_click_handler(idx, frm):
                return lambda e: self.show_context_menu(idx, frm, e)
            
            frame.bind('<Button-3>', make_right_click_handler(i, frame))
            label.bind('<Button-3>', make_right_click_handler(i, frame))
            info_label.bind('<Button-3>', make_right_click_handler(i, frame))

            self.widget_to_index[frame] = i
            self.widget_to_index[label] = i
            self.widget_to_index[info_label] = i

            if i in self.selected_indices:
                frame.configure(relief=SUNKEN, borderwidth=4)
            
            self.texture_frames.append(frame)

    def destroy(self):
        """Release tab references that can pin large WAD/image objects."""
        self.texture_frames = []
        self.widget_to_index = {}
        self.selected_indices.clear()
        self.last_selected_index = None
        self.wad = None
        self.on_texture_double_click = None
        self.editor = None
        super().destroy()

    def on_texture_press(self, index: int, frame: Frame, event):
        """Handle mouse press on a texture tile"""
        self.select_texture(index, frame, event)
        self.drag_source_index = index
        self.drag_target_index = index
        self.drag_start_pos = (event.x_root, event.y_root)
        self.drag_in_progress = False

    def on_texture_drag(self, index: int, event):
        """Track thumbnail dragging for reordering"""
        if self.drag_source_index is None or self.drag_start_pos is None:
            return

        dx = abs(event.x_root - self.drag_start_pos[0])
        dy = abs(event.y_root - self.drag_start_pos[1])

        if not self.drag_in_progress:
            if dx < self.drag_threshold and dy < self.drag_threshold:
                return
            self.drag_in_progress = True

        target_index = self.get_texture_index_at_pointer(event.x_root, event.y_root)
        if target_index is not None:
            self.drag_target_index = target_index
            self.update_drag_highlight(target_index)

    def on_texture_release(self, index: int, event):
        """Finish drag operation and reorder textures"""
        source_index = self.drag_source_index
        target_index = self.get_texture_index_at_pointer(event.x_root, event.y_root)
        was_dragging = self.drag_in_progress

        if target_index is None:
            target_index = self.drag_target_index

        self.clear_drag_highlights()
        self.drag_source_index = None
        self.drag_target_index = None
        self.drag_start_pos = None
        self.drag_in_progress = False

        if not was_dragging or source_index is None or target_index is None:
            return

        self.reorder_texture(source_index, target_index)

    def get_texture_index_at_pointer(self, x_root: int, y_root: int) -> Optional[int]:
        """Return texture index under the mouse pointer"""
        widget = self.winfo_containing(x_root, y_root)

        while widget is not None:
            if widget in self.widget_to_index:
                return self.widget_to_index[widget]

            parent_name = widget.winfo_parent()
            if not parent_name:
                break

            try:
                widget = widget._nametowidget(parent_name)
            except Exception:
                break

        return None

    def update_drag_highlight(self, target_index: int):
        """Highlight the current drag target tile"""
        self.clear_drag_highlights()
        if 0 <= target_index < len(self.texture_frames):
            self.texture_frames[target_index].configure(highlightthickness=2, highlightbackground='#f0a500')

    def clear_drag_highlights(self):
        """Remove drag target highlighting from all tiles"""
        for frame in self.texture_frames:
            frame.configure(highlightthickness=0)

    def reorder_texture(self, source_index: int, target_index: int):
        """Move a texture from source index to target index"""
        if source_index == target_index:
            return

        if not (0 <= source_index < len(self.wad.textures)):
            return

        if not (0 <= target_index < len(self.wad.textures)):
            return

        moved_texture = self.wad.textures.pop(source_index)
        self.wad.textures.insert(target_index, moved_texture)
        self.wad.modified = True

        self.selected_indices = {target_index}
        self.last_selected_index = target_index

        self.refresh()

        if self.editor:
            tab_id = str(self)
            self.editor.update_tab_title(tab_id)
            self.editor.set_status(f"Moved texture: {moved_texture.name}")
    
    def show_context_menu(self, index: int, frame: Frame, event):
        """Show context menu on right-click"""
        # Select the texture if not already selected
        if index not in self.selected_indices:
            self.select_texture(index, frame, None)
        
        # Create context menu
        menu = Menu(self, tearoff=0)
        menu.add_command(label="Copy Texture", command=self.editor.edit_copy)
        menu.add_command(label="Paste Texture", command=self.editor.edit_paste)
        menu.add_separator()
        menu.add_command(label="Delete", command=self.editor.edit_delete)
        menu.add_separator()
        menu.add_command(label="Rename Texture...", command=self.editor.edit_rename)
        menu.add_command(label="Resize Texture...", command=self.editor.edit_resize)
        menu.add_command(label="Reimport Texture...", command=self.editor.edit_reimport)
        menu.add_separator()
        menu.add_command(label="View in Separate Tab", command=self.editor.view_in_separate_tab)
        
        # Show menu at cursor position
        menu.tk_popup(event.x_root, event.y_root)
    
    def select_texture(self, index: int, frame: Frame, event=None):
        """Select a texture (supports Shift+click for range, Ctrl+click for toggle)"""
        shift_pressed = event and (event.state & 0x0001)  # Check if Shift key is pressed
        ctrl_pressed = event and (event.state & 0x0004)   # Check if Ctrl key is pressed
        
        if ctrl_pressed:
            # Toggle selection with Ctrl+click (for non-contiguous selection)
            if index in self.selected_indices:
                # Deselect this item
                self.selected_indices.remove(index)
                if index < len(self.texture_frames):
                    self.texture_frames[index].configure(relief=RAISED, borderwidth=2)
            else:
                # Add to selection
                self.selected_indices.add(index)
                frame.configure(relief=SUNKEN, borderwidth=4)
            
            self.last_selected_index = index
            
        elif shift_pressed and self.last_selected_index is not None:
            # Range selection with Shift+click
            start = min(self.last_selected_index, index)
            end = max(self.last_selected_index, index)
            
            # Clear previous selection
            for idx in self.selected_indices:
                if idx < len(self.texture_frames):
                    self.texture_frames[idx].configure(relief=RAISED, borderwidth=2)
            
            # Select range
            self.selected_indices = set(range(start, end + 1))
            for idx in self.selected_indices:
                if idx < len(self.texture_frames):
                    self.texture_frames[idx].configure(relief=SUNKEN, borderwidth=4)
        else:
            # Single selection (clear previous)
            for idx in self.selected_indices:
                if idx < len(self.texture_frames):
                    self.texture_frames[idx].configure(relief=RAISED, borderwidth=2)
            
            # Select new
            self.selected_indices = {index}
            frame.configure(relief=SUNKEN, borderwidth=4)
        
            self.last_selected_index = index
    
    def get_selected_textures(self) -> List[TextureData]:
        """Get all currently selected textures"""
        textures = []
        for idx in sorted(self.selected_indices):
            if 0 <= idx < len(self.wad.textures):
                textures.append(self.wad.textures[idx])
        return textures
    
    def get_selected_texture(self) -> Optional[TextureData]:
        """Get the first selected texture (for backward compatibility)"""
        textures = self.get_selected_textures()
        return textures[0] if textures else None
    
    def on_delete_key(self, event=None):
        """Handle Delete/Backspace key press"""
        self.delete_selected_textures()
    
    def delete_selected_textures(self):
        """Delete the currently selected textures"""
        if not self.selected_indices:
            return
        
        # Confirm deletion
        count = len(self.selected_indices)
        if count == 1:
            texture_name = self.wad.textures[list(self.selected_indices)[0]].name
            confirm = messagebox.askyesno(
                "Confirm Delete",
                f"Are you sure you want to delete texture '{texture_name}'?"
            )
        else:
            confirm = messagebox.askyesno(
                "Confirm Delete",
                f"Are you sure you want to delete {count} textures?"
            )
        
        if not confirm:
            return
        
        # Delete textures (in reverse order to maintain indices)
        for idx in sorted(self.selected_indices, reverse=True):
            if 0 <= idx < len(self.wad.textures):
                del self.wad.textures[idx]
        
        # Mark as modified
        self.wad.modified = True
        
        # Clear selection
        self.selected_indices.clear()
        self.last_selected_index = None
        
        # Refresh the display
        self.refresh()
        
        # Update tab title to show modified state
        if self.editor:
            tab_id = str(self)
            self.editor.update_tab_title(tab_id)
            if count == 1:
                self.editor.set_status(f"Deleted texture: {texture_name}")
            else:
                self.editor.set_status(f"Deleted {count} textures")


class ImportProgressTab(Frame):
    """Tab for showing import progress with non-blocking updates"""
    def __init__(self, parent, editor, target_wad_tab_id):
        super().__init__(parent)
        self.editor = editor
        self.target_wad_tab_id = target_wad_tab_id
        self.cancelled = False
        
        # Main container
        container = Frame(self, padx=30, pady=20)
        container.pack(fill=BOTH, expand=True)
        
        # Title
        self.title_label = Label(container, text="Importing Images", font=('Arial', 14, 'bold'))
        self.title_label.pack(pady=(0, 20))
        
        # Status label
        self.status_label = Label(container, text="Preparing...", font=('Arial', 11))
        self.status_label.pack(pady=10)
        
        # Progress bar frame
        progress_frame = Frame(container)
        progress_frame.pack(fill=X, pady=10)
        
        # Progress bar (3 pixels tall)
        bar_frame = Frame(progress_frame, height=3, bg='#d0d0d0')
        bar_frame.pack(fill=X)
        bar_frame.pack_propagate(False)
        
        self.progress_canvas = Canvas(bar_frame, height=3, bg='#d0d0d0', highlightthickness=0)
        self.progress_canvas.pack(fill=BOTH, expand=True)
        
        # Progress rectangle (initially 0 width)
        self.progress_rect = self.progress_canvas.create_rectangle(0, 0, 0, 3, fill='#0078d4', outline='')
        
        # Byte progress label
        self.byte_label = Label(container, text="0 / 0 (0%)", font=('Arial', 9))
        self.byte_label.pack(pady=(5, 20))
        
        # Current file label
        self.file_label = Label(container, text="", font=('Arial', 10), fg='#666')
        self.file_label.pack(pady=5)
        
        # Log text area
        log_frame = Frame(container)
        log_frame.pack(fill=BOTH, expand=True, pady=(10, 10))
        
        scrollbar = Scrollbar(log_frame)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        self.log_text = Text(log_frame, height=15, width=80, yscrollcommand=scrollbar.set, 
                            font=('Courier', 9), state=DISABLED)
        self.log_text.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.config(command=self.log_text.yview)
        
        # Button frame
        button_frame = Frame(container)
        button_frame.pack(pady=10)
        
        self.cancel_button = Button(button_frame, text="Cancel", command=self.cancel_import)
        self.cancel_button.pack(side=LEFT, padx=5)
        
        self.close_button = Button(button_frame, text="Close Tab", command=self.close_tab, state=DISABLED)
        self.close_button.pack(side=LEFT, padx=5)
    
    def log(self, message):
        """Add a message to the log"""
        self.log_text.config(state=NORMAL)
        self.log_text.insert(END, message + "\n")
        self.log_text.see(END)
        self.log_text.config(state=DISABLED)
        # Mirror import logs to the launching console for timing telemetry review.
        print(message, flush=True)
    
    def update_progress(self, current_bytes, total_bytes, current_file=None, file_num=None, total_files=None):
        """Update progress display"""
        # Update byte label
        percentage = int((current_bytes / total_bytes) * 100) if total_bytes > 0 else 0
        self.byte_label.config(text=f"{current_bytes:,} / {total_bytes:,} ({percentage}%)")
        
        # Update progress bar
        canvas_width = self.progress_canvas.winfo_width()
        if canvas_width > 1:  # Ensure canvas is rendered
            bar_width = int((current_bytes / total_bytes) * canvas_width) if total_bytes > 0 else 0
            self.progress_canvas.coords(self.progress_rect, 0, 0, bar_width, 3)
        
        # Update file label
        if current_file and file_num and total_files:
            self.file_label.config(text=f"Processing {file_num}/{total_files}: {current_file}")
        
        # Update status
        if file_num and total_files:
            self.status_label.config(text=f"Processing file {file_num} of {total_files}...")
    
    def complete(self, success_count, failed_count):
        """Mark import as complete"""
        self.cancel_button.config(state=DISABLED)
        self.close_button.config(state=NORMAL)
        
        if success_count > 0:
            self.title_label.config(text="Import Complete ✓", fg='#008000')
            self.status_label.config(text=f"Successfully imported {success_count} image(s)")
        else:
            self.title_label.config(text="Import Failed ✗", fg='#cc0000')
            self.status_label.config(text="No images could be imported")
        
        if failed_count > 0:
            self.log(f"\n{failed_count} file(s) failed to import. See errors above.")
    
    def cancel_import(self):
        """Cancel the import operation"""
        self.cancelled = True
        self.cancel_button.config(state=DISABLED)
        self.status_label.config(text="Cancelling...")
        self.log("\nImport cancelled by user")
    
    def close_tab(self):
        """Close this progress tab"""
        self.editor._destroy_notebook_tab(str(self))


class PaletteEditorTab(Frame):
    """Tab for editing a full 256-color Quake palette."""
    def __init__(self, parent, editor, palette_values: Optional[List[int]] = None, on_palette_changed=None):
        super().__init__(parent)
        self.editor = editor
        self.on_palette_changed = on_palette_changed
        self.palette = self._normalize_palette(palette_values)
        self.columns = PALETTE_GRID_COLUMNS
        self.cell_size = 28
        self.cell_padding = 2
        self.swatch_size = self.cell_size - (self.cell_padding * 2)
        self.selected_index: Optional[int] = None
        self.swatch_ids: Dict[int, int] = {}

        container = Frame(self, padx=14, pady=12)
        container.pack(fill=BOTH, expand=True)

        Label(
            container,
            text='Click any color swatch to edit that palette entry.',
            anchor='w',
            font=('Arial', 10),
        ).pack(fill=X, pady=(0, 8))

        canvas_size = self.columns * self.cell_size
        self.palette_canvas = Canvas(
            container,
            width=canvas_size,
            height=canvas_size,
            bg='#2b2b2b',
            highlightthickness=1,
            highlightbackground='#555',
        )
        self.palette_canvas.pack(anchor='w')

        self.info_label = Label(
            container,
            text='No color selected',
            anchor='w',
            font=('Arial', 10),
        )
        self.info_label.pack(fill=X, pady=(10, 10))

        button_frame = Frame(container)
        button_frame.pack(fill=X)
        Button(button_frame, text='Export Custom Palette', command=self.export_palette).pack(side=LEFT, padx=(0, 8))
        Button(button_frame, text='Load Custom Palette', command=self.load_palette).pack(side=LEFT)

        self._draw_palette()

    def _normalize_palette(self, palette_values: Optional[List[int]]) -> List[int]:
        """Normalize palette values to exactly 768 bytes (256 RGB triplets)."""
        if palette_values is None:
            palette_values = fcwadtool.QUAKE_PALETTE

        normalized = []
        for value in list(palette_values)[:PALETTE_LMP_BYTE_COUNT]:
            try:
                channel = int(value)
            except Exception:
                channel = 0
            normalized.append(max(0, min(255, channel)))

        if len(normalized) < PALETTE_LMP_BYTE_COUNT:
            normalized.extend([0] * (PALETTE_LMP_BYTE_COUNT - len(normalized)))

        return normalized

    def _get_rgb(self, color_index: int) -> Tuple[int, int, int]:
        """Return RGB tuple for a palette index."""
        offset = color_index * 3
        return (
            self.palette[offset],
            self.palette[offset + 1],
            self.palette[offset + 2],
        )

    def _rgb_to_hex(self, rgb: Tuple[int, int, int]) -> str:
        """Format RGB values as a CSS-style hex color."""
        return f'#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}'

    def _set_info_for_index(self, color_index: int):
        """Update the selected-color info label."""
        r, g, b = self._get_rgb(color_index)
        self.info_label.config(text=f'Color {color_index}: RGB({r}, {g}, {b})')

    def _highlight_selected(self):
        """Highlight the selected swatch."""
        for index, swatch_id in self.swatch_ids.items():
            if index == self.selected_index:
                self.palette_canvas.itemconfig(swatch_id, outline='#ffffff', width=2)
            else:
                self.palette_canvas.itemconfig(swatch_id, outline='#1a1a1a', width=1)

    def _notify_palette_changed(self):
        """Forward palette updates to the owner/editor."""
        if callable(self.on_palette_changed):
            self.on_palette_changed(self.palette[:])

    def _draw_palette(self):
        """Render the 16x16 palette grid."""
        self.palette_canvas.delete('all')
        self.swatch_ids = {}

        for color_index in range(PALETTE_GRID_COLOR_COUNT):
            row = color_index // self.columns
            col = color_index % self.columns

            x0 = col * self.cell_size + self.cell_padding
            y0 = row * self.cell_size + self.cell_padding
            x1 = x0 + self.swatch_size
            y1 = y0 + self.swatch_size

            swatch_id = self.palette_canvas.create_rectangle(
                x0,
                y0,
                x1,
                y1,
                fill=self._rgb_to_hex(self._get_rgb(color_index)),
                outline='#1a1a1a',
                width=1,
            )
            self.swatch_ids[color_index] = swatch_id
            self.palette_canvas.tag_bind(
                swatch_id,
                '<Button-1>',
                lambda _event, idx=color_index: self.edit_color(idx)
            )

        self._highlight_selected()

    def _clamp_rgb(self, rgb_values: Tuple[float, float, float]) -> Tuple[int, int, int]:
        """Clamp RGB channel values into 8-bit range."""
        return (
            max(0, min(255, int(round(rgb_values[0])))),
            max(0, min(255, int(round(rgb_values[1])))),
            max(0, min(255, int(round(rgb_values[2])))),
        )

    def _set_palette_rgb(self, color_index: int, rgb: Tuple[int, int, int]):
        """Apply an RGB color to a palette index and refresh that swatch."""
        if color_index < 0 or color_index >= PALETTE_GRID_COLOR_COUNT:
            return

        offset = color_index * 3
        self.palette[offset] = rgb[0]
        self.palette[offset + 1] = rgb[1]
        self.palette[offset + 2] = rgb[2]

        swatch_id = self.swatch_ids.get(color_index)
        if swatch_id is not None:
            self.palette_canvas.itemconfig(swatch_id, fill=self._rgb_to_hex(rgb))

    def _apply_fade_gradient(
        self,
        start_index: int,
        source_rgb: Tuple[int, int, int],
        direction: int,
        steps: int,
    ) -> List[int]:
        """Apply a linear brightness fade from source color down to 10% brightness."""
        changed_indices: List[int] = []
        final_brightness = 0.10

        for offset in range(steps + 1):
            color_index = start_index + (direction * offset)
            if color_index < 0 or color_index >= PALETTE_GRID_COLOR_COUNT:
                break

            if steps <= 0:
                brightness = 1.0
            else:
                fade_ratio = offset / float(steps)
                brightness = 1.0 - ((1.0 - final_brightness) * fade_ratio)

            faded_rgb = (
                source_rgb[0] * brightness,
                source_rgb[1] * brightness,
                source_rgb[2] * brightness,
            )
            self._set_palette_rgb(color_index, self._clamp_rgb(faded_rgb))
            changed_indices.append(color_index)

        return changed_indices

    def edit_color(self, color_index: int):
        """Open a color edit dialog with optional gradient fade controls."""
        self.selected_index = color_index
        self._highlight_selected()
        self._set_info_for_index(color_index)
        dialog = None

        try:
            parent_window = self.winfo_toplevel()
            dialog = Toplevel(parent_window)
            dialog.title(f'Edit Quake Palette Color {color_index}')
            dialog.geometry('420x260')
            dialog.minsize(420, 260)
            dialog.resizable(False, False)
            dialog.transient(parent_window)

            frame = Frame(dialog, padx=14, pady=12)
            frame.pack(fill=BOTH, expand=True)

            current_rgb = self._get_rgb(color_index)
            selected_rgb = [current_rgb[0], current_rgb[1], current_rgb[2]]
            fade_var = BooleanVar(value=False)
            direction_var = StringVar(value='Fade Right')
            steps_var = StringVar(value='15')

            Label(frame, text=f'Palette Index: {color_index}', font=('Arial', 10, 'bold')).pack(anchor=W, pady=(0, 10))

            color_row = Frame(frame)
            color_row.pack(fill=X, pady=(0, 10))

            preview = Canvas(color_row, width=26, height=26, highlightthickness=1, highlightbackground='#333')
            preview.configure(bg=self._rgb_to_hex(tuple(selected_rgb)))
            preview.pack(side=LEFT, padx=(0, 10))

            color_label_var = StringVar(value=f'RGB({selected_rgb[0]}, {selected_rgb[1]}, {selected_rgb[2]})')
            Label(color_row, textvariable=color_label_var, anchor='w').pack(side=LEFT, fill=X, expand=True)

            def choose_color():
                selected_color = colorchooser.askcolor(
                    color=tuple(selected_rgb),
                    title=f'Pick Color for Index {color_index}',
                    parent=dialog,
                )
                if not selected_color or selected_color[0] is None:
                    return

                rgb = self._clamp_rgb(selected_color[0])
                selected_rgb[0], selected_rgb[1], selected_rgb[2] = rgb
                preview.configure(bg=self._rgb_to_hex(rgb))
                color_label_var.set(f'RGB({rgb[0]}, {rgb[1]}, {rgb[2]})')

            Button(color_row, text='Pick Color...', command=choose_color).pack(side=RIGHT)

            fade_check = Checkbutton(frame, text='Fade this color', variable=fade_var)
            fade_check.pack(anchor=W, pady=(4, 8))

            fade_controls = Frame(frame)
            fade_controls.pack(fill=X, pady=(0, 8))

            Label(fade_controls, text='Direction').grid(row=0, column=0, sticky='w')
            direction_combo = ttk.Combobox(
                fade_controls,
                textvariable=direction_var,
                values=['Fade Right', 'Fade Left'],
                state='readonly',
                width=16,
            )
            direction_combo.grid(row=0, column=1, padx=(8, 16), sticky='w')

            Label(fade_controls, text='Steps').grid(row=0, column=2, sticky='w')
            steps_entry = Entry(fade_controls, textvariable=steps_var, width=8)
            steps_entry.grid(row=0, column=3, padx=(8, 0), sticky='w')

            Label(
                frame,
                text='Steps default to 15: source color + 15 faded colors ending at 10% brightness.',
                fg='#555',
                anchor='w',
                justify=LEFT,
            ).pack(fill=X, pady=(0, 12))

            def update_fade_controls(_event=None):
                widget_state = NORMAL if fade_var.get() else DISABLED
                direction_combo.config(state='readonly' if fade_var.get() else DISABLED)
                steps_entry.config(state=widget_state)

            fade_check.config(command=update_fade_controls)
            update_fade_controls()

            button_frame = Frame(frame)
            button_frame.pack(fill=X)

            def apply_changes():
                base_rgb = (selected_rgb[0], selected_rgb[1], selected_rgb[2])

                if fade_var.get():
                    try:
                        steps = int(steps_var.get().strip())
                    except Exception:
                        messagebox.showerror('Invalid Steps', 'Steps must be a whole number.')
                        return

                    if steps < 0 or steps > 255:
                        messagebox.showerror('Invalid Steps', 'Steps must be between 0 and 255.')
                        return

                    direction = 1 if direction_var.get() == 'Fade Right' else -1
                    changed_indices = self._apply_fade_gradient(color_index, base_rgb, direction, steps)
                    if not changed_indices:
                        messagebox.showerror('Error', 'No palette indices were updated.')
                        return

                    self._set_info_for_index(color_index)
                    self._notify_palette_changed()

                    applied_fade_steps = max(0, len(changed_indices) - 1)
                    status_msg = (
                        f'Applied fade from color {color_index} ({direction_var.get()}) '
                        f'for {applied_fade_steps} step(s).'
                    )
                    if applied_fade_steps < steps:
                        status_msg = status_msg + ' Reached palette boundary before all steps were applied.'

                    self.editor.set_status(status_msg)
                else:
                    if base_rgb == current_rgb:
                        dialog.destroy()
                        return

                    self._set_palette_rgb(color_index, base_rgb)
                    self._set_info_for_index(color_index)
                    self._notify_palette_changed()
                    self.editor.set_status(
                        f'Updated palette color {color_index} to RGB({base_rgb[0]}, {base_rgb[1]}, {base_rgb[2]})'
                    )

                dialog.destroy()

            Button(button_frame, text='Apply', command=apply_changes, width=10).pack(side=LEFT)
            Button(button_frame, text='Cancel', command=dialog.destroy, width=10).pack(side=RIGHT)

            dialog.bind('<Return>', lambda _event: apply_changes())
            dialog.bind('<Escape>', lambda _event: dialog.destroy())

            # Ensure widgets are realized before making the dialog modal.
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
            y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
            dialog.geometry(f'+{x}+{y}')
            dialog.deiconify()
            dialog.wait_visibility()
            dialog.grab_set()
            dialog.focus_force()

        except Exception as e:
            if dialog is not None and dialog.winfo_exists():
                dialog.destroy()

            messagebox.showerror(
                'Palette Edit Error',
                f'Unable to open the color edit dialog. Falling back to direct color picker.\n\n{str(e)}',
            )

            fallback_color = colorchooser.askcolor(
                color=self._get_rgb(color_index),
                title=f'Edit Quake Palette Color {color_index}',
                parent=self.winfo_toplevel(),
            )
            if not fallback_color or fallback_color[0] is None:
                return

            fallback_rgb = self._clamp_rgb(fallback_color[0])
            self._set_palette_rgb(color_index, fallback_rgb)
            self._set_info_for_index(color_index)
            self._notify_palette_changed()
            self.editor.set_status(
                f'Updated palette color {color_index} to RGB({fallback_rgb[0]}, {fallback_rgb[1]}, {fallback_rgb[2]})'
            )

    def export_palette(self):
        """Export palette as Quake palette.lmp-compatible raw RGB bytes."""
        filepath = filedialog.asksaveasfilename(
            title='Export Custom Palette',
            defaultextension='.lmp',
            filetypes=[('Quake Palette Files', '*.lmp'), ('All Files', '*.*')],
            initialdir=self.editor.get_dialog_initial_dir(),
        )

        if not filepath:
            return

        self.editor.update_last_folder(filepath)

        try:
            with open(filepath, 'wb') as f:
                f.write(bytes(self.palette[:PALETTE_LMP_BYTE_COUNT]))
            self.editor.set_status(f'Exported custom palette: {filepath}')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to export custom palette:\n{str(e)}')

    def load_palette(self):
        """Load palette from a Quake palette.lmp-compatible file."""
        filepath = filedialog.askopenfilename(
            title='Load Custom Palette',
            filetypes=[('Quake Palette Files', '*.lmp'), ('All Files', '*.*')],
            initialdir=self.editor.get_dialog_initial_dir(),
        )

        if not filepath:
            return

        self.editor.update_last_folder(filepath)

        try:
            self.palette = self.editor._load_palette_lmp_file(filepath)
            self._draw_palette()
            if self.selected_index is not None:
                self._set_info_for_index(self.selected_index)
            else:
                self.info_label.config(text='Palette loaded. Click any color swatch to edit.')

            self._notify_palette_changed()
            self.editor.options['custom_palette_file'] = str(Path(filepath).expanduser())
            self.editor.save_options()
            self.editor.set_status(f'Loaded custom palette: {filepath}')

        except ValueError as e:
            messagebox.showerror('Invalid Palette File', str(e))
        except Exception as e:
            messagebox.showerror('Error', f'Failed to load custom palette:\n{str(e)}')


class WADEditor:
    """Main application window"""
    def __init__(self, root):
        self.root = root
        self.root.title("Quake WAD Editor")
        self.root.geometry("1024x768")
        
        # Style configuration
        style = ttk.Style()
        style.theme_use('default')
        
        # Data structures
        self.wad_files: Dict[str, WADFile] = {}  # tab_id -> WADFile
        self.clipboard_textures: List[Tuple[str, int, int, bytes, List[int]]] = []
        self.palette_editor_tab_id: Optional[str] = None
        self.display_palette_file: str = ''
        self.options_path = Path(__file__).resolve().parent / OPTIONS_FILENAME
        self.options = self.load_options()
        self.custom_palette = self._normalize_palette_values(
            self.options.get('custom_palette_data', DEFAULT_EDITOR_OPTIONS['custom_palette_data'])
        )

        if not self.options.get('custom_palette_data'):
            custom_palette_file = self.get_custom_palette_file().strip()
            if custom_palette_file:
                try:
                    self.custom_palette = self._load_palette_lmp_file(custom_palette_file)
                    self.options['custom_palette_data'] = self.custom_palette[:]
                    self.save_options()
                except Exception as e:
                    print(f"Warning: Failed to load configured custom palette file: {e}")
        
        # Create menu bar
        self.create_menu()
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=BOTH, expand=True)
        
        # Status bar
        self.status_bar = Label(self.root, text="Ready", bd=1, relief=SUNKEN, anchor=W)
        self.status_bar.pack(side=BOTTOM, fill=X)
        
        # Bind tab change event
        self.notebook.bind('<<NotebookTabChanged>>', self.on_tab_changed)
        
        # Bind right-click on tabs for close menu
        self.notebook.bind('<Button-3>', self.on_tab_right_click)
        # Bind middle-click on tabs for quick close
        self.notebook.bind('<Button-2>', self.on_tab_middle_click)
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_menu(self):
        """Create the menu bar"""
        menubar = Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New...", command=self.file_new, accelerator="Ctrl+N")
        file_menu.add_command(label="Open...", command=self.file_open, accelerator="Ctrl+O")
        file_menu.add_command(label="Save", command=self.file_save, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As...", command=self.file_save_as)
        file_menu.add_command(label="Preferences...", command=self.file_preferences)
        file_menu.add_separator()
        file_menu.add_command(label="Import from WAD...", command=self.file_import)
        file_menu.add_command(label="Import Image(s)...", command=self.file_import_images)
        file_menu.add_command(label="Add Wad To Blacklist", command=self.file_add_wad_to_blacklist)
        file_menu.add_command(label="Export...", command=self.file_export)
        file_menu.add_command(label="Export Texture List", command=self.file_export_texture_list)
        file_menu.add_command(
            label="Export Image or Sequence as Sprite...",
            command=self.file_export_sprite,
        )
        file_menu.add_separator()
        file_menu.add_command(label="Close Tab", command=self.file_close, accelerator="Ctrl+W")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        
        # Edit menu
        edit_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Copy Texture", command=self.edit_copy, accelerator="Ctrl+C")
        edit_menu.add_command(label="Paste Texture", command=self.edit_paste, accelerator="Ctrl+V")
        edit_menu.add_separator()
        edit_menu.add_command(label="Delete", command=self.edit_delete, accelerator="Delete")
        edit_menu.add_separator()
        edit_menu.add_command(
            label="Remove Blacklisted Textures",
            command=self.edit_remove_blacklisted_textures,
        )
        edit_menu.add_separator()
        edit_menu.add_command(label="Rename Texture...", command=self.edit_rename)
        edit_menu.add_command(label="Resize Texture...", command=self.edit_resize)
        edit_menu.add_command(label="Reimport Texture...", command=self.edit_reimport)
        edit_menu.add_command(label="Edit Quake Palette", command=self.edit_quake_palette)
        edit_menu.add_command(label="Sort Textures Alphabetically", command=self.edit_sort_textures_alphabetically)
        
        # View menu
        self.view_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=self.view_menu)
        self.view_menu.add_command(label="Zoom In", command=self.view_zoom_in, accelerator="Ctrl++")
        self.view_menu.add_command(label="Zoom Out", command=self.view_zoom_out, accelerator="Ctrl+-")
        self.view_menu.add_separator()
        self.view_menu.add_command(label="Set Icon Size...", command=self.view_set_icon_size)

        self.image_zoom_levels = (25, 50, 75, 100, 200, 400)
        self.image_zoom_menu_label = "Set Image Zoom Level"
        self.image_zoom_menu = Menu(self.view_menu, tearoff=0)
        for zoom_level in self.image_zoom_levels:
            self.image_zoom_menu.add_command(
                label=f"{zoom_level}%",
                command=lambda value=zoom_level: self.view_set_image_zoom_level(value),
            )
        self.view_menu.add_cascade(label=self.image_zoom_menu_label, menu=self.image_zoom_menu)
        self.view_menu.entryconfig(self.image_zoom_menu_label, state=DISABLED)

        self.view_original_image_label = "View Original Image"
        self.view_tiled_image_label = "View Tiled Image"
        self.view_menu.add_command(label=self.view_original_image_label, command=self.view_original_image)
        self.view_menu.add_command(label=self.view_tiled_image_label, command=self.view_tiled_image)
        self.view_menu.entryconfig(self.view_original_image_label, state=DISABLED)
        self.view_menu.entryconfig(self.view_tiled_image_label, state=DISABLED)

        self.view_menu.add_separator()
        self.view_menu.add_command(label="Display Using Custom Palette...", command=self.view_display_using_custom_palette)
        self.view_menu.add_command(label="Clear Custom Palette", command=self.view_clear_custom_palette)
        self.view_menu.add_separator()
        self.view_menu.add_command(label="View in Separate Tab", command=self.view_in_separate_tab)
        
        # Keyboard shortcuts
        self.root.bind('<Control-n>', lambda e: self.file_new())
        self.root.bind('<Control-o>', lambda e: self.file_open())
        self.root.bind('<Control-s>', lambda e: self.file_save())
        self.root.bind('<Control-w>', lambda e: self.file_close())
        self.root.bind('<Control-c>', lambda e: self.edit_copy())
        self.root.bind('<Control-v>', lambda e: self.edit_paste())
        # Zoom shortcuts (handle both + and = keys, and - key)
        self.root.bind('<Control-plus>', lambda e: self.view_zoom_in())
        self.root.bind('<Control-equal>', lambda e: self.view_zoom_in())
        self.root.bind('<Control-KP_Add>', lambda e: self.view_zoom_in())  # Numpad +
        self.root.bind('<Control-minus>', lambda e: self.view_zoom_out())
        self.root.bind('<Control-KP_Subtract>', lambda e: self.view_zoom_out())  # Numpad -

    def load_options(self) -> Dict:
        """Load persisted editor options from disk."""
        loaded_data = {}

        if self.options_path.exists():
            try:
                with open(self.options_path, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load {self.options_path.name}: {e}")

        options = self._normalize_options(loaded_data)

        # Ensure options file exists and stays normalized.
        self.options = options
        self.save_options()
        return options

    def _normalize_palette_values(self, palette_values, allow_empty: bool = False) -> List[int]:
        """Normalize palette values to 768 integers (or empty when allowed)."""
        if not isinstance(palette_values, list):
            palette_values = []

        normalized = []
        for value in palette_values[:PALETTE_LMP_BYTE_COUNT]:
            try:
                channel = int(value)
            except Exception:
                channel = 0
            normalized.append(max(0, min(255, channel)))

        if not normalized:
            if allow_empty:
                return []
            normalized = list(fcwadtool.QUAKE_PALETTE[:PALETTE_LMP_BYTE_COUNT])

        if len(normalized) < PALETTE_LMP_BYTE_COUNT:
            normalized.extend([0] * (PALETTE_LMP_BYTE_COUNT - len(normalized)))

        return normalized[:PALETTE_LMP_BYTE_COUNT]

    def _load_palette_lmp_file(self, filepath: str) -> List[int]:
        """Load and validate a Quake palette.lmp file (raw 768-byte RGB table)."""
        with open(filepath, 'rb') as f:
            raw_palette = f.read()

        if len(raw_palette) != PALETTE_LMP_BYTE_COUNT:
            raise ValueError(
                (
                    'This file is not a valid Quake palette.lmp file.\n\n'
                    f'Expected {PALETTE_LMP_BYTE_COUNT} bytes (256 RGB colors), '
                    f'but found {len(raw_palette)} bytes.'
                )
            )

        return self._normalize_palette_values(list(raw_palette))

    def _normalize_options(self, data: Dict) -> Dict:
        """Normalize options content and fill defaults."""
        if not isinstance(data, dict):
            data = {}

        palette_mode = data.get('palette_mode', DEFAULT_EDITOR_OPTIONS['palette_mode'])
        if palette_mode not in PALETTE_MODE_TO_LABEL:
            palette_mode = DEFAULT_EDITOR_OPTIONS['palette_mode']

        dithering_mode = data.get('dithering_mode', DEFAULT_EDITOR_OPTIONS['dithering_mode'])
        try:
            dithering_mode = int(dithering_mode)
        except Exception:
            dithering_mode = DEFAULT_EDITOR_OPTIONS['dithering_mode']
        if dithering_mode not in DITHERING_INDEX_TO_LABEL:
            dithering_mode = DEFAULT_EDITOR_OPTIONS['dithering_mode']

        custom_palette_file = data.get('custom_palette_file', DEFAULT_EDITOR_OPTIONS['custom_palette_file'])
        if not isinstance(custom_palette_file, str):
            custom_palette_file = DEFAULT_EDITOR_OPTIONS['custom_palette_file']

        custom_palette_include_fullbrights_raw = data.get(
            'custom_palette_include_fullbrights',
            DEFAULT_EDITOR_OPTIONS['custom_palette_include_fullbrights']
        )
        if isinstance(custom_palette_include_fullbrights_raw, str):
            custom_palette_include_fullbrights = (
                custom_palette_include_fullbrights_raw.strip().lower() in {'1', 'true', 'yes', 'on'}
            )
        else:
            custom_palette_include_fullbrights = bool(custom_palette_include_fullbrights_raw)

        custom_palette_data = self._normalize_palette_values(
            data.get('custom_palette_data', DEFAULT_EDITOR_OPTIONS['custom_palette_data']),
            allow_empty=True,
        )

        last_folder = data.get('last_folder', DEFAULT_EDITOR_OPTIONS['last_folder'])
        if not isinstance(last_folder, str):
            last_folder = DEFAULT_EDITOR_OPTIONS['last_folder']

        recent_files_raw = data.get('recent_files', DEFAULT_EDITOR_OPTIONS['recent_files'])
        if not isinstance(recent_files_raw, list):
            recent_files_raw = []
        recent_files = []
        for filepath in recent_files_raw:
            if isinstance(filepath, str) and filepath not in recent_files:
                recent_files.append(filepath)
        recent_files = recent_files[:10]

        return {
            'palette_mode': palette_mode,
            'dithering_mode': dithering_mode,
            'custom_palette_file': custom_palette_file,
            'custom_palette_include_fullbrights': custom_palette_include_fullbrights,
            'custom_palette_data': custom_palette_data,
            'last_folder': last_folder,
            'recent_files': recent_files,
        }

    def save_options(self):
        """Persist current editor options to disk."""
        try:
            with open(self.options_path, 'w', encoding='utf-8') as f:
                json.dump(self.options, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save {self.options_path.name}: {e}")

    def get_dialog_initial_dir(self) -> str:
        """Return default folder used by file chooser dialogs."""
        folder = self.options.get('last_folder', '')
        if folder and Path(folder).is_dir():
            return folder
        return str(Path.cwd())

    def update_last_folder(self, selected_path: str):
        """Update and persist the last-used folder from a selected path."""
        if not selected_path:
            return

        candidate = Path(selected_path).expanduser()
        folder = candidate if candidate.is_dir() else candidate.parent
        if not str(folder):
            return

        try:
            normalized = str(folder.resolve())
        except Exception:
            normalized = str(folder)

        if self.options.get('last_folder') != normalized:
            self.options['last_folder'] = normalized
            self.save_options()

    def add_recent_file(self, filepath: Optional[str]):
        """Add a file path to recent edited files list (max 10)."""
        if not filepath:
            return

        try:
            normalized = str(Path(filepath).expanduser().resolve())
        except Exception:
            normalized = str(filepath)

        recent_files = [p for p in self.options.get('recent_files', []) if p != normalized]
        recent_files.insert(0, normalized)
        recent_files = recent_files[:10]

        if recent_files != self.options.get('recent_files', []):
            self.options['recent_files'] = recent_files
            self.save_options()

    def get_import_palette_mode(self) -> str:
        """Get the configured palette mode for image import paths."""
        palette_mode = self.options.get('palette_mode', DEFAULT_EDITOR_OPTIONS['palette_mode'])
        if palette_mode not in PALETTE_MODE_TO_LABEL:
            return DEFAULT_EDITOR_OPTIONS['palette_mode']
        return palette_mode

    def get_custom_palette_file(self) -> str:
        """Get configured custom palette source file path."""
        palette_file = self.options.get('custom_palette_file', DEFAULT_EDITOR_OPTIONS['custom_palette_file'])
        if not isinstance(palette_file, str):
            return DEFAULT_EDITOR_OPTIONS['custom_palette_file']
        return palette_file

    def get_custom_palette_include_fullbrights(self) -> bool:
        """Return whether custom palette import includes fullbright range (224-255)."""
        value = self.options.get(
            'custom_palette_include_fullbrights',
            DEFAULT_EDITOR_OPTIONS['custom_palette_include_fullbrights'],
        )
        if isinstance(value, str):
            return value.strip().lower() in {'1', 'true', 'yes', 'on'}
        return bool(value)

    def get_import_palette_settings(self) -> Tuple[str, Optional[List[int]], bool]:
        """Resolve palette settings used by import, reimport, and resize flows."""
        palette_mode = self.get_import_palette_mode()
        include_fullbrights = self.get_custom_palette_include_fullbrights()
        custom_palette = None

        if palette_mode == fcwadtool.PALETTE_MODE_CUSTOM:
            custom_palette = self._normalize_palette_values(self.custom_palette)

        return palette_mode, custom_palette, include_fullbrights

    def get_import_dithering_mode(self) -> int:
        """Get the configured dithering mode index for image import paths."""
        dithering_mode = self.options.get('dithering_mode', DEFAULT_EDITOR_OPTIONS['dithering_mode'])
        try:
            dithering_mode = int(dithering_mode)
        except Exception:
            return DEFAULT_EDITOR_OPTIONS['dithering_mode']
        if dithering_mode not in DITHERING_INDEX_TO_LABEL:
            return DEFAULT_EDITOR_OPTIONS['dithering_mode']
        return dithering_mode

    def _palette_mode_label(self, palette_mode: str) -> str:
        """Get user-facing label for a palette mode."""
        return PALETTE_MODE_TO_LABEL.get(
            palette_mode,
            PALETTE_MODE_TO_LABEL[DEFAULT_EDITOR_OPTIONS['palette_mode']]
        )

    def _palette_mode_runtime_label(self, palette_mode: str, include_fullbrights: bool = False) -> str:
        """Get palette label with runtime fullbright behavior when using custom palettes."""
        base_label = self._palette_mode_label(palette_mode)
        if palette_mode == fcwadtool.PALETTE_MODE_CUSTOM:
            if include_fullbrights:
                return f"{base_label} (includes fullbrights 224-255)"
            return f"{base_label} (filters fullbrights 224-255)"
        return base_label

    def _dithering_mode_label(self, dithering_mode: int) -> str:
        """Get user-facing label for a dithering mode index."""
        return DITHERING_INDEX_TO_LABEL.get(
            dithering_mode,
            DITHERING_INDEX_TO_LABEL[DEFAULT_EDITOR_OPTIONS['dithering_mode']]
        )

    def _is_transparent_texture_name(self, texture_name: str) -> bool:
        """Return whether a texture name follows Quake transparent naming rules."""
        return bool(texture_name) and texture_name.startswith(fcwadtool.TRANSPARENT_TEXTURE_PREFIX)

    def _show_transparency_name_warning(self, texture_names: List[str]):
        """Warn when transparent textures are missing the leading '{' prefix."""
        unique_names = []
        for name in texture_names:
            if isinstance(name, str) and name and name not in unique_names:
                unique_names.append(name)

        if not unique_names:
            return

        preview_limit = 8
        preview_names = unique_names[:preview_limit]
        texture_list = '\n'.join(f"- {name}" for name in preview_names)
        if len(unique_names) > preview_limit:
            texture_list += f"\n- ... and {len(unique_names) - preview_limit} more"

        message = (
            f"{fcwadtool.TRANSPARENCY_NAME_WARNING}\n\n"
            "Transparent pixels were detected in:\n"
            f"{texture_list}"
        )
        messagebox.showwarning('Transparent Texture Naming', message)

    def file_preferences(self):
        """Open the preferences dialog."""
        dialog = Toplevel(self.root)
        dialog.title('Preferences')
        dialog.geometry('980x560')
        dialog.transient(self.root)
        dialog.grab_set()

        frame = Frame(dialog, padx=16, pady=14)
        frame.pack(fill=BOTH, expand=True)

        Label(frame, text='Palette', font=('Arial', 11, 'bold')).pack(anchor=W)
        palette_var = StringVar(value=self._palette_mode_label(self.get_import_palette_mode()))
        palette_combo = ttk.Combobox(
            frame,
            textvariable=palette_var,
            values=[label for label, _mode in PALETTE_OPTION_ITEMS],
            state='readonly',
            width=90,
        )
        palette_combo.pack(fill=X, pady=(4, 14))

        Label(frame, text='Dithering type', font=('Arial', 11, 'bold')).pack(anchor=W)
        dithering_var = StringVar(value=self._dithering_mode_label(self.get_import_dithering_mode()))
        dithering_combo = ttk.Combobox(
            frame,
            textvariable=dithering_var,
            values=[label for label, _index in DITHERING_OPTION_ITEMS],
            state='readonly',
            width=140,
        )
        dithering_combo.pack(fill=X, pady=(4, 14))

        custom_palette_frame = LabelFrame(frame, text='Custom Palette Import Settings', padx=10, pady=8)
        custom_palette_frame.pack(fill=X, pady=(0, 14))

        custom_palette_file_var = StringVar(value=self.get_custom_palette_file())
        path_row = Frame(custom_palette_frame)
        path_row.pack(fill=X, pady=(0, 6))

        Label(path_row, text='Palette file (.lmp):').pack(side=LEFT, padx=(0, 8))
        custom_palette_entry = Entry(path_row, textvariable=custom_palette_file_var)
        custom_palette_entry.pack(side=LEFT, fill=X, expand=True)

        def browse_custom_palette():
            filepath = filedialog.askopenfilename(
                title='Select Custom Palette (.lmp)',
                filetypes=[('Quake Palette Files', '*.lmp'), ('All Files', '*.*')],
                initialdir=self.get_dialog_initial_dir(),
            )
            if filepath:
                custom_palette_file_var.set(filepath)
                self.update_last_folder(filepath)

        browse_palette_button = Button(path_row, text='Browse...', command=browse_custom_palette, width=10)
        browse_palette_button.pack(side=LEFT, padx=(8, 0))

        include_fullbrights_var = BooleanVar(value=self.get_custom_palette_include_fullbrights())
        include_fullbrights_checkbox = Checkbutton(
            custom_palette_frame,
            text='Include fullbrights in this import',
            variable=include_fullbrights_var,
            anchor='w',
            justify=LEFT,
        )
        include_fullbrights_checkbox.pack(anchor=W, pady=(0, 4))

        Label(
            custom_palette_frame,
            text='When unchecked, importer remaps colors to avoid Quake fullbright indices 224-255.',
            fg='#555',
            anchor='w',
            justify=LEFT,
        ).pack(fill=X)

        last_folder_text = self.options.get('last_folder', '') or '(not set yet)'
        Label(frame, text=f"Last Folder: {last_folder_text}", fg='#555', anchor='w').pack(fill=X, pady=(0, 8))

        Label(frame, text='Last 10 edited files', font=('Arial', 10, 'bold')).pack(anchor=W)
        recent_frame = Frame(frame)
        recent_frame.pack(fill=BOTH, expand=True, pady=(4, 10))

        recent_scrollbar = Scrollbar(recent_frame)
        recent_scrollbar.pack(side=RIGHT, fill=Y)

        recent_list = Listbox(recent_frame, height=7, yscrollcommand=recent_scrollbar.set)
        recent_list.pack(side=LEFT, fill=BOTH, expand=True)
        recent_scrollbar.config(command=recent_list.yview)

        for recent_file in self.options.get('recent_files', []):
            recent_list.insert(END, recent_file)
        if recent_list.size() == 0:
            recent_list.insert(END, '(no edited files tracked yet)')

        def update_custom_palette_controls(_event=None):
            selected_palette_mode = PALETTE_LABEL_TO_MODE.get(
                palette_var.get(),
                DEFAULT_EDITOR_OPTIONS['palette_mode']
            )

            if selected_palette_mode == fcwadtool.PALETTE_MODE_CUSTOM:
                widget_state = NORMAL
            else:
                widget_state = DISABLED

            custom_palette_entry.config(state=widget_state)
            browse_palette_button.config(state=widget_state)
            include_fullbrights_checkbox.config(state=widget_state)

        palette_combo.bind('<<ComboboxSelected>>', update_custom_palette_controls)
        update_custom_palette_controls()

        button_frame = Frame(frame)
        button_frame.pack(fill=X)

        def save_preferences():
            selected_palette = PALETTE_LABEL_TO_MODE.get(
                palette_var.get(),
                DEFAULT_EDITOR_OPTIONS['palette_mode']
            )
            selected_dithering = DITHERING_LABEL_TO_INDEX.get(
                dithering_var.get(),
                DEFAULT_EDITOR_OPTIONS['dithering_mode']
            )

            selected_custom_palette_file = custom_palette_file_var.get().strip()
            include_fullbrights = bool(include_fullbrights_var.get())

            if selected_custom_palette_file:
                try:
                    loaded_custom_palette = self._load_palette_lmp_file(selected_custom_palette_file)
                except ValueError as e:
                    messagebox.showerror('Invalid Custom Palette', str(e))
                    return
                except Exception as e:
                    messagebox.showerror('Error', f'Failed to load custom palette:\n{str(e)}')
                    return
                self.custom_palette = loaded_custom_palette
            else:
                # Keep current in-memory custom palette when no source file is set.
                self.custom_palette = self._normalize_palette_values(self.custom_palette)

            self.options['palette_mode'] = selected_palette
            self.options['dithering_mode'] = selected_dithering
            self.options['custom_palette_file'] = selected_custom_palette_file
            self.options['custom_palette_include_fullbrights'] = include_fullbrights
            self.options['custom_palette_data'] = self.custom_palette[:]
            self.save_options()
            dialog.destroy()
            self.set_status('Preferences saved')

        Button(button_frame, text='Save', command=save_preferences, width=10).pack(side=LEFT)
        Button(button_frame, text='Cancel', command=dialog.destroy, width=10).pack(side=RIGHT)

        dialog.bind('<Return>', lambda _event: save_preferences())
        dialog.bind('<Escape>', lambda _event: dialog.destroy())

    def _status_with_display_palette(self, message: str) -> str:
        """Append active display-palette indicator to status text when enabled."""
        if self.display_palette_file:
            return f"{message} | Display palette: {Path(self.display_palette_file).name}"
        return message

    def _get_current_tab_widget(self):
        """Return the active tab widget, if any."""
        if not hasattr(self, 'notebook'):
            return None

        current_tab = self.notebook.select()
        if not current_tab:
            return None

        try:
            return self.notebook.nametowidget(current_tab)
        except Exception:
            return None

    def _destroy_notebook_tab(self, tab_id: str):
        """Forget and destroy a notebook tab widget to free Tk/Python resources."""
        if not tab_id:
            return

        tab_widget = None
        try:
            tab_widget = self.notebook.nametowidget(tab_id)
        except Exception:
            tab_widget = None

        try:
            self.notebook.forget(tab_id)
        except Exception:
            pass

        if tab_widget is not None:
            try:
                tab_widget.destroy()
            except Exception:
                pass

    def _update_view_menu_state(self):
        """Enable/disable image-only View actions based on active tab type."""
        if not hasattr(self, 'view_menu'):
            return

        active_widget = self._get_current_tab_widget()
        image_menu_state = NORMAL if isinstance(active_widget, ImageViewerTab) else DISABLED
        original_state = image_menu_state
        tiled_state = image_menu_state

        if isinstance(active_widget, ImageViewerTab):
            if active_widget.is_tiled_view:
                tiled_state = DISABLED
                original_state = NORMAL
            else:
                original_state = DISABLED
                tiled_state = NORMAL

        try:
            self.view_menu.entryconfig(self.image_zoom_menu_label, state=image_menu_state)
        except Exception:
            pass

        try:
            self.view_menu.entryconfig(self.view_original_image_label, state=original_state)
            self.view_menu.entryconfig(self.view_tiled_image_label, state=tiled_state)
        except Exception:
            pass

    def _refresh_all_texture_views(self):
        """Regenerate texture previews and refresh all open WAD/image tabs."""
        for wad in self.wad_files.values():
            for texture in wad.textures:
                texture._generate_image()

        for tab_id in self.notebook.tabs():
            widget = self.notebook.nametowidget(tab_id)
            if isinstance(widget, WADViewerTab):
                widget.refresh()
            elif isinstance(widget, ImageViewerTab):
                widget.update_image()

    def view_display_using_custom_palette(self):
        """Load a display-only custom palette and refresh open tabs."""
        filepath = filedialog.askopenfilename(
            title='Select Display Palette (.lmp)',
            filetypes=[('Quake Palette Files', '*.lmp'), ('All Files', '*.*')],
            initialdir=self.get_dialog_initial_dir(),
        )

        if not filepath:
            return

        self.update_last_folder(filepath)

        try:
            display_palette = self._load_palette_lmp_file(filepath)
            TextureData.set_display_palette_override(display_palette)
            self.display_palette_file = str(Path(filepath).expanduser())
            self._refresh_all_texture_views()
            self.set_status(f'Displaying loaded tabs using custom palette: {Path(filepath).name}')
        except ValueError as e:
            messagebox.showerror('Invalid Palette File', str(e))
        except Exception as e:
            messagebox.showerror('Error', f'Failed to load display palette:\n{str(e)}')

    def view_clear_custom_palette(self):
        """Clear display-only custom palette and restore default rendering."""
        if not self.display_palette_file:
            self.set_status('Display palette already using original rendering')
            return

        TextureData.set_display_palette_override(None)
        previous_name = Path(self.display_palette_file).name
        self.display_palette_file = ''
        self._refresh_all_texture_views()
        self.set_status(f'Cleared custom display palette: {previous_name}')
    
    def set_status(self, message: str):
        """Update status bar message"""
        self.status_bar.config(text=self._status_with_display_palette(message))
        self.root.update_idletasks()
    
    def update_tab_title(self, tab_id: str):
        """Update tab title with modified indicator"""
        if tab_id in self.wad_files:
            wad = self.wad_files[tab_id]
            name = wad.get_name()
            if wad.modified:
                name = "* " + name
                self.add_recent_file(wad.filepath)
            
            # Find tab index
            for i in range(self.notebook.index('end')):
                if str(self.notebook.tabs()[i]) == tab_id:
                    self.notebook.tab(i, text=name)
                    break
    
    def add_tab(self, widget, title: str):
        """Add a tab with a close button"""
        self.notebook.add(widget, text=title)
        return str(widget)
    
    def file_new(self):
        """Create a new empty WAD file"""
        # Ask for format
        dialog = Toplevel(self.root)
        dialog.title("New WAD File")
        dialog.geometry("300x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        Label(dialog, text="Select WAD format:", font=('Arial', 12)).pack(pady=10)
        
        format_var = IntVar(value=2)
        Radiobutton(dialog, text="WAD2 (Quake)", variable=format_var, value=2).pack(anchor=W, padx=20)
        Radiobutton(dialog, text="WAD3 (Half-Life)", variable=format_var, value=3).pack(anchor=W, padx=20)
        
        def create_new():
            wad_type = format_var.get()
            dialog.destroy()
            
            # Ask where to save
            filepath = filedialog.asksaveasfilename(
                title="Save New WAD File",
                defaultextension=".wad",
                filetypes=[("WAD Files", "*.wad"), ("All Files", "*.*")],
                initialdir=self.get_dialog_initial_dir(),
            )
            
            if filepath:
                self.update_last_folder(filepath)
                try:
                    # Create empty WAD file
                    wad = WADFile(wad_type=wad_type)
                    wad.filepath = filepath
                    wad.save()
                    
                    # Create tab for this WAD
                    viewer = WADViewerTab(self.notebook, wad, self.on_texture_double_click, self)
                    tab_id = self.add_tab(viewer, wad.get_name())
                    
                    # Store reference
                    self.wad_files[tab_id] = wad
                    
                    # Select the new tab
                    self.notebook.select(viewer)

                    self.add_recent_file(filepath)
                    
                    self.set_status(f"Created new WAD file: {filepath}")
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create WAD file:\n{str(e)}")
                    self.set_status("Error creating file")
        
        Button(dialog, text="Create", command=create_new).pack(side=LEFT, padx=10, pady=10)
        Button(dialog, text="Cancel", command=dialog.destroy).pack(side=RIGHT, padx=10, pady=10)

    def _create_unsaved_wad_from_bsp(self, bsp_filepath: str) -> WADFile:
        """Build an unsaved WAD object containing textures extracted from a BSP file."""
        textures = fcwadtool.extract_textures_from_bsp(bsp_filepath)
        if not textures:
            raise ValueError("No embedded textures were found in this BSP file")

        wad = WADFile(wad_type=2)
        wad.display_name = f"{Path(bsp_filepath).stem}.wad"

        for name, width, height, data in textures:
            texture = TextureData(name, width, height, data, fcwadtool.QUAKE_PALETTE)
            wad.add_texture(texture)

        # This WAD only exists in memory until the user explicitly saves it.
        wad.modified = True
        return wad
    
    def file_open(self):
        """Open WAD/BSP file(s)."""
        filepaths = filedialog.askopenfilenames(
            title="Open WAD or BSP File",
            filetypes=[
                ("WAD and BSP Files", "*.wad *.bsp"),
                ("WAD Files", "*.wad"),
                ("BSP Files", "*.bsp"),
                ("All Files", "*.*"),
            ],
            multiple=True,
            initialdir=self.get_dialog_initial_dir(),
        )

        if filepaths:
            self.update_last_folder(filepaths[0])
        
        for filepath in filepaths:
            if filepath:
                try:
                    extension = Path(filepath).suffix.lower()

                    if extension == '.bsp':
                        self.set_status(f"Loading BSP {filepath}...")
                        wad = self._create_unsaved_wad_from_bsp(filepath)
                    else:
                        self.set_status(f"Loading {filepath}...")
                        wad = WADFile(filepath)
                    
                    # Create tab for this WAD
                    viewer = WADViewerTab(self.notebook, wad, self.on_texture_double_click, self)
                    tab_id = self.add_tab(viewer, wad.get_name())
                    
                    # Store reference
                    self.wad_files[tab_id] = wad
                    
                    # Select the new tab
                    self.notebook.select(viewer)

                    if extension == '.bsp':
                        self.update_tab_title(tab_id)
                        self.set_status(
                            f"Loaded {Path(filepath).name} as unsaved WAD with {len(wad.textures)} texture(s)"
                        )
                    else:
                        self.set_status(f"Loaded {filepath} with {len(wad.textures)} texture(s)")
                
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to open {filepath}:\n{str(e)}")
                    self.set_status("Error loading file")
    
    def file_save(self):
        """Save current WAD file"""
        current_tab = self.notebook.select()
        if not current_tab:
            return
        
        tab_id = str(current_tab)
        if tab_id not in self.wad_files:
            return
        
        wad = self.wad_files[tab_id]
        
        if not wad.filepath:
            self.file_save_as()
            return
        
        try:
            self.set_status(f"Saving {wad.filepath}...")
            wad.save()
            self.update_tab_title(tab_id)
            self.add_recent_file(wad.filepath)
            self.set_status(f"Saved {wad.filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save:\n{str(e)}")
            self.set_status("Error saving file")
    
    def file_save_as(self):
        """Save current WAD file with new name"""
        current_tab = self.notebook.select()
        if not current_tab:
            return
        
        tab_id = str(current_tab)
        if tab_id not in self.wad_files:
            return
        
        wad = self.wad_files[tab_id]
        
        filepath = filedialog.asksaveasfilename(
            title="Save WAD File As",
            defaultextension=".wad",
            filetypes=[("WAD Files", "*.wad"), ("All Files", "*.*")],
            initialdir=self.get_dialog_initial_dir(),
        )
        
        if filepath:
            self.update_last_folder(filepath)
            try:
                self.set_status(f"Saving {filepath}...")
                wad.save(filepath)
                self.update_tab_title(tab_id)
                self.add_recent_file(filepath)
                self.set_status(f"Saved {filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save:\n{str(e)}")
                self.set_status("Error saving file")
    
    def file_import(self):
        """Import textures from another WAD file"""
        current_tab = self.notebook.select()
        if not current_tab:
            messagebox.showinfo("Info", "Please open a WAD file first")
            return
        
        tab_id = str(current_tab)
        if tab_id not in self.wad_files:
            return
        
        filepath = filedialog.askopenfilename(
            title="Import from WAD File",
            filetypes=[("WAD Files", "*.wad"), ("All Files", "*.*")],
            initialdir=self.get_dialog_initial_dir(),
        )
        
        if filepath:
            self.update_last_folder(filepath)
            try:
                # Load source WAD in a separate window
                source_wad = WADFile(filepath)
                
                # Create import dialog
                self.show_import_dialog(source_wad)
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load import file:\n{str(e)}")

    def create_progress_dialog(self, title="Importing", message="Importing... Please wait", show_progress=False):
        """Create a modal progress dialog with optional progress bar"""
        dialog = Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Make it non-resizable
        dialog.resizable(False, False)
        
        # Create content
        frame = Frame(dialog, padx=30, pady=20)
        frame.pack()
        
        label = Label(frame, text=message, font=('Arial', 11))
        label.pack(pady=10)
        
        progress_bar = None
        progress_label = None
        
        if show_progress:
            # Progress bar (3 pixels tall, full width)
            progress_frame = Frame(frame, width=400, height=3)
            progress_frame.pack(fill=X, pady=(10, 5))
            progress_frame.pack_propagate(False)
            
            canvas = Canvas(progress_frame, height=3, bg='#d0d0d0', highlightthickness=0)
            canvas.pack(fill=BOTH, expand=True)
            
            # Create progress rectangle (initially 0 width)
            progress_rect = canvas.create_rectangle(0, 0, 0, 3, fill='#0078d4', outline='')
            progress_bar = (canvas, progress_rect)
            
            # Progress label
            progress_label = Label(frame, text="0 / 0 (0%)", font=('Arial', 9))
            progress_label.pack(pady=(5, 0))
        
        # Center on screen
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (dialog.winfo_screenheight() // 2) - (height // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")
        
        # Force render
        dialog.update_idletasks()
        
        return dialog, label, progress_bar, progress_label
    
    def show_import_dialog(self, source_wad: WADFile):
        """Show dialog for selecting textures to import"""
        dialog = Toplevel(self.root)
        dialog.title(f"Import from {source_wad.get_name()}")
        dialog.geometry("800x600")
        
        Label(dialog, text="Select textures to import:", font=('Arial', 12, 'bold')).pack(pady=10)
        
        # Create listbox with checkboxes
        frame = Frame(dialog)
        frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = Scrollbar(frame)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        listbox = Listbox(frame, selectmode=MULTIPLE, yscrollcommand=scrollbar.set, font=('Arial', 10))
        listbox.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
        
        for texture in source_wad.textures:
            listbox.insert(END, f"{texture.name} ({texture.width}x{texture.height})")
        
        # Buttons
        button_frame = Frame(dialog)
        button_frame.pack(pady=10)
        
        def import_selected():
            selected_indices = listbox.curselection()
            if not selected_indices:
                messagebox.showinfo("Info", "No textures selected")
                return
            
            current_tab = self.notebook.select()
            tab_id = str(current_tab)
            if tab_id not in self.wad_files:
                return
            
            # Show progress dialog
            progress_dialog, status_label, progress_bar, progress_label = self.create_progress_dialog(
                "Importing Textures",
                f"Importing {len(selected_indices)} texture(s)...\nPlease wait"
            )
            
            try:
                target_wad = self.wad_files[tab_id]
                
                for idx in selected_indices:
                    texture = source_wad.textures[idx]
                    # Create a copy of the texture
                    new_texture = TextureData(texture.name, texture.width, texture.height, 
                                             texture.data, texture.palette)
                    target_wad.add_texture(new_texture)
                
                # Refresh the view
                widget = self.notebook.nametowidget(current_tab)
                if isinstance(widget, WADViewerTab):
                    widget.refresh()
                
                self.update_tab_title(tab_id)
                self.set_status(f"Imported {len(selected_indices)} texture(s)")
            finally:
                # Always close progress dialog
                progress_dialog.destroy()
            
            dialog.destroy()
        
        Button(button_frame, text="Import Selected", command=import_selected).pack(side=LEFT, padx=5)
        Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=LEFT, padx=5)
    
    def file_import_images(self):
        """Import images directly as textures"""
        current_tab = self.notebook.select()
        if not current_tab:
            messagebox.showinfo("Info", "Please open a WAD file first")
            return
        
        tab_id = str(current_tab)
        if tab_id not in self.wad_files:
            messagebox.showinfo("Info", "Please select a WAD file tab")
            return

        palette_mode, custom_palette, include_fullbrights = self.get_import_palette_settings()
        dithering_mode = self.get_import_dithering_mode()
        
        # Open file dialog for multiple image selection
        filepaths = filedialog.askopenfilenames(
            title="Import Image(s)",
            filetypes=[
                ("Image Files", "*.png *.jpg *.jpeg *.bmp *.tga *.tif *.tiff"),
                ("PNG Files", "*.png"),
                ("JPEG Files", "*.jpg *.jpeg"),
                ("BMP Files", "*.bmp"),
                ("TGA Files", "*.tga"),
                ("TIFF Files", "*.tif *.tiff"),
                ("All Files", "*.*")
            ],
            initialdir=self.get_dialog_initial_dir(),
        )
        
        if not filepaths:
            return

        self.update_last_folder(filepaths[0])
        
        # Create progress tab
        progress_tab = ImportProgressTab(self.notebook, self, tab_id)
        self.notebook.add(progress_tab, text="Import Progress")
        self.notebook.select(progress_tab)
        progress_tab.log(
            f"Palette: {self._palette_mode_runtime_label(palette_mode, include_fullbrights)}"
        )
        if palette_mode == fcwadtool.PALETTE_MODE_CUSTOM:
            palette_file = self.get_custom_palette_file().strip()
            if palette_file:
                progress_tab.log(f"Custom palette source: {palette_file}")
        progress_tab.log(f"Dithering: {self._dithering_mode_label(dithering_mode)}")
        progress_tab.log("")
        
        # Start import in background thread
        def import_worker():
            """Worker thread for importing images"""
            wad = self.wad_files[tab_id]
            total_bytes = sum(os.path.getsize(fp) for fp in filepaths)
            bytes_processed = 0
            imported_count = 0
            failed_count = 0
            import_start = time.perf_counter()

            timing_keys = (
                'open_seconds',
                'decode_seconds',
                'alpha_seconds',
                'dither_seconds',
                'palette_seconds',
                'total_seconds',
            )
            timing_totals = {key: 0.0 for key in timing_keys}
            timing_samples = 0
            slowest_file = None
            slowest_total = 0.0
            transparent_name_warnings: List[str] = []

            def fmt_seconds(seconds: float) -> str:
                if seconds >= 1.0:
                    return f"{seconds:.2f}s"
                return f"{seconds * 1000.0:.1f}ms"
            
            for i, filepath in enumerate(filepaths, 1):
                # Check if cancelled
                if progress_tab.cancelled:
                    self.root.after(0, progress_tab.log, "\\nImport cancelled")
                    self.root.after(0, progress_tab.complete, imported_count, failed_count)
                    return
                
                file_size = 0
                try:
                    file_size = os.path.getsize(filepath)
                    filename = Path(filepath).name
                    
                    # Update progress (must use after() to be thread-safe)
                    self.root.after(0, progress_tab.update_progress, 
                                  bytes_processed, total_bytes, filename, i, len(filepaths))
                    self.root.after(0, progress_tab.log, f"Processing: {filename}")
                    
                    # Process image
                    telemetry = {}
                    result = fcwadtool.process_image(
                        filepath,
                        dithering_mode,
                        0,
                        0,
                        (0, 0, 0),
                        telemetry=telemetry,
                        palette_mode=palette_mode,
                        custom_palette=custom_palette,
                        include_fullbrights=include_fullbrights,
                    )

                    if telemetry:
                        for key in timing_keys:
                            timing_totals[key] += float(telemetry.get(key, 0.0) or 0.0)
                        timing_samples += 1

                        total_seconds = float(telemetry.get('total_seconds', 0.0) or 0.0)
                        if total_seconds > slowest_total:
                            slowest_total = total_seconds
                            slowest_file = filename

                        self.root.after(
                            0,
                            progress_tab.log,
                            (
                                f"  Timing: open={fmt_seconds(float(telemetry.get('open_seconds', 0.0) or 0.0))}, "
                                f"decode={fmt_seconds(float(telemetry.get('decode_seconds', 0.0) or 0.0))}, "
                                f"alpha/rgb={fmt_seconds(float(telemetry.get('alpha_seconds', 0.0) or 0.0))}, "
                                f"dither={fmt_seconds(float(telemetry.get('dither_seconds', 0.0) or 0.0))}, "
                                f"palette={fmt_seconds(float(telemetry.get('palette_seconds', 0.0) or 0.0))}, "
                                f"total={fmt_seconds(total_seconds)}"
                            )
                        )
                    
                    if result:
                        name, width, height, data = result
                        
                        # Create TextureData object
                        texture = TextureData(name, width, height, data, fcwadtool.QUAKE_PALETTE)
                        
                        # Add to WAD (handles duplicate naming automatically)
                        wad.add_texture(texture)
                        imported_count += 1

                        if telemetry.get('has_transparency'):
                            transparent_pixels = int(telemetry.get('transparent_pixel_count', 0) or 0)
                            self.root.after(
                                0,
                                progress_tab.log,
                                (
                                    f"  Info: Mapped {transparent_pixels} transparent pixel(s) "
                                    f"to palette index {fcwadtool.TRANSPARENT_PALETTE_INDEX}."
                                ),
                            )

                            if not self._is_transparent_texture_name(texture.name):
                                transparent_name_warnings.append(texture.name)
                        
                        self.root.after(0, progress_tab.log, 
                                      f"  ✓ Success: {name} ({width}x{height})")
                    else:
                        failed_count += 1
                        self.root.after(0, progress_tab.log, 
                                      f"  ✗ Failed: Could not process image")
                    
                    # Update bytes processed
                    bytes_processed += file_size
                    
                except Exception as e:
                    failed_count += 1
                    self.root.after(0, progress_tab.log, 
                                  f"  ✗ Error: {str(e)}")
                    # Still count the bytes even if it failed
                    try:
                        bytes_processed += file_size
                    except:
                        pass

            total_wall_time = time.perf_counter() - import_start
            if timing_samples > 0:
                avg_timings = {key: timing_totals[key] / timing_samples for key in timing_keys}
                total_stage_seconds = timing_totals['total_seconds'] if timing_totals['total_seconds'] > 0 else 1.0

                self.root.after(0, progress_tab.log, "")
                self.root.after(0, progress_tab.log, "Import timing summary:")
                self.root.after(
                    0,
                    progress_tab.log,
                    (
                        f"  Avg/file: open={fmt_seconds(avg_timings['open_seconds'])}, "
                        f"decode={fmt_seconds(avg_timings['decode_seconds'])}, "
                        f"alpha/rgb={fmt_seconds(avg_timings['alpha_seconds'])}, "
                        f"dither={fmt_seconds(avg_timings['dither_seconds'])}, "
                        f"palette={fmt_seconds(avg_timings['palette_seconds'])}, "
                        f"total={fmt_seconds(avg_timings['total_seconds'])}"
                    )
                )
                self.root.after(
                    0,
                    progress_tab.log,
                    (
                        "  Stage share: "
                        f"open={timing_totals['open_seconds'] / total_stage_seconds * 100.0:.1f}%, "
                        f"decode={timing_totals['decode_seconds'] / total_stage_seconds * 100.0:.1f}%, "
                        f"alpha/rgb={timing_totals['alpha_seconds'] / total_stage_seconds * 100.0:.1f}%, "
                        f"dither={timing_totals['dither_seconds'] / total_stage_seconds * 100.0:.1f}%, "
                        f"palette={timing_totals['palette_seconds'] / total_stage_seconds * 100.0:.1f}%"
                    )
                )
                self.root.after(
                    0,
                    progress_tab.log,
                    f"  Total import wall time: {fmt_seconds(total_wall_time)} for {timing_samples} file(s)"
                )
                if slowest_file:
                    self.root.after(
                        0,
                        progress_tab.log,
                        f"  Slowest file: {slowest_file} ({fmt_seconds(slowest_total)})"
                    )
            
            # Final update
            self.root.after(0, progress_tab.update_progress, 
                          total_bytes, total_bytes, None, len(filepaths), len(filepaths))
            self.root.after(0, progress_tab.complete, imported_count, failed_count)
            
            # Refresh the WAD view
            def refresh_wad():
                widget = self.notebook.nametowidget(tab_id)
                if isinstance(widget, WADViewerTab):
                    widget.refresh()
                self.update_tab_title(tab_id)
                
                if imported_count > 0:
                    if imported_count == 1:
                        self.set_status(f"Imported 1 image")
                    else:
                        self.set_status(f"Imported {imported_count} images")
            
            self.root.after(0, refresh_wad)

            if transparent_name_warnings:
                warning_names = sorted(set(transparent_name_warnings), key=str.lower)
                self.root.after(0, self._show_transparency_name_warning, warning_names)
        
        # Start the worker thread
        thread = threading.Thread(target=import_worker, daemon=True)
        thread.start()
    
    def file_export(self):
        """Export current WAD file in specified format"""
        current_tab = self.notebook.select()
        if not current_tab:
            return
        
        tab_id = str(current_tab)
        if tab_id not in self.wad_files:
            return
        
        wad = self.wad_files[tab_id]
        
        # Ask for export format
        dialog = Toplevel(self.root)
        dialog.title("Export WAD File")
        dialog.geometry("300x150")
        
        Label(dialog, text="Select export format:", font=('Arial', 12)).pack(pady=10)
        
        format_var = IntVar(value=2)
        Radiobutton(dialog, text="WAD2 (Quake)", variable=format_var, value=2).pack(anchor=W, padx=20)
        Radiobutton(dialog, text="WAD3 (Half-Life)", variable=format_var, value=3).pack(anchor=W, padx=20)
        
        def do_export():
            wad_type = format_var.get()
            dialog.destroy()
            
            filepath = filedialog.asksaveasfilename(
                title="Export WAD File",
                defaultextension=".wad",
                filetypes=[("WAD Files", "*.wad"), ("All Files", "*.*")],
                initialdir=self.get_dialog_initial_dir(),
            )
            
            if filepath:
                self.update_last_folder(filepath)
                try:
                    self.set_status(f"Exporting to {filepath}...")
                    old_type = wad.wad_type
                    wad.wad_type = wad_type
                    wad.save(filepath)
                    wad.wad_type = old_type  # Restore original type
                    self.set_status(f"Exported to {filepath}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to export:\n{str(e)}")
                    self.set_status("Error exporting file")
        
        Button(dialog, text="Export", command=do_export).pack(side=LEFT, padx=10, pady=10)
        Button(dialog, text="Cancel", command=dialog.destroy).pack(side=RIGHT, padx=10, pady=10)

    def file_export_texture_list(self):
        """Export the current WAD's texture names in their current order."""
        current_tab = self.notebook.select()
        if not current_tab:
            return

        tab_id = str(current_tab)
        if tab_id not in self.wad_files:
            messagebox.showinfo(
                "Info",
                "Export Texture List only works in WAD viewer tabs",
            )
            return

        wad = self.wad_files[tab_id]
        default_name = f"{Path(wad.get_name()).stem}_textures.txt"
        filepath = filedialog.asksaveasfilename(
            title="Export Texture List",
            initialfile=default_name,
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            initialdir=self.get_dialog_initial_dir(),
        )
        if not filepath:
            return

        self.update_last_folder(filepath)
        try:
            with open(filepath, "w", encoding="utf-8", newline="\n") as list_file:
                list_file.write("\n".join(texture.name for texture in wad.textures))
                if wad.textures:
                    list_file.write("\n")
            self.set_status(f"Exported texture list: {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export texture list:\n{str(e)}")
            self.set_status("Error exporting texture list")

    def file_add_wad_to_blacklist(self):
        """Write the current WAD's texture names to the blacklist directory."""
        current_tab = self.notebook.select()
        if not current_tab:
            return

        widget = self.notebook.nametowidget(current_tab)
        if not isinstance(widget, WADViewerTab):
            messagebox.showinfo(
                "Info",
                "Add Wad To Blacklist only works in WAD viewer tabs",
            )
            return

        tab_id = str(current_tab)
        if tab_id not in self.wad_files:
            return

        wad = self.wad_files[tab_id]
        output_path = BLACKLIST_DIRECTORY / Path(wad.get_name()).with_suffix('.txt').name
        BLACKLIST_DIRECTORY.mkdir(parents=True, exist_ok=True)

        if output_path.exists() and not messagebox.askyesno(
            "Overwrite Blacklist File",
            f"{output_path.name} already exists. Overwrite it?",
        ):
            return

        try:
            texture_names = [texture.name for texture in wad.textures]
            with output_path.open('w', encoding='utf-8', newline='\n') as list_file:
                list_file.write('\n'.join(texture_names))
                if texture_names:
                    list_file.write('\n')
            self.update_last_folder(str(output_path))
            self.set_status(f"Added WAD textures to blacklist: {output_path}")
        except Exception as e:
            messagebox.showerror(
                "Error",
                f"Failed to add WAD to blacklist:\n{str(e)}",
            )
            self.set_status("Error adding WAD to blacklist")

    def file_export_sprite(self):
        """Export selected image or image sequence as a Quake .spr sprite file."""
        current_tab = self.notebook.select()
        if not current_tab:
            return

        widget = self.notebook.nametowidget(current_tab)
        if not isinstance(widget, WADViewerTab):
            messagebox.showinfo(
                "Info",
                "Export Sprite only works in WAD viewer tabs with a selected texture",
            )
            return

        selected_textures = widget.get_selected_textures()
        if not selected_textures:
            messagebox.showinfo("Info", "No texture selected")
            return

        # Group animated textures (+1name, +2name, ...) into sequences so a
        # multi-selection exports as one animated sprite per sequence.
        sequences = self._group_sprite_sequences(selected_textures)

        if len(sequences) == 1:
            sequence_name, frames = sequences[0]
            self._show_sprite_export_dialog(sequence_name, frames)
            return

        # Multiple sequences: export each one as its own .spr file.
        confirmed = messagebox.askyesno(
            "Export Sprite Sequences",
            (
                f"Export {len(sequences)} sprite sequence(s) as separate .spr files?\n\n"
                "Each sequence will be saved next to a chosen base file."
            ),
        )
        if not confirmed:
            return

        base_filepath = filedialog.asksaveasfilename(
            title="Export Sprite Sequences",
            defaultextension=".spr",
            filetypes=[("Quake Sprite Files", "*.spr"), ("All Files", "*.*")],
            initialdir=self.get_dialog_initial_dir(),
        )
        if not base_filepath:
            return

        self.update_last_folder(base_filepath)
        base_path = Path(base_filepath)
        exported = 0
        failed_sequences = []

        for sequence_name, frames in sequences:
            if len(sequences) == 1:
                output_path = base_path
            else:
                output_path = base_path.with_name(
                    f"{base_path.stem}_{self._sanitize_sprite_filename(sequence_name)}{base_path.suffix}"
                )

            try:
                fcwadtool.create_sprite(
                    [(name, width, height, data) for name, width, height, data, _palette in frames],
                    str(output_path),
                )
                exported += 1
            except Exception as e:
                failed_sequences.append(f"{sequence_name}: {str(e)}")

        if exported > 0:
            self.set_status(f"Exported {exported} sprite file(s)")

        if failed_sequences:
            messagebox.showerror(
                "Sprite Export Failed",
                "Some sequences could not be exported:\n" + "\n".join(failed_sequences),
            )

    def _group_sprite_sequences(self, textures: List[TextureData]):
        """Group selected textures into (sequence_name, frames) lists.

        Animated textures named like ``+1button01`` / ``+2button01`` belong to
        one sequence and are ordered by their frame number. Regular textures
        each form their own single-frame sequence.
        """
        animated: Dict[str, List[Tuple[int, TextureData]]] = {}
        regular: List[Tuple[str, TextureData]] = []

        for texture in textures:
            match = re.match(r'^\+(\d+)(.*)$', texture.name)
            if match:
                frame_number = int(match.group(1))
                base_name = match.group(2) or texture.name
                animated.setdefault(base_name.casefold(), []).append((frame_number, texture))
            else:
                regular.append((texture.name, texture))

        sequences = []

        for base_key, entries in animated.items():
            entries.sort(key=lambda entry: (entry[0], entry[1].name.casefold()))
            display_name = entries[0][1].name
            frames = [(texture.name, texture.width, texture.height, texture.data, texture.palette)
                      for _frame_number, texture in entries]
            sequences.append((display_name, frames))

        for name, texture in regular:
            sequences.append((
                name,
                [(texture.name, texture.width, texture.height, texture.data, texture.palette)],
            ))

        return sequences

    @staticmethod
    def _sanitize_sprite_filename(name: str) -> str:
        """Return a filesystem-safe component derived from a texture name."""
        sanitized = re.sub(r'[^A-Za-z0-9_-]+', '_', name).strip('_')
        return sanitized or 'sprite'

    def _show_sprite_export_dialog(self, sequence_name: str, frames):
        """Show the sprite export dialog for a single sequence."""
        frame_count = len(frames)
        if frame_count == 1:
            title = f"Export Sprite: {sequence_name}"
            summary = f"Export 1 frame ({frames[0][1]}x{frames[0][2]}) as a Quake .spr sprite."
        else:
            title = f"Export Sprite Sequence: {sequence_name}"
            summary = (
                f"Export {frame_count} frames as an animated Quake .spr sprite.\n"
                f"Frame size: {frames[0][1]}x{frames[0][2]}"
            )

        dialog = Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("420x260")
        dialog.transient(self.root)
        dialog.grab_set()

        Label(dialog, text=summary, font=('Arial', 10), justify=LEFT, wraplength=380).pack(
            anchor=W, padx=16, pady=(14, 8)
        )

        Label(dialog, text="Sprite orientation:", font=('Arial', 10, 'bold')).pack(anchor=W, padx=16)
        sprite_type_var = IntVar(value=fcwadtool.SPRITE_TYPE_VP_PARALLEL)
        for sprite_type, label in (
            (fcwadtool.SPRITE_TYPE_VP_PARALLEL, 'VP Parallel (always faces the viewer)'),
            (fcwadtool.SPRITE_TYPE_VP_PARALLEL_UPRIGHT, 'VP Parallel Upright (stands upright, faces viewer)'),
            (fcwadtool.SPRITE_TYPE_FACING_UPRIGHT, 'Facing Upright (always upright)'),
            (fcwadtool.SPRITE_TYPE_ORIENTED, 'Oriented (uses entity angles)'),
            (fcwadtool.SPRITE_TYPE_VP_PARALLEL_ORIENTED, 'VP Parallel Oriented'),
        ):
            Radiobutton(
                dialog,
                text=label,
                variable=sprite_type_var,
                value=sprite_type,
                anchor=W,
                justify=LEFT,
            ).pack(anchor=W, padx=28)

        interval_frame = Frame(dialog)
        interval_frame.pack(fill=X, padx=16, pady=(10, 0))
        Label(interval_frame, text="Frame interval (seconds):").pack(side=LEFT, padx=(0, 8))
        interval_var = StringVar(value='0.1')
        interval_entry = Entry(interval_frame, textvariable=interval_var, width=8)
        interval_entry.pack(side=LEFT)

        def do_export():
            try:
                frame_interval = float(interval_var.get().strip())
            except ValueError:
                messagebox.showerror("Error", "Frame interval must be a number (e.g. 0.1)")
                return
            if frame_interval <= 0:
                messagebox.showerror("Error", "Frame interval must be greater than 0")
                return

            default_name = self._sanitize_sprite_filename(sequence_name)
            filepath = filedialog.asksaveasfilename(
                title="Export Sprite File",
                defaultextension=".spr",
                initialfile=f"{default_name}.spr",
                filetypes=[("Quake Sprite Files", "*.spr"), ("All Files", "*.*")],
                initialdir=self.get_dialog_initial_dir(),
            )
            if not filepath:
                return

            self.update_last_folder(filepath)

            try:
                self.set_status(f"Exporting sprite to {filepath}...")
                fcwadtool.create_sprite(
                    [(name, width, height, data) for name, width, height, data, _palette in frames],
                    filepath,
                    sprite_type=sprite_type_var.get(),
                    frame_interval=frame_interval,
                )
                self.set_status(f"Exported sprite: {filepath}")
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export sprite:\n{str(e)}")
                self.set_status("Error exporting sprite")

        button_frame = Frame(dialog)
        button_frame.pack(side=BOTTOM, pady=10)
        Button(button_frame, text="Export", command=do_export, width=10).pack(side=LEFT, padx=5)
        Button(button_frame, text="Cancel", command=dialog.destroy, width=10).pack(side=LEFT, padx=5)

        dialog.bind('<Return>', lambda _event: do_export())
        dialog.bind('<Escape>', lambda _event: dialog.destroy())
    
    def file_close(self):
        """Close current tab"""
        current_tab = self.notebook.select()
        if not current_tab:
            return
        
        tab_id = str(current_tab)
        
        # Check if modified
        if tab_id in self.wad_files:
            wad = self.wad_files[tab_id]
            if wad.modified:
                result = messagebox.askyesnocancel(
                    "Save Changes?",
                    f"Do you want to save changes to {wad.get_name()}?"
                )
                
                if result is None:  # Cancel
                    return
                elif result:  # Yes
                    self.file_save()
            
            del self.wad_files[tab_id]

        if tab_id == self.palette_editor_tab_id:
            self.palette_editor_tab_id = None
        
        # Remove and destroy tab widget to release memory.
        self._destroy_notebook_tab(current_tab)
        self._update_view_menu_state()
        self.set_status("Tab closed")

    def _update_custom_palette(self, palette_values: List[int]):
        """Store latest custom palette values for reopening the editor tab."""
        self.custom_palette = self._normalize_palette_values(palette_values)
        self.options['custom_palette_data'] = self.custom_palette[:]
        self.save_options()

    def edit_quake_palette(self):
        """Open or focus the Quake palette editor tab."""
        if self.palette_editor_tab_id and self.palette_editor_tab_id in self.notebook.tabs():
            self.notebook.select(self.palette_editor_tab_id)
            self.set_status('Editing Quake palette')
            return

        self.palette_editor_tab_id = None
        palette_tab = PaletteEditorTab(
            self.notebook,
            self,
            palette_values=self.custom_palette,
            on_palette_changed=self._update_custom_palette,
        )
        tab_id = self.add_tab(palette_tab, 'Quake Palette')
        self.palette_editor_tab_id = tab_id
        self.notebook.select(palette_tab)
        self.set_status('Opened Quake palette editor')
    
    def edit_copy(self):
        """Copy selected texture(s) to clipboard"""
        current_tab = self.notebook.select()
        if not current_tab:
            return
        
        widget = self.notebook.nametowidget(current_tab)
        if isinstance(widget, WADViewerTab):
            textures = widget.get_selected_textures()
            if textures:
                # Copy texture payloads instead of storing live TextureData references.
                self.clipboard_textures = [
                    (
                        texture.name,
                        texture.width,
                        texture.height,
                        bytes(texture.data),
                        list(texture.palette) if texture.palette else list(fcwadtool.QUAKE_PALETTE),
                    )
                    for texture in textures
                ]
                if len(textures) == 1:
                    self.set_status(f"Copied texture: {textures[0].name}")
                else:
                    self.set_status(f"Copied {len(textures)} textures")
            else:
                messagebox.showinfo("Info", "No texture selected")
    
    def edit_paste(self):
        """Paste texture(s) from clipboard to current WAD"""
        if not self.clipboard_textures:
            messagebox.showinfo("Info", "Clipboard is empty")
            return
        
        current_tab = self.notebook.select()
        if not current_tab:
            return
        
        tab_id = str(current_tab)
        if tab_id not in self.wad_files:
            return
        
        wad = self.wad_files[tab_id]
        
        # Create copies of all textures in clipboard
        pasted_count = 0
        for name, width, height, data, palette in self.clipboard_textures:
            new_texture = TextureData(
                name,
                width,
                height,
                data,
                palette,
            )
            
            wad.add_texture(new_texture)
            pasted_count += 1
        
        # Refresh view
        widget = self.notebook.nametowidget(current_tab)
        if isinstance(widget, WADViewerTab):
            widget.refresh()
        
        self.update_tab_title(tab_id)
        
        if pasted_count == 1:
            self.set_status(f"Pasted texture: {self.clipboard_textures[0][0]}")
        else:
            self.set_status(f"Pasted {pasted_count} textures")
    
    def edit_delete(self):
        """Delete selected texture(s)"""
        current_tab = self.notebook.select()
        if not current_tab:
            return
        
        widget = self.notebook.nametowidget(current_tab)
        if isinstance(widget, WADViewerTab):
            widget.delete_selected_textures()
        else:
            messagebox.showinfo("Info", "Delete only works in WAD viewer tabs")
    
    def edit_resize(self):
        """Resize selected texture(s)"""
        current_tab = self.notebook.select()
        if not current_tab:
            return
        
        widget = self.notebook.nametowidget(current_tab)
        if isinstance(widget, WADViewerTab):
            selected_textures = widget.get_selected_textures()
            if not selected_textures:
                messagebox.showinfo("Info", "No texture selected")
                return

            primary_texture = selected_textures[0]
            selected_count = len(selected_textures)

            palette_mode, custom_palette, include_fullbrights = self.get_import_palette_settings()
            dithering_mode = self.get_import_dithering_mode()
            
            # Create resize dialog
            dialog = Toplevel(self.root)
            if selected_count == 1:
                dialog.title(f"Resize {primary_texture.name}")
            else:
                dialog.title(f"Resize {selected_count} Textures")
            dialog.geometry("300x150")
            
            Label(dialog, text="New Width:").grid(row=0, column=0, padx=10, pady=10)
            width_var = IntVar(value=primary_texture.width)
            Entry(dialog, textvariable=width_var).grid(row=0, column=1, padx=10, pady=10)
            
            Label(dialog, text="New Height:").grid(row=1, column=0, padx=10, pady=10)
            height_var = IntVar(value=primary_texture.height)
            Entry(dialog, textvariable=height_var).grid(row=1, column=1, padx=10, pady=10)
            
            def do_resize():
                new_width = width_var.get()
                new_height = height_var.get()
                
                if new_width <= 0 or new_height <= 0:
                    messagebox.showerror("Error", "Invalid dimensions")
                    return
                
                try:
                    # Step 1: resolve conversion settings once for the whole batch.
                    (
                        _,
                        process_palette,
                        process_color_count,
                        process_palette_image,
                        process_index_remap_table,
                    ) = fcwadtool.resolve_process_palette(
                        palette_mode,
                        custom_palette=custom_palette,
                        include_fullbrights=include_fullbrights,
                    )
                    dithering_index = fcwadtool.resolve_dithering_index(dithering_mode)

                    resized_count = 0
                    failed_textures = []

                    for texture in selected_textures:
                        try:
                            # Step 2: convert to RGB for a clean colour source.
                            rgb_img = texture.image.convert('RGB')

                            # Step 3: smooth resize using high-quality Lanczos resampling.
                            resized_img = rgb_img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                            # Step 4: convert to Quake palette using the user's chosen settings.
                            if dithering_index == fcwadtool.DITHERING_INDEX_ERROR_DIFFUSION:
                                quantized = resized_img.quantize(
                                    palette=process_palette_image,
                                    dither=Image.Dither.FLOYDSTEINBERG,
                                )
                                new_data = quantized.tobytes()
                                if process_index_remap_table is not None:
                                    new_data = new_data.translate(process_index_remap_table)
                            elif dithering_index == fcwadtool.DITHERING_INDEX_CLOSEST_COLOR:
                                quantized = resized_img.quantize(
                                    palette=process_palette_image,
                                    dither=Image.Dither.NONE,
                                )
                                new_data = quantized.tobytes()
                                if process_index_remap_table is not None:
                                    new_data = new_data.translate(process_index_remap_table)
                            elif dithering_index == fcwadtool.DITHERING_INDEX_RANDOM:
                                noisy_img = fcwadtool.random_dither(
                                    resized_img, process_palette, max_colors=process_color_count
                                )
                                quantized = noisy_img.quantize(
                                    palette=process_palette_image,
                                    dither=Image.Dither.NONE,
                                )
                                new_data = quantized.tobytes()
                                if process_index_remap_table is not None:
                                    new_data = new_data.translate(process_index_remap_table)
                            elif dithering_index == fcwadtool.DITHERING_INDEX_ORDERED:
                                prepped = fcwadtool.ordered_dither(
                                    resized_img, process_palette, max_colors=process_color_count
                                )
                                quantized = prepped.quantize(
                                    palette=process_palette_image,
                                    dither=Image.Dither.NONE,
                                )
                                new_data = fcwadtool._palette_bytes_from_quantized_image(
                                    quantized, process_index_remap_table
                                )
                            else:  # DITHERING_INDEX_HALFTONE or fallback
                                prepped = fcwadtool.halftone_dither(
                                    resized_img, process_palette, max_colors=process_color_count
                                )
                                quantized = prepped.quantize(
                                    palette=process_palette_image,
                                    dither=Image.Dither.NONE,
                                )
                                new_data = fcwadtool._palette_bytes_from_quantized_image(
                                    quantized, process_index_remap_table
                                )

                            # Update texture
                            texture.width = new_width
                            texture.height = new_height
                            texture.data = new_data
                            texture._generate_image()
                            resized_count += 1
                        except Exception:
                            failed_textures.append(texture.name)

                    if resized_count == 0:
                        if failed_textures:
                            messagebox.showerror(
                                "Error",
                                "Failed to resize selected textures:\n" + ", ".join(failed_textures),
                            )
                        else:
                            messagebox.showerror("Error", "Failed to resize selected textures")
                        return
                    
                    # Mark as modified
                    tab_id = str(current_tab)
                    if tab_id in self.wad_files:
                        self.wad_files[tab_id].modified = True
                        self.update_tab_title(tab_id)
                    
                    # Refresh view
                    widget.refresh()
                    
                    dialog.destroy()
                    if resized_count == 1 and selected_count == 1:
                        self.set_status(
                            (
                                f"Resized {primary_texture.name} to {new_width}x{new_height} "
                                f"({self._palette_mode_runtime_label(palette_mode, include_fullbrights)})"
                            )
                        )
                    else:
                        self.set_status(
                            (
                                f"Resized {resized_count} texture(s) to {new_width}x{new_height} "
                                f"({self._palette_mode_runtime_label(palette_mode, include_fullbrights)})"
                            )
                        )

                    if failed_textures:
                        messagebox.showwarning(
                            "Resize Completed with Errors",
                            "Some textures failed to resize:\n" + ", ".join(failed_textures),
                        )
                
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to resize:\n{str(e)}")
            
            Button(dialog, text="Resize", command=do_resize).grid(row=2, column=0, padx=10, pady=10)
            Button(dialog, text="Cancel", command=dialog.destroy).grid(row=2, column=1, padx=10, pady=10)
    
    def edit_reimport(self):
        """Reimport texture from image file"""
        current_tab = self.notebook.select()
        if not current_tab:
            return
        
        widget = self.notebook.nametowidget(current_tab)
        if isinstance(widget, WADViewerTab):
            texture = widget.get_selected_texture()
            if not texture:
                messagebox.showinfo("Info", "No texture selected")
                return

            palette_mode, custom_palette, include_fullbrights = self.get_import_palette_settings()
            dithering_mode = self.get_import_dithering_mode()
            
            filepath = filedialog.askopenfilename(
                title="Select Image File",
                filetypes=[
                    ("Image Files", "*.png *.jpg *.jpeg *.bmp *.tga *.tif *.tiff"),
                    ("All Files", "*.*")
                ],
                initialdir=self.get_dialog_initial_dir(),
            )
            
            if filepath:
                self.update_last_folder(filepath)
                try:
                    # Process the image using fcwadtool functions
                    telemetry = {}
                    result = fcwadtool.process_image(
                        filepath,
                        dithering_mode,
                        0,
                        0,
                        (0, 0, 0),
                        telemetry=telemetry,
                        palette_mode=palette_mode,
                        custom_palette=custom_palette,
                        include_fullbrights=include_fullbrights,
                    )
                    
                    if result:
                        name, width, height, data = result
                        
                        # Update texture
                        texture.width = width
                        texture.height = height
                        texture.data = data
                        texture._generate_image()
                        
                        # Mark as modified
                        tab_id = str(current_tab)
                        if tab_id in self.wad_files:
                            self.wad_files[tab_id].modified = True
                            self.update_tab_title(tab_id)
                        
                        # Refresh view
                        widget.refresh()
                        
                        self.set_status(
                            (
                                f"Reimported {texture.name} from {filepath} "
                                f"({self._palette_mode_runtime_label(palette_mode, include_fullbrights)}, "
                                f"{self._dithering_mode_label(dithering_mode)})"
                            )
                        )

                        if telemetry.get('has_transparency') and not self._is_transparent_texture_name(texture.name):
                            self._show_transparency_name_warning([texture.name])
                    else:
                        messagebox.showerror("Error", "Failed to process image")
                
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to reimport:\n{str(e)}")

    @staticmethod
    def _animated_texture_sort_key(name: str):
        """Build a sort key that keeps animated texture sequences grouped.

        Animated textures look like ``+1button01`` / ``+2button01`` where the
        digits after ``+`` are the frame number in the sequence and the rest is
        the real texture name. Sorting those by their raw name scatters the
        frames of one sequence across the WAD, so instead:

        1. Textures starting with ``+`` are detected and split into
           ``(frame number, base name)``.
        2. Everything is ordered by the base name (animated textures use the
           name after the frame digits, so they sort alphabetically alongside
           regular textures).
        3. Frames of the same base name are then grouped together in sequence
           order (``+1button01, +2button01, +3button01, +1button02, ...``).
        """
        match = re.match(r'^\+(\d+)(.*)$', name)
        if match:
            frame_number = int(match.group(1))
            base_name = match.group(2)
            return (base_name.casefold(), frame_number, name.casefold())
        return (name.casefold(), -1, name.casefold())

    def edit_sort_textures_alphabetically(self):
        """Sort textures alphabetically in the current WAD"""
        current_tab = self.notebook.select()
        if not current_tab:
            return

        widget = self.notebook.nametowidget(current_tab)
        if not isinstance(widget, WADViewerTab):
            messagebox.showinfo("Info", "Sort only works in WAD viewer tabs")
            return

        tab_id = str(current_tab)
        if tab_id not in self.wad_files:
            return

        wad = self.wad_files[tab_id]
        if len(wad.textures) < 2:
            self.set_status("Need at least two textures to sort")
            return

        original_order = [texture.name for texture in wad.textures]
        wad.textures.sort(key=lambda texture: self._animated_texture_sort_key(texture.name))
        sorted_order = [texture.name for texture in wad.textures]

        if original_order == sorted_order:
            self.set_status("Textures are already sorted alphabetically")
            return

        wad.modified = True
        self.update_tab_title(tab_id)

        # Selection indices no longer map to the same textures after sorting.
        widget.selected_indices.clear()
        widget.last_selected_index = None
        widget.refresh()

        self.set_status("Sorted textures alphabetically")

    def _load_blacklisted_texture_names(self) -> set:
        """Load case-insensitive texture names from all blacklist text files."""
        if not BLACKLIST_DIRECTORY.is_dir():
            raise FileNotFoundError(
                f'Blacklist directory does not exist: {BLACKLIST_DIRECTORY}'
            )

        texture_names = set()
        blacklist_paths = sorted(
            (
                path
                for path in BLACKLIST_DIRECTORY.iterdir()
                if path.is_file() and path.suffix.lower() == '.txt'
            ),
            key=lambda path: path.name.casefold(),
        )
        for blacklist_path in blacklist_paths:
            with blacklist_path.open('r', encoding='utf-8') as list_file:
                texture_names.update(
                    texture_name.casefold()
                    for line in list_file
                    for texture_name in [line.strip()]
                    if texture_name and not texture_name.startswith('#')
                )

        return texture_names

    def edit_remove_blacklisted_textures(self):
        """Remove blacklisted texture names from the active WAD tab."""
        current_tab = self.notebook.select()
        if not current_tab:
            return

        widget = self.notebook.nametowidget(current_tab)
        if not isinstance(widget, WADViewerTab):
            messagebox.showinfo(
                "Info",
                "Remove Blacklisted Textures only works in WAD viewer tabs",
            )
            return

        tab_id = str(current_tab)
        if tab_id not in self.wad_files:
            return

        try:
            blacklisted_texture_names = self._load_blacklisted_texture_names()
        except (FileNotFoundError, OSError, UnicodeError) as error:
            messagebox.showerror("Blacklist Not Found", str(error))
            return

        wad = self.wad_files[tab_id]
        removable_indices = [
            index
            for index, texture in enumerate(wad.textures)
            if texture.name.casefold() in blacklisted_texture_names
            and not is_utility_texture_name(texture.name)
        ]

        if not removable_indices:
            self.set_status(
                f"No blacklisted textures found (loaded "
                f"{len(blacklisted_texture_names)} names from {BLACKLIST_DIRECTORY.name}/)"
            )
            return

        confirmed = messagebox.askyesno(
            "Remove Blacklisted Textures",
            (
                f"Remove {len(removable_indices)} texture(s) matching the names in "
                f"the text files in {BLACKLIST_DIRECTORY.name}/?\n\n"
                f"Utility textures (skip, clip, "
                f"trigger, sky) will be preserved."
            ),
        )
        if not confirmed:
            return

        for index in reversed(removable_indices):
            del wad.textures[index]

        wad.modified = True
        widget.selected_indices.clear()
        widget.last_selected_index = None
        widget.refresh()
        self.update_tab_title(tab_id)
        self.set_status(
            f"Removed {len(removable_indices)} blacklisted texture(s); "
            "preserved utility textures"
        )
    
    def edit_rename(self):
        """Rename selected texture"""
        current_tab = self.notebook.select()
        if not current_tab:
            return
        
        widget = self.notebook.nametowidget(current_tab)
        if isinstance(widget, WADViewerTab):
            texture = widget.get_selected_texture()
            if not texture:
                messagebox.showinfo("Info", "No texture selected")
                return
            
            # Create rename dialog
            dialog = Toplevel(self.root)
            dialog.title("Rename Texture")
            dialog.geometry("400x200")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Center dialog
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
            y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
            dialog.geometry(f"+{x}+{y}")
            
            Label(dialog, text="Enter new name for texture:", font=('Arial', 10)).pack(pady=(10, 5))
            
            name_entry = Entry(dialog, font=('Arial', 11), width=30)
            name_entry.insert(0, texture.name)
            name_entry.pack(pady=5, padx=20)
            name_entry.select_range(0, END)
            name_entry.focus()
            
            # Info label about naming restrictions
            info_frame = Frame(dialog, bg='#ffffcc', relief=SOLID, borderwidth=1)
            info_frame.pack(fill=X, pady=10, padx=20)
            
            info_text = (
                "Note: WAD2/WAD3 texture names are limited to 15 characters.\n"
                "Names will be automatically truncated if longer."
            )
            Label(info_frame, text=info_text, bg='#ffffcc', fg='#333', 
                  font=('Arial', 8), justify=LEFT).pack(pady=5, padx=5)
            
            def do_rename():
                new_name = name_entry.get().strip()
                
                if not new_name:
                    messagebox.showerror("Error", "Texture name cannot be empty")
                    return
                
                # Truncate to 15 characters
                if len(new_name) > 15:
                    new_name = new_name[:15]
                    messagebox.showinfo("Info", f"Name truncated to 15 characters: {new_name}")
                
                # Check if name already exists (case-insensitive)
                tab_id = str(current_tab)
                if tab_id in self.wad_files:
                    wad = self.wad_files[tab_id]
                    existing_names = [t.name.lower() for t in wad.textures if t != texture]
                    
                    if new_name.lower() in existing_names:
                        messagebox.showerror("Error", f"A texture named '{new_name}' already exists")
                        return
                
                # Rename the texture
                old_name = texture.name
                texture.name = new_name
                
                # Mark as modified
                if tab_id in self.wad_files:
                    self.wad_files[tab_id].modified = True
                    self.update_tab_title(tab_id)
                
                # Refresh view
                widget.refresh()
                
                dialog.destroy()
                self.set_status(f"Renamed '{old_name}' to '{new_name}'")
            
            # Button frame
            button_frame = Frame(dialog)
            button_frame.pack(pady=10)
            
            Button(button_frame, text="Rename", command=do_rename, width=10).pack(side=LEFT, padx=5)
            Button(button_frame, text="Cancel", command=dialog.destroy, width=10).pack(side=LEFT, padx=5)
            
            # Bind Enter key to rename
            name_entry.bind('<Return>', lambda e: do_rename())
    
    def on_texture_double_click(self, index: int):
        """Handle double-click on texture to open in image viewer"""
        current_tab = self.notebook.select()
        if not current_tab:
            return
        
        tab_id = str(current_tab)
        if tab_id not in self.wad_files:
            return
        
        wad = self.wad_files[tab_id]
        
        if 0 <= index < len(wad.textures):
            texture = wad.textures[index]
            
            # Create image viewer tab
            viewer = ImageViewerTab(self.notebook, texture)
            self.add_tab(viewer, texture.name)
            self.notebook.select(viewer)
            self._update_view_menu_state()
            
            self.set_status(f"Viewing texture: {texture.name}")
    
    def on_tab_changed(self, event):
        """Handle tab change event"""
        self._update_view_menu_state()
        current_tab = self.notebook.select()
        if current_tab:
            tab_id = str(current_tab)
            if tab_id in self.wad_files:
                wad = self.wad_files[tab_id]
                self.set_status(f"Viewing {wad.get_name()} ({len(wad.textures)} textures)")
            elif tab_id == self.palette_editor_tab_id:
                self.set_status('Editing Quake palette')
    
    def on_tab_right_click(self, event):
        """Handle right-click on tab for context menu"""
        try:
            # Get the tab index that was clicked
            clicked_tab = self.notebook.tk.call(self.notebook._w, "identify", "tab", event.x, event.y)
            if clicked_tab != '':
                # Select the tab
                self.notebook.select(clicked_tab)
                
                # Create context menu
                menu = Menu(self.root, tearoff=0)
                menu.add_command(label="Close Tab", command=self.file_close)
                menu.add_command(label="Close Other Tabs", command=lambda: self.close_other_tabs(clicked_tab))
                menu.post(event.x_root, event.y_root)
        except:
            pass
    
    def on_tab_middle_click(self, event):
        """Handle middle-click on tab to close it"""
        try:
            # Get the tab index that was clicked
            clicked_tab = self.notebook.tk.call(self.notebook._w, "identify", "tab", event.x, event.y)
            if clicked_tab != '':
                # Select and close the tab
                self.notebook.select(clicked_tab)
                self.file_close()
        except:
            pass
    
    def close_other_tabs(self, keep_tab):
        """Close all tabs except the specified one"""
        tabs = list(self.notebook.tabs())
        for tab in tabs:
            if tab != keep_tab:
                self.notebook.select(tab)
                self.file_close()
    
    def view_zoom_in(self):
        """Zoom in the current view"""
        current_tab = self.notebook.select()
        if not current_tab:
            return
        
        widget = self.notebook.nametowidget(current_tab)
        if isinstance(widget, WADViewerTab):
            widget.zoom_icons_in()
            self.set_status(f"Icon size: {widget.icon_size}px")
        elif isinstance(widget, ImageViewerTab):
            widget.zoom_in()
    
    def view_zoom_out(self):
        """Zoom out the current view"""
        current_tab = self.notebook.select()
        if not current_tab:
            return
        
        widget = self.notebook.nametowidget(current_tab)
        if isinstance(widget, WADViewerTab):
            widget.zoom_icons_out()
            self.set_status(f"Icon size: {widget.icon_size}px")
        elif isinstance(widget, ImageViewerTab):
            widget.zoom_out()
    
    def view_set_icon_size(self):
        """Show dialog to set icon size"""
        current_tab = self.notebook.select()
        if not current_tab:
            return
        
        widget = self.notebook.nametowidget(current_tab)
        if not isinstance(widget, WADViewerTab):
            messagebox.showinfo("Info", "This option only applies to WAD viewer tabs")
            return
        
        # Create custom dialog
        dialog = Toplevel(self.root)
        dialog.title("Set Icon Size")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        Label(dialog, text="Please enter the size of image icons in pixels\n(for the largest dimension):",
              font=('Arial', 10)).pack(pady=15)
        
        size_var = IntVar(value=widget.icon_size)
        entry = Entry(dialog, textvariable=size_var, font=('Arial', 12), width=10)
        entry.pack(pady=10)
        entry.focus_set()
        entry.select_range(0, END)
        
        def apply_size():
            try:
                new_size = size_var.get()
                if 32 <= new_size <= 512:
                    widget.set_icon_size(new_size)
                    self.set_status(f"Icon size set to: {new_size}px")
                    dialog.destroy()
                else:
                    messagebox.showerror("Error", "Icon size must be between 32 and 512 pixels")
            except:
                messagebox.showerror("Error", "Invalid size value")
        
        button_frame = Frame(dialog)
        button_frame.pack(pady=10)
        
        Button(button_frame, text="OK", command=apply_size, width=10).pack(side=LEFT, padx=5)
        Button(button_frame, text="Close", command=dialog.destroy, width=10).pack(side=LEFT, padx=5)
        
        # Bind Enter key to OK
        entry.bind('<Return>', lambda e: apply_size())

    def view_set_image_zoom_level(self, zoom_percent: int):
        """Set zoom level for current image tab from predefined menu values."""
        widget = self._get_current_tab_widget()
        if not isinstance(widget, ImageViewerTab):
            messagebox.showinfo("Info", "Set Image Zoom Level only applies to image tabs")
            self._update_view_menu_state()
            return

        widget.set_zoom_percent(zoom_percent)
        self.set_status(f"Image zoom set to {zoom_percent}%")

    def view_original_image(self):
        """Switch current image tab to original (non-tiled) view."""
        widget = self._get_current_tab_widget()
        if not isinstance(widget, ImageViewerTab):
            messagebox.showinfo("Info", "View Original Image only applies to image tabs")
            self._update_view_menu_state()
            return

        widget.set_tiled_view(False)
        self._update_view_menu_state()
        self.set_status("Image view mode: Original")

    def view_tiled_image(self):
        """Switch current image tab to tiled 3x3 view."""
        widget = self._get_current_tab_widget()
        if not isinstance(widget, ImageViewerTab):
            messagebox.showinfo("Info", "View Tiled Image only applies to image tabs")
            self._update_view_menu_state()
            return

        widget.set_tiled_view(True)
        self._update_view_menu_state()
        self.set_status("Image view mode: Tiled 3x3")
    
    def view_in_separate_tab(self):
        """View selected texture in separate tab (same as double-click)"""
        current_tab = self.notebook.select()
        if not current_tab:
            return
        
        widget = self.notebook.nametowidget(current_tab)
        if isinstance(widget, WADViewerTab):
            textures = widget.get_selected_textures()
            if textures:
                index = min(widget.selected_indices)  # Get first selected index
                if index is not None:
                    self.on_texture_double_click(index)
            else:
                messagebox.showinfo("Info", "No texture selected")
    
    def on_closing(self):
        """Handle application closing"""
        # Check for unsaved changes
        unsaved_wads = [wad for wad in self.wad_files.values() if wad.modified]
        
        if unsaved_wads:
            for tab_id, wad in list(self.wad_files.items()):
                if wad.modified:
                    result = messagebox.askyesnocancel(
                        "Save Changes?",
                        f"Do you want to save changes to {wad.get_name()}?"
                    )
                    
                    if result is None:  # Cancel
                        return
                    elif result:  # Yes
                        # Find and select the tab
                        for i, tab in enumerate(self.notebook.tabs()):
                            if str(tab) == tab_id:
                                self.notebook.select(i)
                                self.file_save()
                                break
        
        self.root.destroy()


def main():
    """Main entry point"""
    root = Tk()
    app = WADEditor(root)
    root.mainloop()


if __name__ == '__main__':
    main()
