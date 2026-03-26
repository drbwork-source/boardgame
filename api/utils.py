"""
Shared utilities for the API and desktop app (e.g. optional PIL detection, board drawing).
"""

from __future__ import annotations

import importlib.util
from typing import Any

PIL_AVAILABLE = False
Image = None
ImageDraw = None
ImageFont = None

if importlib.util.find_spec("PIL") is not None:
    try:
        from PIL import Image as _Image, ImageDraw as _ImageDraw, ImageFont as _ImageFont
        Image = _Image
        ImageDraw = _ImageDraw
        ImageFont = _ImageFont
        PIL_AVAILABLE = True
    except ImportError:
        pass


def draw_board_to_image(
    board: list[list[str]],
    tile_size: int,
    tile_colors: dict[str, str],
    tile_styles: dict[str, dict[str, str]] | None,
    bg_color: str = "#0A0E14",
    border_color: str = "#262a33",
    outline_overrides: dict[str, tuple[str, int]] | None = None,
    draw_glyphs: bool = True,
    font: Any = None,
):
    """
    Draw a board grid onto a new PIL Image and return it.
    tile_styles: symbol -> {fg, glyph}. outline_overrides: symbol -> (outline_color, width).
    If draw_glyphs is False or font is None, only colored cells are drawn (no glyphs).
    Requires PIL_AVAILABLE; returns None if PIL is not available.
    """
    if not PIL_AVAILABLE or Image is None or ImageDraw is None:
        return None
    if not board or not board[0]:
        return None
    w = len(board[0]) * tile_size
    h = len(board) * tile_size
    image = Image.new("RGB", (w, h), bg_color)
    draw = ImageDraw.Draw(image)
    for y, row in enumerate(board):
        for x, symbol in enumerate(row):
            color = tile_colors.get(symbol, "#F8FAFC")
            x0, y0 = x * tile_size, y * tile_size
            x1, y1 = x0 + tile_size, y0 + tile_size
            outline_color = border_color
            outline_width = 1
            if outline_overrides and symbol in outline_overrides:
                outline_color, outline_width = outline_overrides[symbol]
            draw.rectangle([x0, y0, x1, y1], fill=color, outline=outline_color, width=outline_width)
            if draw_glyphs and font and tile_styles and symbol in tile_styles:
                style = tile_styles[symbol]
                glyph = style.get("glyph", symbol)
                fg = style.get("fg", "#1f2937")
                bbox = draw.textbbox((0, 0), glyph, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                draw.text((x0 + (tile_size - tw) / 2, y0 + (tile_size - th) / 2), glyph, fill=fg, font=font)
    return image
