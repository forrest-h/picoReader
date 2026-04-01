"""Shim for CircuitPython 'displayio' module.

Provides Group, Bitmap, Palette, TileGrid, and FourWire classes that
maintain a scene graph. The ST7735R shim calls serialize() on the root
group to produce a message for the main thread renderer.
"""
from _bridge import post_message


def release_displays():
    pass


class Palette:
    def __init__(self, color_count):
        self._colors = [0] * color_count

    def __setitem__(self, index, color):
        self._colors[index] = color

    def __getitem__(self, index):
        return self._colors[index]

    def __len__(self):
        return len(self._colors)


class Bitmap:
    def __init__(self, width, height, color_count):
        self.width = width
        self.height = height
        self.color_count = color_count
        self._data = [0] * (width * height)

    def __setitem__(self, key, value):
        if isinstance(key, tuple):
            x, y = key
            self._data[y * self.width + x] = value
        else:
            self._data[key] = value

    def __getitem__(self, key):
        if isinstance(key, tuple):
            x, y = key
            return self._data[y * self.width + x]
        return self._data[key]


class TileGrid:
    def __init__(self, bitmap, pixel_shader=None, x=0, y=0,
                 tile_width=None, tile_height=None, **kwargs):
        self.bitmap = bitmap
        self.pixel_shader = pixel_shader
        self.x = x
        self.y = y
        self.tile_width = tile_width or bitmap.width
        self.tile_height = tile_height or bitmap.height
        self._tiles = [0]

    def __setitem__(self, index, value):
        if index >= len(self._tiles):
            self._tiles.extend([0] * (index + 1 - len(self._tiles)))
        self._tiles[index] = value

    def __getitem__(self, index):
        if index >= len(self._tiles):
            return 0
        return self._tiles[index]

    def serialize(self):
        bmp = self.bitmap
        pal = self.pixel_shader
        palette_colors = list(pal._colors) if pal else [0]

        tw = self.tile_width
        th = self.tile_height

        # If using tiles (sprite sheet), extract only the active tile's pixels
        if tw != bmp.width or th != bmp.height:
            tile_idx = self._tiles[0] if self._tiles else 0
            cols = bmp.width // tw
            tile_col = tile_idx % cols
            tile_row = tile_idx // cols
            tile_data = []
            for row in range(th):
                src_y = tile_row * th + row
                for col in range(tw):
                    src_x = tile_col * tw + col
                    tile_data.append(bmp._data[src_y * bmp.width + src_x])
            node = {
                "type": "tilegrid",
                "x": self.x,
                "y": self.y,
                "w": tw,
                "h": th,
                "paletteColors": palette_colors,
            }
            if any(v != 0 for v in tile_data):
                node["bitmapData"] = tile_data
            return node

        # Non-tiled: send full bitmap
        has_pixel_data = any(v != 0 for v in bmp._data)

        node = {
            "type": "tilegrid",
            "x": self.x,
            "y": self.y,
            "w": bmp.width,
            "h": bmp.height,
            "paletteColors": palette_colors,
        }

        if has_pixel_data:
            node["bitmapData"] = list(bmp._data)

        return node


class Group:
    def __init__(self, **kwargs):
        self._children = []

    def append(self, child):
        self._children.append(child)

    def __setitem__(self, index, child):
        self._children[index] = child

    def __getitem__(self, index):
        return self._children[index]

    def pop(self, index=-1):
        return self._children.pop(index)

    def __len__(self):
        return len(self._children)

    def serialize(self):
        nodes = []
        for child in self._children:
            if hasattr(child, 'serialize'):
                nodes.append(child.serialize())
        return nodes


class FourWire:
    def __init__(self, spi, command=None, chip_select=None, reset=None, **kwargs):
        pass
