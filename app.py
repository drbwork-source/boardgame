"""
Board Generator Studio — desktop application.
The app is the centre: board canvas dominates the layout with compact side panels.
"""

from __future__ import annotations

import binascii
import json
import struct
import threading
import zlib
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

from board_core import (
    Board,
    BoardOptions,
    TILE_COLORS,
    TILE_METADATA,
    TILE_NAMES,
    TILE_RULES,
    TILE_STYLES,
    TILESET_PRESETS,
    BOARD_PRESETS,
    BOARD_SIZE_MIN,
    BOARD_SIZE_MAX,
    GENERATION_MODE_LABELS,
    SPECIAL_SYMBOLS,
    check_pathability,
    compute_route_quality,
    default_weights_string,
    generate_board,
    generate_board_with_selection_or_locks,
    get_tile_metadata,
    set_tile_metadata,
    run_monte_carlo,
    board_to_string,
    parse_weights,
)

# Optional PIL for image export (shared with api.utils)
from api.utils import Image, ImageDraw, ImageFont, draw_board_to_image

# ---------------------------------------------------------------------------
# Theme and constants
# ---------------------------------------------------------------------------

THEME = {
    "bg_dark": "#0D1117",
    "bg_panel": "#161B22",
    "bg_panel_hover": "#21262D",
    "bg_canvas": "#0A0E14",
    "fg_primary": "#F0F6FC",
    "fg_secondary": "#8B949E",
    "accent": "#58A6FF",
    "accent_hover": "#79B8FF",
    "border": "#262a33",
    "highlight": "#388BFD",
    "success": "#3FB950",
    "panel_radius": 8,
    "spacing_sm": 6,
    "spacing_md": 12,
    "spacing_lg": 16,
    "font_title": 12,
    "font_body": 11,
    "font_secondary": 10,
}
MAX_UNDO_STEPS = 30
DEBOUNCE_MS = 180
# Desktop UI stores the long label text; map back to core mode ids.
_GENERATION_UI_LABEL_TO_MODE: dict[str, str] = {v: k for k, v in GENERATION_MODE_LABELS.items()}
ZOOM_DEBOUNCE_MS = 60
ZOOM_THROTTLE_MS = 16  # ~60 fps max redraw rate during scroll
TILE_SIZE_MIN = 8
TILE_SIZE_MAX = 48


# ---------------------------------------------------------------------------
# Tooltip
# ---------------------------------------------------------------------------


class Tooltip:
    def __init__(self, widget: tk.Widget, text: str, delay_ms: int = 500) -> None:
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.after_id: str | None = None
        self.tip_window: tk.Toplevel | None = None
        self.widget.bind("<Enter>", self._on_enter)
        self.widget.bind("<Leave>", self._on_leave)

    def _on_enter(self, _e: tk.Event) -> None:
        self.after_id = self.widget.after(self.delay_ms, self._show)

    def _on_leave(self, _e: tk.Event) -> None:
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None
        self._hide()

    def _show(self) -> None:
        if self.tip_window:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(
            tw, text=self.text, justify="left",
            bg=THEME["bg_panel"], fg=THEME["fg_secondary"],
            relief="solid", borderwidth=1, padx=6, pady=4, font=("Segoe UI", 9),
        ).pack()

    def _hide(self) -> None:
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


# ---------------------------------------------------------------------------
# Image export (PIL or fallback)
# ---------------------------------------------------------------------------


def _export_board_image_to_path(
    path: str, board: Board, tile_size: int, rules: dict[str, str]
) -> None:
    if Image is None or ImageDraw is None:
        raise RuntimeError("PIL (Pillow) is required for image export")
    font = ImageFont.load_default() if ImageFont else None
    outline_overrides = {"G": ("#FACC15", 3), "1": (THEME["highlight"], 2), "2": (THEME["highlight"], 2), "3": (THEME["highlight"], 2), "4": (THEME["highlight"], 2)}
    board_img = draw_board_to_image(
        board,
        tile_size,
        TILE_COLORS,
        TILE_STYLES,
        bg_color=THEME["bg_canvas"],
        border_color=THEME["border"],
        outline_overrides=outline_overrides,
        draw_glyphs=True,
        font=font,
    )
    if board_img is None:
        raise RuntimeError("PIL (Pillow) is required for image export")
    board_w, board_h = board_img.size
    legend_line_h = 22
    legend_pad = 20
    legend_title_h = 24
    legend_h = legend_title_h + legend_pad + len(TILE_COLORS) * legend_line_h + legend_pad
    total_h = board_h + legend_h
    image = Image.new("RGB", (board_w, total_h), THEME["bg_canvas"])
    image.paste(board_img, (0, 0))
    draw = ImageDraw.Draw(image)
    ly = board_h + legend_pad
    if font:
        draw.text((10, ly), "Legend (symbol — name — rule)", fill=THEME["fg_primary"], font=font)
    ly += legend_title_h
    for symbol in sorted(TILE_COLORS.keys()):
        style = TILE_STYLES.get(symbol, {"fg": "#111827", "glyph": symbol})
        color = TILE_COLORS.get(symbol, "#F8FAFC")
        name = TILE_NAMES.get(symbol, "Custom")
        rule = rules.get(symbol, "")
        draw.rectangle([10, ly, 28, ly + 18], fill=color, outline=THEME["border"])
        if font:
            draw.text((34, ly), f"{style.get('glyph', symbol)} {symbol} {name}", fill=THEME["fg_primary"], font=font)
            if rule:
                draw.text((200, ly), f"— {rule}", fill=THEME["fg_secondary"], font=font)
        ly += legend_line_h
    image.save(path)


def _export_png_fallback(path: str, board: Board, tile_size: int) -> None:
    """Export board to PNG without PIL (raw PNG encoding)."""
    w = len(board[0]) * tile_size
    h = len(board) * tile_size
    pixels = bytearray(w * h * 3)
    for y, row in enumerate(board):
        for x, symbol in enumerate(row):
            color = TILE_COLORS.get(symbol, "#F8FAFC")
            c = color.lstrip("#")
            if len(c) == 3:
                c = "".join(ch * 2 for ch in c)
            r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
            for py in range(y * tile_size, (y + 1) * tile_size):
                for px in range(x * tile_size, (x + 1) * tile_size):
                    idx = (py * w + px) * 3
                    pixels[idx : idx + 3] = bytes((r, g, b))
    scanlines = bytearray()
    stride = w * 3
    for y in range(h):
        scanlines.append(0)
        start = y * stride
        scanlines.extend(pixels[start : start + stride])

    def chunk(ct: bytes, data: bytes) -> bytes:
        crc = binascii.crc32(ct)
        crc = binascii.crc32(data, crc) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + ct + data + struct.pack(">I", crc)

    png = bytearray()
    png.extend(b"\x89PNG\r\n\x1a\n")
    png.extend(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)))
    png.extend(chunk(b"IDAT", zlib.compress(bytes(scanlines), level=9)))
    png.extend(chunk(b"IEND", b""))
    Path(path).write_bytes(bytes(png))


def _export_print_tiled(path_base: str, board: Board, paper: str) -> int:
    """Export board as tiled pages (A4 or Letter). Returns number of pages saved."""
    if Image is None or ImageDraw is None:
        return 0
    if paper == "Letter":
        page_w, page_h = int(8.5 * 150), int(11 * 150)
    else:
        page_w, page_h = int(210 / 25.4 * 150), int(297 / 25.4 * 150)
    board_w, board_h = len(board[0]), len(board)
    margin = 40
    mark = 12
    cell_px = min((page_w - 2 * margin) // board_w, (page_h - 2 * margin) // board_h)
    cells_per_page_x = (page_w - 2 * margin) // cell_px
    cells_per_page_y = (page_h - 2 * margin) // cell_px
    pages_x = (board_w + cells_per_page_x - 1) // cells_per_page_x
    pages_y = (board_h + cells_per_page_y - 1) // cells_per_page_y
    path_base = str(Path(path_base).with_suffix(""))
    for py in range(pages_y):
        for px in range(pages_x):
            img = Image.new("RGB", (page_w, page_h), "white")
            draw = ImageDraw.Draw(img)
            ox, oy = margin, margin
            for dy in range(cells_per_page_y):
                for dx in range(cells_per_page_x):
                    gx = px * cells_per_page_x + dx
                    gy = py * cells_per_page_y + dy
                    if gx >= board_w or gy >= board_h:
                        continue
                    symbol = board[gy][gx]
                    color = TILE_COLORS.get(symbol, "#F8FAFC")
                    x0, y0 = ox + dx * cell_px, oy + dy * cell_px
                    draw.rectangle([x0, y0, x0 + cell_px, y0 + cell_px], fill=color, outline="#333")
            for (mx, my) in [(margin, margin), (page_w - margin, margin), (page_w - margin, page_h - margin), (margin, page_h - margin)]:
                draw.ellipse([mx - mark, my - mark, mx + mark, my + mark], outline="#000", width=2)
            img.save(f"{path_base}_{py * pages_x + px + 1}.png")
    return pages_x * pages_y


def _export_print_poster(path: str, board: Board) -> None:
    """Export board as a single poster image."""
    if Image is None or ImageDraw is None:
        return
    cell_px = 24
    img = draw_board_to_image(
        board,
        cell_px,
        TILE_COLORS,
        None,
        bg_color=THEME["bg_canvas"],
        border_color=THEME["border"],
        draw_glyphs=False,
    )
    if img is not None:
        img.save(path)


def _export_cards_image(path: str) -> None:
    """Export card deck sheet image."""
    if Image is None or ImageDraw is None:
        return
    deck_names = sorted(set(get_tile_metadata(s)["deck_id"] for s in TILE_COLORS))
    card_w, card_h = 180, 270
    pad, cut_margin, cols = 10, 5, 4
    rows = (len(deck_names) + cols - 1) // cols
    sheet_w = cols * (card_w + 2 * pad) + 2 * cut_margin
    sheet_h = rows * (card_h + 2 * pad) + 2 * cut_margin
    img = Image.new("RGB", (sheet_w, sheet_h), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
        font_small = ImageFont.truetype("arial.ttf", 12)
    except Exception:
        font = ImageFont.load_default()
        font_small = font
    for i, deck in enumerate(deck_names):
        col, row = i % cols, i // cols
        x0 = cut_margin + col * (card_w + 2 * pad) + pad
        y0 = cut_margin + row * (card_h + 2 * pad) + pad
        x1, y1 = x0 + card_w, y0 + card_h
        draw.rectangle([x0, y0, x1, y1], fill="#F8FAFC", outline=THEME["border"], width=2)
        draw.text((x0 + card_w // 2 - 30, y0 + 20), f"Deck: {deck}", fill=THEME["bg_dark"], font=font)
        draw.text((x0 + 10, y0 + 60), "Draw when landing on tiles", fill=THEME["fg_secondary"], font=font_small)
        draw.text((x0 + 10, y0 + 80), "that use this deck.", fill=THEME["fg_secondary"], font=font_small)
        for (cx, cy) in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]:
            draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], outline="#000", width=1)
    img.save(path)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


class BoardGeneratorApp:
    """Main application window. Board canvas is the visual centre."""

    def __init__(self, root: tk.Tk, use_ctk: bool = False) -> None:
        self.root = root
        self._ctk = use_ctk and ctk is not None
        self.root.title("Board Generator Studio")
        self.root.minsize(900, 620)
        self.root.geometry("1280x800")
        if self._ctk:
            self.root.configure(fg_color=THEME["bg_dark"])
        else:
            self.root.configure(bg=THEME["bg_dark"])

        self.board_text = ""
        self.current_board: Board = []
        self.locked_mask: list[list[bool]] = []
        self.selection_rect: tuple[int, int, int, int] | None = None
        self._select_start: tuple[int, int] | None = None
        self.tile_size = 20
        self.app_mode_var = tk.StringVar(value="edit")
        self.generation_mode_var = tk.StringVar(value=GENERATION_MODE_LABELS["grid"])
        self.mode_var = tk.StringVar(value="editor")
        self.paint_tile_var = tk.StringVar(value=".")
        self.board_origin_x = 0
        self.board_origin_y = 0
        self.last_seed: int | None = None
        self._undo_stack: list[Board] = []
        self._redo_stack: list[Board] = []
        self._pan_start: tuple[int, int] | None = None
        self._hover_rect_id: int | None = None
        self._cell_items: list[list[tuple[int | None, int | None]]] = []
        self._tile_size_after_id: str | None = None
        self._zoom_throttle_after_id: str | None = None
        self._zoom_pending_cursor: tuple[int, int] | None = None
        self._zoom_pending_cell: tuple[int, int] | None = None
        self._resize_after_id: str | None = None
        self._generating = False
        self.tile_rules: dict[str, str] = dict(TILE_RULES)

        self._configure_styles()
        self._build_ui()
        self.refresh_legend()
        self._update_app_mode_ui()
        self._update_mode_ui()
        self._build_status_bar()
        self._bind_shortcuts()
        self.generate()

    # ---------- Setup / layout ----------
    def _configure_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        for orient in ("Vertical", "Horizontal"):
            style.configure(
                f"{orient}.TScrollbar",
                background=THEME["bg_panel"],
                troughcolor=THEME["border"],
                arrowcolor=THEME["fg_secondary"],
            )
            style.map(f"{orient}.TScrollbar", background=[("active", THEME["accent"])])

    # ---------- Widget helpers ----------
    def _run_async(
        self,
        callback: Callable[[], Any],
        on_done: Callable[[Any], None],
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        result: list[Any] = []
        err: list[Exception | None] = [None]

        def work() -> None:
            try:
                result.append(callback())
            except Exception as e:
                err[0] = e

        def finish() -> None:
            if err[0]:
                if on_error:
                    on_error(err[0])
                else:
                    messagebox.showerror("Error", str(err[0]))
            else:
                on_done(result[0])

        def schedule() -> None:
            self.root.after(0, finish)

        t = threading.Thread(target=lambda: (work(), schedule()))
        t.daemon = True
        t.start()

    def _frame(self, parent: Any, bg: str | None = None, **kw: Any) -> Any:
        if self._ctk:
            kw.setdefault("fg_color", "transparent")
            return ctk.CTkFrame(parent, **kw)
        bg = bg or THEME["bg_dark"]
        return tk.Frame(parent, bg=bg, **{k: v for k, v in kw.items() if k != "fg_color"})

    def _panel(self, parent: Any, title: str = "", **kw: Any) -> Any:
        r = THEME.get("panel_radius", 8)
        pad = THEME.get("spacing_md", 12)
        if self._ctk:
            f = ctk.CTkFrame(parent, fg_color=THEME["bg_panel"], corner_radius=r, **kw)
            if title:
                ctk.CTkLabel(f, text=title, font=ctk.CTkFont(size=THEME["font_title"], weight="bold"), text_color=THEME["fg_primary"]).pack(anchor="w", padx=pad, pady=(10, 6))
            return f
        f = tk.LabelFrame(parent, text=f" {title} " if title else "", bg=THEME["bg_panel"], fg=THEME["fg_primary"],
                          font=("Segoe UI", THEME["font_body"], "bold"), padx=pad, pady=THEME["spacing_sm"], **kw)
        return f

    def _label(self, parent: Any, text: str, **kw: Any) -> Any:
        if self._ctk:
            return ctk.CTkLabel(parent, text=text, text_color=THEME["fg_primary"], font=ctk.CTkFont(size=THEME["font_body"]), **kw)
        return tk.Label(parent, text=text, bg=THEME["bg_panel"], fg=THEME["fg_primary"], font=("Segoe UI", THEME["font_body"]), **kw)

    def _section_header(self, parent: Any, text: str) -> None:
        pad = THEME.get("spacing_md", 12)
        fs = THEME.get("font_secondary", 10)
        # Slightly more top margin for visual separation between sections
        pady_top = THEME.get("spacing_md", 12)
        pady_bottom = 2
        if self._ctk:
            ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=fs, weight="bold"), text_color=THEME["fg_secondary"]).pack(anchor="w", padx=pad, pady=(pady_top, pady_bottom))
        else:
            tk.Label(parent, text=text, bg=THEME["bg_panel"], fg=THEME["fg_secondary"], font=("Segoe UI", fs, "bold")).pack(anchor="w", padx=pad, pady=(pady_top, pady_bottom))

    def _btn(self, parent: Any, text: str, command: Callable[[], None], **kw: Any) -> Any:
        padx = kw.pop("padx", THEME.get("spacing_md", 12))
        pady = kw.pop("pady", THEME.get("spacing_sm", 6))
        if self._ctk:
            return ctk.CTkButton(parent, text=text, command=command, fg_color=THEME["accent"],
                                 hover_color=THEME["accent_hover"], corner_radius=THEME.get("panel_radius", 8),
                                 font=ctk.CTkFont(size=THEME["font_body"]), **kw)
        btn = tk.Button(parent, text=text, command=command, bg=THEME["accent"], fg="white",
                       activebackground=THEME["accent_hover"], relief="flat", padx=padx, pady=pady, cursor="hand2",
                       font=("Segoe UI", THEME["font_body"], "bold"), **kw)
        def on_enter(_e): btn.configure(bg=THEME["accent_hover"])
        def on_leave(_e): btn.configure(bg=THEME["accent"])
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    def _make_entry(self, parent: Any, textvariable: tk.StringVar, width: int) -> Any:
        """Create an entry widget (CTk or tk) for use in settings rows. width is pixels for CTk, approx. chars for tk."""
        if self._ctk:
            return ctk.CTkEntry(parent, textvariable=textvariable, width=width, fg_color=THEME["border"])
        char_width = max(4, min(30, width // 5))
        return tk.Entry(parent, textvariable=textvariable, width=char_width, bg=THEME["border"], fg=THEME["fg_primary"])

    def _make_option_menu(
        self, parent: Any, variable: tk.StringVar, values: list[str], width: int = 120
    ) -> Any:
        """Create an option menu (CTk or tk) for use in settings rows."""
        if self._ctk:
            return ctk.CTkOptionMenu(
                parent, variable=variable, values=values,
                fg_color=THEME["border"], button_color=THEME["accent"], width=width
            )
        return tk.OptionMenu(parent, variable, *values)

    def _scrollable_frame(self, parent: Any) -> Any:
        """Create a scrollable container: returns the inner frame to pack content into. Canvas + vscrollbar in parent."""
        bg = THEME["bg_panel"] if not self._ctk else THEME["bg_panel"]
        container = self._frame(parent)
        container.pack(fill="both", expand=True)
        if not self._ctk:
            container.configure(bg=bg)
        canvas = tk.Canvas(container, bg=bg, highlightthickness=0)
        vscroll = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)
        inner = tk.Frame(canvas, bg=bg)
        canvas_window = canvas.create_window(0, 0, window=inner, anchor="nw")

        def _on_frame_configure(_e: tk.Event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(e: tk.Event) -> None:
            canvas.itemconfig(canvas_window, width=e.width)

        def _on_mousewheel(event: tk.Event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        inner.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.bind("<MouseWheel>", _on_mousewheel)
        canvas.bind("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))
        vscroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        return inner

    def _collapsible_section(
        self, parent: Any, title: str, is_expanded: bool, accordion_state: list[tuple[Any, Any, Any]]
    ) -> tuple[Any, Any]:
        """Create a collapsible section: returns (header_btn, content_frame). Only one in accordion_state is expanded."""
        pad = THEME.get("spacing_md", 12)
        sm = THEME.get("spacing_sm", 6)
        header = self._frame(parent)
        header.pack(fill="x", padx=0, pady=(sm, 0))
        content = self._frame(parent)
        content.pack(fill="x", padx=0, pady=0)
        if self._ctk:
            arrow = ctk.CTkLabel(header, text="▼" if is_expanded else "▶", width=16, text_color=THEME["fg_secondary"], font=ctk.CTkFont(size=THEME["font_secondary"]))
            arrow.pack(side="left", padx=(pad, 4), pady=6)
            lbl = ctk.CTkLabel(header, text=title, font=ctk.CTkFont(size=THEME["font_secondary"], weight="bold"), text_color=THEME["fg_secondary"])
            lbl.pack(side="left", fill="x", expand=True, pady=6)
            header.configure(fg_color=THEME["bg_panel_hover"] if is_expanded else "transparent", corner_radius=THEME.get("panel_radius", 8))
        else:
            arrow = tk.Label(header, text="▼" if is_expanded else "▶", width=2, bg=THEME["bg_panel"], fg=THEME["fg_secondary"], font=("Segoe UI", THEME["font_secondary"]))
            arrow.pack(side="left", padx=(pad, 4), pady=6)
            lbl = tk.Label(header, text=title, bg=THEME["bg_panel"], fg=THEME["fg_secondary"], font=("Segoe UI", THEME["font_secondary"], "bold"))
            lbl.pack(side="left", fill="x", expand=True, pady=6)
        if not is_expanded:
            content.pack_forget()

        def toggle() -> None:
            for (h, c, a) in accordion_state:
                if (h, c, a) == (header, content, arrow):
                    if c.winfo_ismapped():
                        c.pack_forget()
                        if self._ctk:
                            a.configure(text="▶")
                            h.configure(fg_color="transparent")
                        else:
                            a.configure(text="▶")
                    else:
                        # Expand this: first collapse all others
                        for (oh, oc, oa) in accordion_state:
                            if (oh, oc, oa) != (header, content, arrow):
                                oc.pack_forget()
                                if self._ctk:
                                    oa.configure(text="▶")
                                    oh.configure(fg_color="transparent")
                                else:
                                    oa.configure(text="▶")
                        c.pack(fill="x", padx=0, pady=0)
                        if self._ctk:
                            a.configure(text="▼")
                            h.configure(fg_color=THEME["bg_panel_hover"])
                        else:
                            a.configure(text="▼")
                else:
                    c.pack_forget()
                    if self._ctk:
                        a.configure(text="▶")
                        h.configure(fg_color="transparent")
                    else:
                        a.configure(text="▶")

        header.bind("<Button-1>", lambda e: toggle())
        if self._ctk:
            lbl.bind("<Button-1>", lambda e: toggle())
            arrow.bind("<Button-1>", lambda e: toggle())
            header.configure(cursor="hand2")
        else:
            lbl.bind("<Button-1>", lambda e: toggle())
            arrow.bind("<Button-1>", lambda e: toggle())
            header.configure(cursor="hand2")
        accordion_state.append((header, content, arrow))
        return header, content

    def _build_menubar(self) -> None:
        """Build File, Edit, View, Game menu bar. Attach to root (tk) or CTk's underlying window."""
        menubar = tk.Menu(self.root)
        # File
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Generate", command=self.generate, accelerator="Ctrl+G")
        file_menu.add_command(label="Save text…", command=self.save_board, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Export image…", command=self.export_image)
        file_menu.add_command(label="Print export…", command=self._ask_export_print)
        file_menu.add_command(label="Export cards…", command=self._export_cards_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        # Edit
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo", command=self._undo, accelerator="Ctrl+Z")
        edit_menu.add_command(label="Redo", command=self._redo, accelerator="Ctrl+Y")
        # View
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="View page", command=lambda: self.app_mode_var.set("view") or self._update_app_mode_ui())
        view_menu.add_command(label="Edit page", command=lambda: self.app_mode_var.set("edit") or self._update_app_mode_ui())
        view_menu.add_separator()
        view_menu.add_command(label="Zoom in", command=lambda: self._on_wheel_zoom_delta(1))
        view_menu.add_command(label="Zoom out", command=lambda: self._on_wheel_zoom_delta(-1))
        # Game
        game_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Game", menu=game_menu)
        game_menu.add_command(label="Save game…", command=self.save_game)
        game_menu.add_command(label="Load game…", command=self.load_game)
        game_menu.add_separator()
        game_menu.add_command(label="Simulate", command=self._run_simulator)
        game_menu.add_command(label="Validate paths", command=self._validate_paths)
        # Attach: CTk uses .tk for the underlying Tk instance
        toplevel = getattr(self.root, "tk", self.root)
        try:
            toplevel.configure(menu=menubar)
        except Exception:
            pass

    def _build_ui(self) -> None:
        self._build_menubar()
        # Top bar: title | primary actions | Page | Mode + Paint | Zoom (grouped)
        sp = THEME.get("spacing_lg", 16)
        sm = THEME.get("spacing_md", 12)
        top = self._frame(self.root)
        top.pack(fill="x", padx=sp, pady=(10, 8))
        # Group 1: Title
        if self._ctk:
            ctk.CTkLabel(top, text="Board Generator Studio", font=ctk.CTkFont(size=18, weight="bold"),
                         text_color=THEME["fg_primary"]).pack(side="left", padx=(0, sp))
        else:
            tk.Label(top, text="Board Generator Studio", font=("Segoe UI", 18, "bold"),
                    bg=THEME["bg_dark"], fg=THEME["fg_primary"]).pack(side="left", padx=(0, sp))

        # Group 2: Primary actions (Edit page only)
        self.edit_top_bar = self._frame(top)
        self.edit_top_bar.pack(side="left", padx=(0, sm))
        gen_btn = self._btn(self.edit_top_bar, "Generate", self.generate)
        gen_btn.pack(side="left", padx=2)
        Tooltip(gen_btn, "Generate new board (Ctrl+G)")
        save_btn = self._btn(self.edit_top_bar, "Save text", self.save_board)
        save_btn.pack(side="left", padx=2)
        Tooltip(save_btn, "Save board to text file (Ctrl+S)")
        undo_btn = self._btn(self.edit_top_bar, "Undo", self._undo)
        undo_btn.pack(side="left", padx=2)
        Tooltip(undo_btn, "Undo (Ctrl+Z)")
        redo_btn = self._btn(self.edit_top_bar, "Redo", self._redo)
        redo_btn.pack(side="left", padx=2)
        Tooltip(redo_btn, "Redo (Ctrl+Y)")

        # Group 3: Page toggle
        app_mode_f = self._frame(top)
        app_mode_f.pack(side="left", padx=(0, sm))
        fs = THEME.get("font_secondary", 10)
        if self._ctk:
            ctk.CTkLabel(app_mode_f, text="Page:", text_color=THEME["fg_secondary"], font=ctk.CTkFont(size=fs)).pack(side="left", padx=(0, THEME["spacing_sm"]))
            for val, lbl in [("view", "View"), ("edit", "Edit")]:
                ctk.CTkRadioButton(app_mode_f, text=lbl, variable=self.app_mode_var, value=val,
                                    command=self._update_app_mode_ui, fg_color=THEME["accent"], text_color=THEME["fg_primary"]).pack(side="left", padx=4)
        else:
            tk.Label(app_mode_f, text="Page:", bg=THEME["bg_dark"], fg=THEME["fg_secondary"], font=("Segoe UI", fs)).pack(side="left", padx=(0, THEME["spacing_sm"]))
            for val, lbl in [("view", "View"), ("edit", "Edit")]:
                tk.Radiobutton(app_mode_f, text=lbl, variable=self.app_mode_var, value=val,
                               command=self._update_app_mode_ui, bg=THEME["bg_dark"], fg=THEME["fg_primary"],
                               selectcolor=THEME["border"], highlightthickness=0).pack(side="left", padx=4)

        # Group 4: Mode + Paint (Edit page only)
        mode_f = self._frame(self.edit_top_bar)
        mode_f.pack(side="left", padx=(sm, 0))
        if self._ctk:
            ctk.CTkLabel(mode_f, text="Mode:", text_color=THEME["fg_secondary"], font=ctk.CTkFont(size=fs)).pack(side="left", padx=(0, THEME["spacing_sm"]))
            for val, lbl in [("viewer", "View"), ("editor", "Edit"), ("select", "Select")]:
                ctk.CTkRadioButton(mode_f, text=lbl, variable=self.mode_var, value=val, command=self._update_mode_ui,
                                    fg_color=THEME["accent"], text_color=THEME["fg_primary"]).pack(side="left", padx=4)
        else:
            tk.Label(mode_f, text="Mode:", bg=THEME["bg_dark"], fg=THEME["fg_secondary"], font=("Segoe UI", fs)).pack(side="left", padx=(0, THEME["spacing_sm"]))
            for val, lbl in [("viewer", "View"), ("editor", "Edit"), ("select", "Select")]:
                tk.Radiobutton(mode_f, text=lbl, variable=self.mode_var, value=val, command=self._update_mode_ui,
                               bg=THEME["bg_dark"], fg=THEME["fg_primary"], selectcolor=THEME["border"], highlightthickness=0).pack(side="left", padx=4)
        if self._ctk:
            ctk.CTkLabel(self.edit_top_bar, text="Paint:", text_color=THEME["fg_secondary"], font=ctk.CTkFont(size=fs)).pack(side="left", padx=(sm, 4))
            self.paint_tile_menu = ctk.CTkOptionMenu(self.edit_top_bar, variable=self.paint_tile_var, values=sorted(TILE_COLORS.keys()),
                                                     fg_color=THEME["border"], button_color=THEME["accent"], width=80)
            self.paint_tile_menu.pack(side="left", padx=2)
        else:
            tk.Label(self.edit_top_bar, text="Paint:", bg=THEME["bg_dark"], fg=THEME["fg_secondary"], font=("Segoe UI", fs)).pack(side="left", padx=(sm, 4))
            self.paint_tile_menu = tk.OptionMenu(self.edit_top_bar, self.paint_tile_var, *sorted(TILE_COLORS.keys()))
            self.paint_tile_menu.pack(side="left", padx=2)

        # View-only: "Edit" button
        self.view_top_bar = self._frame(top)
        self._btn(self.view_top_bar, "Edit", lambda: self.app_mode_var.set("edit") or self._update_app_mode_ui()).pack(side="left", padx=2)
        if self._ctk:
            ctk.CTkLabel(self.view_top_bar, text="Generator:", text_color=THEME["fg_secondary"], font=ctk.CTkFont(size=fs)).pack(
                side="left", padx=(sm, 4)
            )
            self._view_gen_menu = ctk.CTkOptionMenu(
                self.view_top_bar,
                variable=self.generation_mode_var,
                values=list(GENERATION_MODE_LABELS.values()),
                fg_color=THEME["border"],
                button_color=THEME["accent"],
                width=220,
            )
            self._view_gen_menu.pack(side="left", padx=2)
        else:
            tk.Label(self.view_top_bar, text="Generator:", bg=THEME["bg_dark"], fg=THEME["fg_secondary"], font=("Segoe UI", fs)).pack(
                side="left", padx=(sm, 4)
            )
            self._view_gen_menu = tk.OptionMenu(
                self.view_top_bar, self.generation_mode_var, *list(GENERATION_MODE_LABELS.values())
            )
            self._view_gen_menu.pack(side="left", padx=2)
        Tooltip(self._view_gen_menu, "Grid = full terrain board. Pathway = intertwined routes (one start, one goal).")

        # Group 5: Zoom (always visible)
        self.size_var = tk.IntVar(value=self.tile_size)
        zoom_f = self._frame(top)
        zoom_f.pack(side="left", padx=(sm, 0))
        if self._ctk:
            ctk.CTkLabel(zoom_f, text="Zoom:", text_color=THEME["fg_secondary"], font=ctk.CTkFont(size=fs)).pack(side="left", padx=(0, 4))
            zoom_out_btn = ctk.CTkButton(zoom_f, text="−", width=36, command=lambda: self._on_wheel_zoom_delta(-1), fg_color=THEME["accent"], hover_color=THEME["accent_hover"], corner_radius=THEME.get("panel_radius", 8))
            zoom_out_btn.pack(side="left", padx=2)
            Tooltip(zoom_out_btn, "Zoom out")
            zoom_in_btn = ctk.CTkButton(zoom_f, text="+", width=36, command=lambda: self._on_wheel_zoom_delta(1), fg_color=THEME["accent"], hover_color=THEME["accent_hover"], corner_radius=THEME.get("panel_radius", 8))
            zoom_in_btn.pack(side="left", padx=2)
            Tooltip(zoom_in_btn, "Zoom in")
            self.size_label = ctk.CTkLabel(zoom_f, text=f"{self.tile_size}px", font=ctk.CTkFont(size=fs), text_color=THEME["fg_secondary"])
            self.size_label.pack(side="left", padx=4)
        else:
            tk.Label(zoom_f, text="Zoom:", bg=THEME["bg_dark"], fg=THEME["fg_secondary"], font=("Segoe UI", fs)).pack(side="left", padx=(0, 4))
            zo = self._btn(zoom_f, " − ", lambda: self._on_wheel_zoom_delta(-1))
            zo.pack(side="left", padx=2)
            Tooltip(zo, "Zoom out")
            zi = self._btn(zoom_f, " + ", lambda: self._on_wheel_zoom_delta(1))
            zi.pack(side="left", padx=2)
            Tooltip(zi, "Zoom in")
            self.size_label = tk.Label(zoom_f, text=f"{self.tile_size}px", bg=THEME["bg_dark"], fg=THEME["fg_secondary"], font=("Segoe UI", fs))
            self.size_label.pack(side="left", padx=4)

        # Main content: left sidebar | board (center) | right sidebar (columns resizable)
        self.content = self._frame(self.root)
        self.content.pack(fill="both", expand=True, padx=sp, pady=(0, THEME["spacing_md"]))
        LEFT_MINSIZE, RIGHT_MINSIZE = 260, 240
        self.content.grid_columnconfigure(0, minsize=LEFT_MINSIZE, weight=1)
        self.content.grid_columnconfigure(1, weight=10)
        self.content.grid_columnconfigure(2, minsize=RIGHT_MINSIZE, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        # Left: container with settings panel (scrollable) + collapse gutter
        self._left_collapsed = False
        self._right_collapsed = False
        left_container = self._frame(self.content)
        left_container.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=0)
        self.left_panel = self._panel(left_container, title="Settings")
        self.left_panel.pack(side="left", fill="both", expand=True)
        self.left_panel.configure(width=LEFT_MINSIZE)
        try:
            self.left_panel.pack_propagate(False)
        except Exception:
            pass
        left_inner = self._scrollable_frame(self.left_panel)
        self._build_left_panel(left_inner)
        left_gutter = self._frame(left_container)
        left_gutter.pack(side="right", fill="y", padx=0, pady=0)
        if self._ctk:
            left_gutter.configure(width=24, fg_color=THEME["bg_panel_hover"])
            self._left_gutter_btn = ctk.CTkButton(left_gutter, text="◀", width=24, height=32, command=self._toggle_left_panel, fg_color=THEME["border"], hover_color=THEME["accent"], corner_radius=0)
            self._left_gutter_btn.pack(fill="y", expand=True)
        else:
            left_gutter.configure(width=24, bg=THEME["bg_panel_hover"])
            self._left_gutter_btn = tk.Button(left_gutter, text="◀", width=2, command=self._toggle_left_panel, bg=THEME["border"], fg=THEME["fg_primary"], relief="flat", cursor="hand2")
            self._left_gutter_btn.pack(fill="y", expand=True)
        Tooltip(self._left_gutter_btn, "Collapse settings panel")
        self.left_container = left_container

        # Center: board canvas (the focus)
        self.center_panel = self._panel(self.content, title="Board")
        self.center_panel.grid(row=0, column=1, sticky="nsew", padx=6, pady=0)
        self.center_panel.grid_columnconfigure(0, weight=1)
        self.center_panel.grid_rowconfigure(0, weight=1)
        canvas_shell = self._frame(self.center_panel)
        canvas_shell.pack(fill="both", expand=True)
        if not self._ctk:
            canvas_shell.configure(bg=THEME["border"])
        canvas_shell.grid_columnconfigure(0, weight=1)
        canvas_shell.grid_rowconfigure(0, weight=1)
        self.board_canvas = tk.Canvas(canvas_shell, bg=THEME["bg_canvas"], highlightthickness=0, relief="flat")
        x_scroll = ttk.Scrollbar(canvas_shell, orient="horizontal", command=self.board_canvas.xview)
        y_scroll = ttk.Scrollbar(canvas_shell, orient="vertical", command=self.board_canvas.yview)
        self.board_canvas.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)
        self.board_canvas.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        self._bind_canvas()

        # Right: container with actions panel (scrollable) + collapse gutter
        right_container = self._frame(self.content)
        right_container.grid(row=0, column=2, sticky="nsew", padx=(6, 0), pady=0)
        self.right_panel = self._panel(right_container, title="Actions")
        self.right_panel.pack(side="right", fill="both", expand=True)
        self.right_panel.configure(width=RIGHT_MINSIZE)
        try:
            self.right_panel.pack_propagate(False)
        except Exception:
            pass
        right_inner = self._scrollable_frame(self.right_panel)
        self._build_right_panel(right_inner)
        right_gutter = self._frame(right_container)
        right_gutter.pack(side="left", fill="y", padx=0, pady=0)
        if self._ctk:
            right_gutter.configure(width=24, fg_color=THEME["bg_panel_hover"])
            self._right_gutter_btn = ctk.CTkButton(right_gutter, text="▶", width=24, height=32, command=self._toggle_right_panel, fg_color=THEME["border"], hover_color=THEME["accent"], corner_radius=0)
            self._right_gutter_btn.pack(fill="y", expand=True)
        else:
            right_gutter.configure(width=24, bg=THEME["bg_panel_hover"])
            self._right_gutter_btn = tk.Button(right_gutter, text="▶", width=2, command=self._toggle_right_panel, bg=THEME["border"], fg=THEME["fg_primary"], relief="flat", cursor="hand2")
            self._right_gutter_btn.pack(fill="y", expand=True)
        Tooltip(self._right_gutter_btn, "Collapse actions panel")
        self.right_container = right_container

        # Right: minimal actions for View page
        self.right_view_panel = self._panel(self.content, title="Actions")
        pad = THEME.get("spacing_md", 12)
        py = THEME.get("spacing_sm", 6)
        self._btn(self.right_view_panel, "Edit", lambda: self.app_mode_var.set("edit") or self._update_app_mode_ui()).pack(anchor="w", padx=pad, pady=py)
        self._section_header(self.right_view_panel, "Export")
        self._btn(self.right_view_panel, "Copy", self._copy_board).pack(anchor="w", padx=pad, pady=py)
        self._btn(self.right_view_panel, "Export image", self.export_image).pack(anchor="w", padx=pad, pady=py)
        self._section_header(self.right_view_panel, "Game")
        self._btn(self.right_view_panel, "Load game", self.load_game).pack(anchor="w", padx=pad, pady=py)

        # Legend (below content): collapsible header + content frame
        legend_container = self._panel(self.content, title="")
        legend_container.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        self.content.grid_rowconfigure(1, weight=0)
        self.legend_frame = legend_container
        self._legend_expanded = True
        pad = THEME.get("spacing_md", 12)
        fs = THEME.get("font_secondary", 10)
        legend_header = self._frame(legend_container)
        legend_header.pack(fill="x", padx=pad, pady=(8, 4))
        if self._ctk:
            self._legend_arrow_lbl = ctk.CTkLabel(legend_header, text="▼", width=16, text_color=THEME["fg_secondary"], font=ctk.CTkFont(size=fs))
            self._legend_arrow_lbl.pack(side="left", padx=(0, 4))
            self._legend_text_lbl = ctk.CTkLabel(legend_header, text="Legend", font=ctk.CTkFont(size=THEME["font_body"], weight="bold"), text_color=THEME["fg_primary"])
            self._legend_text_lbl.pack(side="left")
        else:
            self._legend_arrow_lbl = tk.Label(legend_header, text="▼", width=2, bg=THEME["bg_panel"], fg=THEME["fg_secondary"], font=("Segoe UI", fs))
            self._legend_arrow_lbl.pack(side="left", padx=(0, 4))
            self._legend_text_lbl = tk.Label(legend_header, text="Legend", bg=THEME["bg_panel"], fg=THEME["fg_primary"], font=("Segoe UI", THEME["font_body"], "bold"))
            self._legend_text_lbl.pack(side="left")
        legend_header.configure(cursor="hand2")
        legend_header.bind("<Button-1>", lambda e: self._toggle_legend())
        self._legend_arrow_lbl.bind("<Button-1>", lambda e: self._toggle_legend())
        self._legend_text_lbl.bind("<Button-1>", lambda e: self._toggle_legend())
        self.legend_content = self._frame(legend_container)
        self.legend_content.pack(fill="x", padx=0, pady=(0, 8))

    def _toggle_left_panel(self) -> None:
        """Collapse or expand the left (Settings) panel."""
        if self._left_collapsed:
            self.left_panel.pack(side="left", fill="both", expand=True)
            self.content.grid_columnconfigure(0, minsize=260, weight=1)
            self._left_gutter_btn.configure(text="◀")
            self._left_collapsed = False
        else:
            self.left_panel.pack_forget()
            self.content.grid_columnconfigure(0, minsize=28, weight=0)
            self._left_gutter_btn.configure(text="▶")
            self._left_collapsed = True

    def _toggle_right_panel(self) -> None:
        """Collapse or expand the right (Actions) panel."""
        if self._right_collapsed:
            self.right_panel.pack(side="right", fill="both", expand=True)
            self.content.grid_columnconfigure(2, minsize=240, weight=1)
            self._right_gutter_btn.configure(text="▶")
            self._right_collapsed = False
        else:
            self.right_panel.pack_forget()
            self.content.grid_columnconfigure(2, minsize=28, weight=0)
            self._right_gutter_btn.configure(text="◀")
            self._right_collapsed = True

    def _update_app_mode_ui(self) -> None:
        is_edit = self.app_mode_var.get() == "edit"
        if is_edit:
            self.edit_top_bar.pack(side="left", padx=2)
            self.view_top_bar.pack_forget()
            self.left_container.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=0)
            self.center_panel.grid(row=0, column=1, sticky="nsew", padx=6, pady=0)
            self.right_view_panel.grid_remove()
            self.right_container.grid(row=0, column=2, sticky="nsew", padx=(6, 0), pady=0)
        else:
            self.edit_top_bar.pack_forget()
            self.view_top_bar.pack(side="left", padx=2)
            self.left_container.grid_remove()
            self.center_panel.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=6, pady=0)
            self.right_container.grid_remove()
            self.right_view_panel.grid(row=0, column=2, sticky="nsew", padx=(6, 0), pady=0)
        self.refresh_legend()
        if is_edit:
            self._update_mode_ui()

    def _build_left_panel(self, parent: Any) -> None:
        self.width_var = tk.StringVar(value="50")
        self.height_var = tk.StringVar(value="50")
        self.seed_var = tk.StringVar(value="")
        self.weights_var = tk.StringVar(value=default_weights_string())
        self.symmetry_var = tk.StringVar(value="none")
        self.smoothing_var = tk.StringVar(value="1")
        self.cluster_var = tk.StringVar(value="0.2")
        self.tileset_var = tk.StringVar(value="Classic")
        self.custom_tile_var = tk.StringVar(value="")
        self.custom_weight_var = tk.StringVar(value="0.10")
        self.num_starts_var = tk.StringVar(value="4")
        self.goal_placement_var = tk.StringVar(value="center")
        self.start_placement_var = tk.StringVar(value="corners")
        self.min_goal_distance_var = tk.StringVar(value="0")
        self.safe_segment_radius_var = tk.StringVar(value="0")
        self.num_checkpoints_var = tk.StringVar(value="0")

        pad = THEME.get("spacing_md", 12)
        py = 3
        accordion_state: list[tuple[Any, Any, Any]] = []

        def row(p: Any, label: str, make_widget: Callable[[Any], Any], row_bg: str | None = None) -> None:
            r = self._frame(p, bg=row_bg or THEME["bg_panel"])
            r.pack(fill="x", padx=pad, pady=py)
            if self._ctk:
                ctk.CTkLabel(r, text=label, font=ctk.CTkFont(size=THEME["font_body"]), text_color=THEME["fg_primary"], width=72).pack(side="left", padx=(0, THEME["spacing_sm"]), pady=4)
                make_widget(r).pack(side="left", pady=4)
            else:
                tk.Label(r, text=label, bg=THEME["bg_panel"], fg=THEME["fg_primary"], font=("Segoe UI", THEME["font_body"]), width=10).pack(side="left", padx=(0, THEME["spacing_sm"]), pady=4)
                make_widget(r).pack(side="left", pady=4)

        # Section 1: Size (always expanded — board generator lives here so it stays visible)
        _, content_size = self._collapsible_section(parent, "Size", True, accordion_state)
        row(
            content_size,
            "Generator",
            lambda r: self._make_option_menu(
                r, self.generation_mode_var, list(GENERATION_MODE_LABELS.values()), 200
            ),
        )
        size_f = self._frame(content_size)
        size_f.pack(fill="x", padx=pad, pady=(pad, py))
        # 2×2 grid so all four presets fit in the narrow sidebar
        for idx, (w, h) in enumerate(BOARD_PRESETS):
            r, c = idx // 2, idx % 2
            self._btn(size_f, f"{w}×{h}", lambda w=w, h=h: self._apply_board_preset(w, h)).grid(row=r, column=c, padx=4, pady=4, sticky="w")
        size_f_inner = self._frame(content_size)
        size_f_inner.pack(fill="x", padx=pad, pady=py)
        if self._ctk:
            ctk.CTkLabel(size_f_inner, text="W:", width=20, text_color=THEME["fg_secondary"]).pack(side="left")
            ctk.CTkEntry(size_f_inner, textvariable=self.width_var, width=50, fg_color=THEME["border"]).pack(side="left", padx=2)
            ctk.CTkLabel(size_f_inner, text="H:", width=20, text_color=THEME["fg_secondary"]).pack(side="left", padx=(8, 0))
            ctk.CTkEntry(size_f_inner, textvariable=self.height_var, width=50, fg_color=THEME["border"]).pack(side="left", padx=2)
        else:
            tk.Label(size_f_inner, text="W", bg=THEME["bg_panel"], fg=THEME["fg_secondary"], width=4).pack(side="left")
            tk.Entry(size_f_inner, textvariable=self.width_var, width=5, bg=THEME["border"], fg=THEME["fg_primary"]).pack(side="left", padx=2)
            tk.Label(size_f_inner, text="H", bg=THEME["bg_panel"], fg=THEME["fg_secondary"], width=4).pack(side="left", padx=(8, 0))
            tk.Entry(size_f_inner, textvariable=self.height_var, width=5, bg=THEME["border"], fg=THEME["fg_primary"]).pack(side="left", padx=2)

        # Section 2: Generation
        _, content_gen = self._collapsible_section(parent, "Generation", False, accordion_state)
        row(content_gen, "Seed", lambda r: self._make_entry(r, self.seed_var, 100))
        row(content_gen, "Symmetry", lambda r: self._make_option_menu(r, self.symmetry_var, ["none", "horizontal", "vertical", "both"], 120))
        row(content_gen, "Tileset", lambda r: self._make_option_menu(r, self.tileset_var, list(TILESET_PRESETS.keys()), 140))
        self._btn(content_gen, "Apply tileset", self.apply_tileset).pack(anchor="w", padx=pad, pady=py)
        self._btn(content_gen, "Random seed + Generate", self._random_seed_and_generate).pack(anchor="w", padx=pad, pady=py)
        row(content_gen, "Weights", lambda r: self._make_entry(r, self.weights_var, 180))
        row(content_gen, "Smoothing", lambda r: self._make_entry(r, self.smoothing_var, 60))
        row(content_gen, "Cluster", lambda r: self._make_entry(r, self.cluster_var, 60))
        custom_f = self._frame(content_gen)
        custom_f.pack(fill="x", padx=pad, pady=py)
        self._make_entry(custom_f, self.custom_tile_var, 40).pack(side="left", padx=2)
        self._make_entry(custom_f, self.custom_weight_var, 50).pack(side="left", padx=2)
        if self._ctk:
            ctk.CTkButton(custom_f, text="Add tile", command=self.add_custom_tile, fg_color=THEME["accent"], width=70).pack(side="left", padx=2)
        else:
            self._btn(custom_f, "Add tile", self.add_custom_tile).pack(side="left", padx=2)

        # Section 3: Start & goal
        _, content_sg = self._collapsible_section(parent, "Start & goal", False, accordion_state)
        row(content_sg, "Starts", lambda r: self._make_entry(r, self.num_starts_var, 50))
        row(content_sg, "Goal", lambda r: self._make_option_menu(r, self.goal_placement_var, ["center", "random"], 100))
        row(content_sg, "Start pos", lambda r: self._make_option_menu(r, self.start_placement_var, ["corners", "random"], 100))
        row(content_sg, "Min dist", lambda r: self._make_entry(r, self.min_goal_distance_var, 50))
        row(content_sg, "Safe r", lambda r: self._make_entry(r, self.safe_segment_radius_var, 50))
        row(content_sg, "Checkpoints", lambda r: self._make_entry(r, self.num_checkpoints_var, 50))

    def _build_right_panel(self, parent: Any) -> None:
        pad = THEME.get("spacing_md", 12)
        py = THEME.get("spacing_sm", 6)
        section_pady = THEME.get("spacing_lg", 16)

        # Export: primary actions then "More export" dropdown
        self._section_header(parent, "Export")
        self._btn(parent, "Save text", self.save_board).pack(anchor="w", padx=pad, pady=py)
        self._btn(parent, "Copy", self._copy_board).pack(anchor="w", padx=pad, pady=py)
        self._btn(parent, "Export image", self.export_image).pack(anchor="w", padx=pad, pady=py)
        more_export_btn = self._btn(parent, "More export ▼", self._show_more_export_menu)
        more_export_btn.pack(anchor="w", padx=pad, pady=py)
        self._more_export_btn_ref = more_export_btn
        Tooltip(more_export_btn, "Print export, Export cards")

        # Game
        sep1 = self._frame(parent)
        sep1.pack(fill="x", padx=pad, pady=(section_pady, 0))
        if not self._ctk:
            sep1.configure(height=1, bg=THEME["border"])
        else:
            sep1.configure(height=1, fg_color=THEME["border"])
        try:
            sep1.pack_propagate(False)
        except Exception:
            pass
        self._section_header(parent, "Game")
        self._btn(parent, "Save game", self.save_game).pack(anchor="w", padx=pad, pady=py)
        self._btn(parent, "Load game", self.load_game).pack(anchor="w", padx=pad, pady=py)

        # Edit
        sep2 = self._frame(parent)
        sep2.pack(fill="x", padx=pad, pady=(section_pady, 0))
        if not self._ctk:
            sep2.configure(height=1, bg=THEME["border"])
        else:
            sep2.configure(height=1, fg_color=THEME["border"])
        try:
            sep2.pack_propagate(False)
        except Exception:
            pass
        self._section_header(parent, "Edit")
        self._btn(parent, "Validate paths", self._validate_paths).pack(anchor="w", padx=pad, pady=py)
        self._btn(parent, "Tile metadata", self._open_tile_metadata_editor).pack(anchor="w", padx=pad, pady=py)
        self._btn(parent, "Simulate", self._run_simulator).pack(anchor="w", padx=pad, pady=py)
        self._btn_lock_sel = self._btn(parent, "Lock selection", self._lock_selection)
        self._btn_lock_sel.pack(anchor="w", padx=pad, pady=py)
        self._btn_unlock_sel = self._btn(parent, "Unlock selection", self._unlock_selection)
        self._btn_unlock_sel.pack(anchor="w", padx=pad, pady=py)
        self._btn_regen_sel = self._btn(parent, "Regen selection", self._regen_selection)
        self._btn_regen_sel.pack(anchor="w", padx=pad, pady=py)

    def _show_more_export_menu(self) -> None:
        """Show popup menu for Print export and Export cards."""
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Print export…", command=self._ask_export_print)
        menu.add_command(label="Export cards…", command=self._export_cards_dialog)
        try:
            btn = getattr(self, "_more_export_btn_ref", None)
            if btn and btn.winfo_exists():
                x = btn.winfo_rootx()
                y = btn.winfo_rooty() + btn.winfo_height()
                menu.tk_popup(x, y)
        except Exception:
            menu.post(0, 0)

    def _bind_canvas(self) -> None:
        self.board_canvas.bind("<Button-1>", self._on_canvas_click)
        self.board_canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.board_canvas.bind("<B1-Motion>", self._paint_tile)
        self.board_canvas.bind("<Button-2>", self._start_pan)
        self.board_canvas.bind("<B2-Motion>", self._do_pan)
        self.board_canvas.bind("<ButtonRelease-2>", self._end_pan)
        self.board_canvas.bind("<MouseWheel>", self._on_wheel_zoom)
        self.board_canvas.bind("<Button-4>", lambda e: self._on_wheel_zoom_delta(1))
        self.board_canvas.bind("<Button-5>", lambda e: self._on_wheel_zoom_delta(-1))
        self.board_canvas.bind("<Motion>", self._on_canvas_motion)
        self.board_canvas.bind("<Leave>", self._on_canvas_leave)
        self.board_canvas.bind("<Configure>", self._on_canvas_resize)

    def _build_status_bar(self) -> None:
        fs = THEME.get("font_secondary", 10)
        pad = THEME.get("spacing_md", 12)
        if self._ctk:
            self.status_frame = ctk.CTkFrame(self.root, fg_color=THEME["border"], height=28, corner_radius=0)
            self.status_frame.pack(side="bottom", fill="x")
            self.status_frame.pack_propagate(False)
            self.status_label = ctk.CTkLabel(self.status_frame, text="Ready", anchor="w", font=ctk.CTkFont(size=fs), text_color=THEME["fg_secondary"])
            self.status_label.pack(side="left", fill="x", expand=True, padx=pad, pady=5)
            self.status_hover_label = ctk.CTkLabel(self.status_frame, text="", anchor="e", font=ctk.CTkFont(size=fs), text_color=THEME["fg_secondary"])
            self.status_hover_label.pack(side="right", padx=pad, pady=5)
        else:
            self.status_frame = tk.Frame(self.root, bg=THEME["border"], height=26)
            self.status_frame.pack(side="bottom", fill="x")
            self.status_frame.pack_propagate(False)
            self.status_label = tk.Label(self.status_frame, text="Ready", anchor="w", bg=THEME["border"], fg=THEME["fg_secondary"], font=("Segoe UI", fs))
            self.status_label.pack(side="left", fill="x", expand=True, padx=pad, pady=4)
            self.status_hover_label = tk.Label(self.status_frame, text="", anchor="e", bg=THEME["border"], fg=THEME["fg_secondary"], font=("Segoe UI", fs))
            self.status_hover_label.pack(side="right", padx=pad, pady=4)

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-g>", lambda e: self.generate())
        self.root.bind("<Control-s>", lambda e: self.save_board())
        self.root.bind("<Control-z>", lambda e: self._undo())
        self.root.bind("<Control-y>", lambda e: self._redo())

    def _apply_board_preset(self, width: int, height: int) -> None:
        self.width_var.set(str(width))
        self.height_var.set(str(height))

    def _random_seed_and_generate(self) -> None:
        import random
        self.seed_var.set(str(random.randint(1, 2**31 - 1)))
        self.generate()

    def _build_options(self) -> BoardOptions:
        seed_text = self.seed_var.get().strip()
        seed = int(seed_text) if seed_text else None
        num_starts = int(self.num_starts_var.get()) if self.num_starts_var.get().strip().isdigit() else 4
        num_starts = max(1, min(4, num_starts))
        min_dist = max(0, int(self.min_goal_distance_var.get())) if self.min_goal_distance_var.get().strip().isdigit() else 0
        safe_r = max(0, int(self.safe_segment_radius_var.get())) if self.safe_segment_radius_var.get().strip().isdigit() else 0
        n_check = max(0, int(self.num_checkpoints_var.get())) if self.num_checkpoints_var.get().strip().isdigit() else 0
        return BoardOptions(
            width=int(self.width_var.get()) if self.width_var.get().strip().isdigit() else 50,
            height=int(self.height_var.get()) if self.height_var.get().strip().isdigit() else 50,
            seed=seed,
            terrain_weights=parse_weights(self.weights_var.get()),
            symmetry=self.symmetry_var.get(),
            smoothing_passes=int(self.smoothing_var.get()) if self.smoothing_var.get().strip().isdigit() else 1,
            cluster_bias=float(self.cluster_var.get()) if self.cluster_var.get().strip() else 0.2,
            generation_mode=_GENERATION_UI_LABEL_TO_MODE.get(
                self.generation_mode_var.get(), "grid"
            ),
            num_starts=num_starts,
            goal_placement=self.goal_placement_var.get(),
            start_placement=self.start_placement_var.get(),
            min_goal_distance=min_dist,
            safe_segment_radius=safe_r,
            num_checkpoints=n_check,
        )

    def _ensure_locked_mask(self) -> None:
        if not self.current_board:
            self.locked_mask = []
            return
        h, w = len(self.current_board), len(self.current_board[0])
        if len(self.locked_mask) != h or (self.locked_mask and len(self.locked_mask[0]) != w):
            self.locked_mask = [[False] * w for _ in range(h)]

    def generate(self, regenerate_selection_only: bool = False) -> None:
        if self._generating:
            return
        try:
            options = self._build_options()
        except Exception as e:
            messagebox.showerror("Invalid options", str(e))
            return
        if options.seed is not None:
            self.last_seed = options.seed
        self._generating = True
        self.status_label.configure(text="Generating…")
        current_copy = [row[:] for row in self.current_board] if self.current_board else None
        sel_rect = self.selection_rect
        locked_copy = [row[:] for row in self.locked_mask] if self.locked_mask else None

        def worker() -> tuple[Board, bool, list[int]]:
            board = generate_board_with_selection_or_locks(options, regenerate_selection_only, current_copy, sel_rect, locked_copy)
            all_ok, unreachable = check_pathability(board)
            return board, all_ok, unreachable

        def on_done(result: tuple[Board, bool, list[int]]) -> None:
            self._generating = False
            board, all_ok, unreachable = result
            self._redo_stack.clear()
            if self.current_board and not regenerate_selection_only:
                self._push_undo()
            self._ensure_locked_mask()
            self.current_board = board
            self.board_text = board_to_string(board)
            self._refresh_editor_tile_options()
            self._draw_board(board)
            self.refresh_legend()
            if all_ok:
                self._update_status_from_board()
            else:
                unreachable_str = ", ".join(str(i + 1) for i in unreachable)
                self.status_label.configure(text=f"Start(s) {unreachable_str} unreachable")
                messagebox.showwarning("Pathability", f"Start(s) {unreachable_str} cannot reach the goal.")

        def on_error(e: Exception) -> None:
            self._generating = False
            self._update_status_from_board()
            messagebox.showerror("Error", str(e))

        self._run_async(worker, on_done, on_error)

    def _push_undo(self) -> None:
        if not self.current_board:
            return
        self._redo_stack.clear()
        self._undo_stack.append([row[:] for row in self.current_board])
        if len(self._undo_stack) > MAX_UNDO_STEPS:
            self._undo_stack.pop(0)

    def _undo(self) -> None:
        if not self._undo_stack:
            return
        if self.current_board:
            self._redo_stack.append([row[:] for row in self.current_board])
            if len(self._redo_stack) > MAX_UNDO_STEPS:
                self._redo_stack.pop(0)
        self.current_board = [row[:] for row in self._undo_stack.pop()]
        self.board_text = board_to_string(self.current_board)
        self._draw_board(self.current_board)
        self._update_status_from_board()

    def _redo(self) -> None:
        if not self._redo_stack:
            return
        if self.current_board:
            self._undo_stack.append([row[:] for row in self.current_board])
            if len(self._undo_stack) > MAX_UNDO_STEPS:
                self._undo_stack.pop(0)
        self.current_board = [row[:] for row in self._redo_stack.pop()]
        self.board_text = board_to_string(self.current_board)
        self._draw_board(self.current_board)
        self._update_status_from_board()

    def _update_status_from_board(self) -> None:
        if not self.current_board:
            self.status_label.configure(text="Ready")
            return
        w, h = len(self.current_board[0]), len(self.current_board)
        seed_str = f" • Seed: {self.last_seed}" if self.last_seed is not None else ""
        label, details = compute_route_quality(self.current_board)
        self.status_label.configure(text=f"Board {w}×{h}{seed_str} • Route: {label} ({details})")

    def apply_tileset(self) -> None:
        chosen = TILESET_PRESETS.get(self.tileset_var.get(), TILESET_PRESETS["Classic"])
        self.weights_var.set(",".join(f"{s}:{w:.2f}" for s, w in chosen.items()))
        self._refresh_editor_tile_options()
        self.refresh_legend()
        self.status_label.configure(text="Tileset applied. Click Generate to create a board.")

    def add_custom_tile(self) -> None:
        symbol = self.custom_tile_var.get().strip()
        if len(symbol) != 1:
            messagebox.showerror("Invalid tile", "Custom tile symbol must be exactly one character.")
            return
        try:
            weight = float(self.custom_weight_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid weight", "Custom tile weight must be numeric.")
            return
        if weight < 0:
            messagebox.showerror("Invalid weight", "Weight cannot be negative.")
            return
        weights = parse_weights(self.weights_var.get())
        weights[symbol] = weight
        self.weights_var.set(",".join(f"{t}:{v:.2f}" for t, v in weights.items()))
        if symbol not in TILE_COLORS:
            TILE_COLORS[symbol] = "#E2E8F0"
            TILE_NAMES[symbol] = f"Tile '{symbol}'"
            TILE_STYLES[symbol] = {"fg": "#111827", "bg": "#F8FAFC", "glyph": symbol}
        self._refresh_editor_tile_options()
        self.refresh_legend()

    def _refresh_editor_tile_options(self) -> None:
        values = sorted(TILE_COLORS.keys())
        if self._ctk:
            self.paint_tile_menu.configure(values=values)
        else:
            menu = self.paint_tile_menu["menu"]
            menu.delete(0, "end")
            for s in values:
                menu.add_command(label=s, command=lambda v=s: self.paint_tile_var.set(v))
        if self.paint_tile_var.get() not in TILE_COLORS:
            self.paint_tile_var.set(values[0] if values else ".")

    def _update_mode_ui(self) -> None:
        if self.app_mode_var.get() != "edit":
            return
        mode = self.mode_var.get()
        if self._ctk:
            self.paint_tile_menu.configure(state="normal" if mode == "editor" else "disabled")
        sel_ok = mode == "select" and self.selection_rect is not None and self.current_board
        for btn in (getattr(self, "_btn_lock_sel", None), getattr(self, "_btn_unlock_sel", None), getattr(self, "_btn_regen_sel", None)):
            if btn and btn.winfo_exists():
                btn.configure(state="normal" if sel_ok else "disabled")

    def _on_legend_chip_click(self, symbol: str) -> None:
        self.mode_var.set("editor")
        self._update_mode_ui()
        self.paint_tile_var.set(symbol)

    def _toggle_legend(self) -> None:
        """Toggle legend content visibility and update header."""
        self._legend_expanded = not self._legend_expanded
        if self._legend_expanded:
            self.legend_content.pack(fill="x", padx=0, pady=(0, 8))
            self._legend_arrow_lbl.configure(text="▼")
            self._legend_text_lbl.configure(text="Legend")
        else:
            self.legend_content.pack_forget()
            n = len(TILE_COLORS)
            self._legend_arrow_lbl.configure(text="▶")
            self._legend_text_lbl.configure(text=f"{n} tile type(s) — click to expand")

    def refresh_legend(self) -> None:
        for child in self.legend_content.winfo_children():
            child.destroy()
        pad = THEME.get("spacing_md", 12)
        fs = THEME.get("font_secondary", 10)
        is_edit = getattr(self, "app_mode_var", None) and self.app_mode_var.get() == "edit"
        if not is_edit:
            if self._ctk:
                ctk.CTkLabel(self.legend_content, text="Switch to Edit to change the board.", font=ctk.CTkFont(size=fs), text_color=THEME["fg_secondary"]).pack(anchor="w", padx=pad, pady=(6, 8))
            else:
                tk.Label(self.legend_content, text="Switch to Edit to change the board.", bg=THEME["bg_panel"], fg=THEME["fg_secondary"], font=("Segoe UI", fs)).pack(anchor="w", padx=pad, pady=(6, 8))
            if not self._legend_expanded:
                self._legend_arrow_lbl.configure(text="▶")
                self._legend_text_lbl.configure(text="Legend — click to expand")
            return
        n = len(TILE_COLORS)
        if not self._legend_expanded:
            self._legend_arrow_lbl.configure(text="▶")
            self._legend_text_lbl.configure(text=f"{n} tile type(s) — click to expand")
        else:
            self._legend_arrow_lbl.configure(text="▼")
            self._legend_text_lbl.configure(text="Legend")
        rules = getattr(self, "tile_rules", TILE_RULES)
        if self._ctk:
            ctk.CTkLabel(self.legend_content, text="Click a tile to use as paint (Editor mode)", font=ctk.CTkFont(size=fs), text_color=THEME["fg_secondary"]).pack(anchor="w", padx=pad, pady=(6, 0))
            row_f = ctk.CTkFrame(self.legend_content, fg_color="transparent")
            row_f.pack(fill="x", padx=pad, pady=8)
            for symbol, color in TILE_COLORS.items():
                style = TILE_STYLES.get(symbol, {"fg": "#111827", "glyph": symbol})
                name = TILE_NAMES.get(symbol, "Custom")
                rule = rules.get(symbol, "")
                label_text = f" {style['glyph']} {symbol} {name}"
                if rule:
                    label_text += f" — {rule}"
                chip = ctk.CTkLabel(row_f, text=label_text, fg_color=color, text_color=style["fg"], font=ctk.CTkFont(size=fs, weight="bold"), corner_radius=THEME.get("panel_radius", 8), padx=8, pady=4, cursor="hand2")
                chip.pack(side="left", padx=(0, 8), pady=3)
                chip.bind("<Button-1>", lambda e, s=symbol: self._on_legend_chip_click(s))
        else:
            tk.Label(self.legend_content, text="Click a tile to use as paint (Editor mode)", bg=THEME["bg_panel"], fg=THEME["fg_secondary"], font=("Segoe UI", fs)).pack(anchor="w", padx=pad, pady=(6, 0))
            row_f = tk.Frame(self.legend_content, bg=THEME["bg_panel"])
            row_f.pack(fill="x", padx=pad, pady=8)
            for symbol, color in TILE_COLORS.items():
                style = TILE_STYLES.get(symbol, {"fg": "#111827", "glyph": symbol})
                name = TILE_NAMES.get(symbol, "Custom")
                rule = rules.get(symbol, "")
                label_text = f" {style['glyph']} {symbol} {name}"
                if rule:
                    label_text += f" — {rule}"
                chip = tk.Label(row_f, text=label_text, bg=color, fg=style["fg"], padx=8, pady=4, font=("Segoe UI", fs, "bold"), cursor="hand2", relief="flat")
                chip.pack(side="left", padx=(0, 8), pady=3)
                chip.bind("<Button-1>", lambda e, s=symbol: self._on_legend_chip_click(s))
        if not self._legend_expanded:
            self.legend_content.pack_forget()
        else:
            self.legend_content.pack(fill="x", padx=0, pady=(0, 8))

    def _draw_board(self, board: Board) -> None:
        self.board_canvas.delete("all")
        self._cell_items = []
        if not board:
            self.board_canvas.configure(scrollregion=(0, 0, 0, 0))
            return
        tile = self.tile_size
        width = len(board[0]) * tile
        height = len(board) * tile
        cw = max(1, self.board_canvas.winfo_width())
        ch = max(1, self.board_canvas.winfo_height())
        self.board_origin_x = max(12, (cw - width) // 2)
        self.board_origin_y = max(12, (ch - height) // 2)
        for y, row in enumerate(board):
            self._cell_items.append([])
            for x, symbol in enumerate(row):
                style = TILE_STYLES.get(symbol, {"fg": "#111827", "bg": "#F8FAFC", "glyph": symbol})
                color = TILE_COLORS.get(symbol, style["bg"])
                x0 = self.board_origin_x + x * tile
                y0 = self.board_origin_y + y * tile
                x1, y1 = x0 + tile, y0 + tile
                border = THEME["border"]
                rid = self.board_canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline=border, width=1)
                tid = self.board_canvas.create_text(x0 + tile / 2, y0 + tile / 2, text=style.get("glyph", symbol), fill=style["fg"], font=("Consolas", max(8, tile // 2), "bold"))
                self._cell_items[y].append((rid, tid))
        self.board_canvas.configure(scrollregion=(0, 0, self.board_origin_x + width + 12, self.board_origin_y + height + 12))
        if self.selection_rect:
            x0, y0, x1, y1 = self.selection_rect
            self.board_canvas.create_rectangle(
                self.board_origin_x + x0 * tile, self.board_origin_y + y0 * tile,
                self.board_origin_x + (x1 + 1) * tile, self.board_origin_y + (y1 + 1) * tile,
                outline=THEME["highlight"], width=3, dash=(4, 4)
            )

    def _create_cell_at(self, x: int, y: int, symbol: str, tile: int) -> tuple[int, int]:
        style = TILE_STYLES.get(symbol, {"fg": "#111827", "bg": "#F8FAFC", "glyph": symbol})
        color = TILE_COLORS.get(symbol, style["bg"])
        x0 = self.board_origin_x + x * tile
        y0 = self.board_origin_y + y * tile
        rid = self.board_canvas.create_rectangle(x0, y0, x0 + tile, y0 + tile, fill=color, outline=THEME["border"], width=1)
        tid = self.board_canvas.create_text(x0 + tile / 2, y0 + tile / 2, text=style.get("glyph", symbol), fill=style["fg"], font=("Consolas", max(8, tile // 2), "bold"))
        return rid, tid

    def _draw_cell(self, x: int, y: int) -> None:
        if not self.current_board or not self._cell_items or y < 0 or y >= len(self._cell_items) or x < 0 or x >= len(self._cell_items[0]):
            return
        rid, tid = self._cell_items[y][x]
        self.board_canvas.delete(rid)
        self.board_canvas.delete(tid)
        r, t = self._create_cell_at(x, y, self.current_board[y][x], self.tile_size)
        self._cell_items[y][x] = (r, t)

    def _event_to_cell(self, event: tk.Event) -> tuple[int, int] | None:
        if not self.current_board:
            return None
        tile = self.tile_size
        cx = self.board_canvas.canvasx(event.x) - self.board_origin_x
        cy = self.board_canvas.canvasy(event.y) - self.board_origin_y
        ix, iy = int(cx // tile), int(cy // tile)
        if 0 <= iy < len(self.current_board) and 0 <= ix < len(self.current_board[0]):
            return (ix, iy)
        return None

    def _on_canvas_click(self, event: tk.Event) -> None:
        if self.app_mode_var.get() == "view":
            return
        if self.mode_var.get() == "select" and self.current_board:
            cell = self._event_to_cell(event)
            if cell is not None:
                self._select_start = cell
            return
        if self.mode_var.get() == "editor" and self.current_board:
            self._push_undo()
        self._paint_tile(event)

    def _on_canvas_release(self, event: tk.Event) -> None:
        if self.app_mode_var.get() == "view":
            return
        if self.mode_var.get() == "select" and self._select_start is not None and self.current_board:
            cell = self._event_to_cell(event)
            if cell is not None:
                x0, y0 = self._select_start
                x1, y1 = cell
                self.selection_rect = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
            self._select_start = None
            self._update_mode_ui()
            self._draw_board(self.current_board)
            return
        self._select_start = None

    def _start_pan(self, event: tk.Event) -> None:
        self._pan_start = (event.x, event.y)

    def _do_pan(self, event: tk.Event) -> None:
        if self._pan_start is None:
            return
        dx = event.x - self._pan_start[0]
        dy = event.y - self._pan_start[1]
        self._pan_start = (event.x, event.y)
        self.board_canvas.xview_scroll(-dx, "units")
        self.board_canvas.yview_scroll(-dy, "units")

    def _end_pan(self, _e: tk.Event) -> None:
        self._pan_start = None

    def _on_wheel_zoom(self, event: tk.Event) -> None:
        d = getattr(event, "delta", 0) or 0
        step = 1 if d >= 0 else -1
        self._on_wheel_zoom_delta(step, event=event)

    def _on_wheel_zoom_delta(self, delta: int, event: tk.Event | None = None) -> None:
        new_size = max(TILE_SIZE_MIN, min(TILE_SIZE_MAX, self.tile_size + delta))
        if new_size == self.tile_size:
            return
        target_cell: tuple[int, int] | None = None
        cursor_xy: tuple[int, int] | None = None
        if event and self.current_board:
            cx = self.board_canvas.canvasx(event.x)
            cy = self.board_canvas.canvasy(event.y)
            tile = self.tile_size
            ix = int((cx - self.board_origin_x) // tile)
            iy = int((cy - self.board_origin_y) // tile)
            h, w = len(self.current_board), len(self.current_board[0])
            if 0 <= ix < w and 0 <= iy < h:
                target_cell = (ix, iy)
                cursor_xy = (event.x, event.y)
        self.tile_size = new_size
        self.size_var.set(new_size)
        if self._ctk:
            self.size_label.configure(text=f"{self.tile_size}px")
        else:
            self.size_label.configure(text=f"{self.tile_size}px")
        if not self.current_board:
            return
        if event and target_cell is not None and cursor_xy is not None:
            self._zoom_pending_cursor = cursor_xy
            self._zoom_pending_cell = target_cell
            if self._zoom_throttle_after_id is None:
                self._draw_board(self.current_board)
                self._apply_zoom_to_cursor(cursor_xy, target_cell)
                self._zoom_throttle_after_id = self.root.after(
                    ZOOM_THROTTLE_MS,
                    self._zoom_throttled_redraw,
                )
        else:
            if self._zoom_throttle_after_id:
                self.root.after_cancel(self._zoom_throttle_after_id)
                self._zoom_throttle_after_id = None
            self._zoom_pending_cursor = None
            self._zoom_pending_cell = None
            self._draw_board(self.current_board)

    def _zoom_throttled_redraw(self) -> None:
        self._zoom_throttle_after_id = None
        if not self.current_board:
            return
        self._draw_board(self.current_board)
        if self._zoom_pending_cell is not None and self._zoom_pending_cursor is not None:
            self._apply_zoom_to_cursor(self._zoom_pending_cursor, self._zoom_pending_cell)

    def _apply_zoom_to_cursor(self, cursor_xy: tuple[int, int], target_cell: tuple[int, int]) -> None:
        ix, iy = target_cell
        tile = self.tile_size
        cell_center_x = self.board_origin_x + (ix + 0.5) * tile
        cell_center_y = self.board_origin_y + (iy + 0.5) * tile
        sr = self.board_canvas.cget("scrollregion").split()
        if len(sr) < 4:
            return
        try:
            sr_w = float(sr[2]) - float(sr[0])
            sr_h = float(sr[3]) - float(sr[1])
        except (ValueError, IndexError):
            return
        cw = max(1, self.board_canvas.winfo_width())
        ch = max(1, self.board_canvas.winfo_height())
        frac_x = (cell_center_x - cursor_xy[0]) / sr_w if sr_w > 0 else 0
        frac_y = (cell_center_y - cursor_xy[1]) / sr_h if sr_h > 0 else 0
        frac_x = max(0, min(1 - cw / sr_w, frac_x)) if sr_w > cw else 0
        frac_y = max(0, min(1 - ch / sr_h, frac_y)) if sr_h > ch else 0
        self.board_canvas.xview_moveto(frac_x)
        self.board_canvas.yview_moveto(frac_y)

    def _on_canvas_motion(self, event: tk.Event) -> None:
        if not self.current_board:
            self.status_hover_label.configure(text="")
            return
        cell = self._event_to_cell(event)
        if cell:
            x, y = cell
            name = TILE_NAMES.get(self.current_board[y][x], f"'{self.current_board[y][x]}'")
            self.status_hover_label.configure(text=f"({x},{y}) {name}")
            if self.app_mode_var.get() == "edit" and self.mode_var.get() == "editor":
                self._draw_hover_cell(x, y)
        else:
            self.status_hover_label.configure(text="")
            self._clear_hover()

    def _draw_hover_cell(self, x: int, y: int) -> None:
        self._clear_hover()
        tile = self.tile_size
        x0 = self.board_origin_x + x * tile + 1
        y0 = self.board_origin_y + y * tile + 1
        self._hover_rect_id = self.board_canvas.create_rectangle(x0, y0, x0 + tile - 2, y0 + tile - 2, outline=THEME["highlight"], width=2)

    def _clear_hover(self) -> None:
        if self._hover_rect_id is not None:
            self.board_canvas.delete(self._hover_rect_id)
            self._hover_rect_id = None

    def _on_canvas_leave(self, _e: tk.Event) -> None:
        self.status_hover_label.configure(text="")
        self._clear_hover()

    def _on_canvas_resize(self, _e: tk.Event) -> None:
        if self._resize_after_id:
            self.root.after_cancel(self._resize_after_id)
        def deferred() -> None:
            self._resize_after_id = None
            if self.current_board:
                self._draw_board(self.current_board)
        self._resize_after_id = self.root.after(DEBOUNCE_MS, deferred)

    # ---------- Canvas: paint ----------
    def _paint_tile(self, event: tk.Event) -> None:
        if self.app_mode_var.get() != "edit" or self.mode_var.get() != "editor" or not self.current_board:
            return
        cell = self._event_to_cell(event)
        if not cell:
            return
        x, y = cell
        selected = self.paint_tile_var.get()
        if not selected:
            return
        if selected in SPECIAL_SYMBOLS:
            h, w = len(self.current_board), len(self.current_board[0])
            for oy in range(h):
                for ox in range(w):
                    if self.current_board[oy][ox] == selected and (ox, oy) != (x, y):
                        self.current_board[oy][ox] = "."
                        if self._cell_items and oy < len(self._cell_items) and ox < len(self._cell_items[0]):
                            self._draw_cell(ox, oy)
        self.current_board[y][x] = selected
        self.board_text = board_to_string(self.current_board)
        if self._cell_items and y < len(self._cell_items) and x < len(self._cell_items[0]):
            self._draw_cell(x, y)
        else:
            self._draw_board(self.current_board)

    # ---------- Save / load / export ----------
    def save_board(self) -> None:
        if not self.board_text.strip():
            messagebox.showwarning("Nothing to save", "Generate a board first.")
            return
        path = filedialog.asksaveasfilename(title="Save board", defaultextension=".txt", filetypes=[("Text files", "*.txt"), ("All files", "*.*")], initialfile="generated_board.txt")
        if path:
            Path(path).write_text(self.board_text, encoding="utf-8")
            messagebox.showinfo("Saved", f"Board saved to:\n{path}")

    def save_game(self) -> None:
        if not self.current_board:
            messagebox.showwarning("Nothing to save", "Generate a board first.")
            return
        path = filedialog.asksaveasfilename(title="Save game", defaultextension=".json", filetypes=[("JSON", "*.json"), ("All files", "*.*")], initialfile="board_game.json")
        if path:
            data = {"version": 1, "board": [list(row) for row in self.current_board], "tile_rules": dict(self.tile_rules), "tile_metadata": dict(TILE_METADATA)}
            Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
            messagebox.showinfo("Saved", f"Game saved to:\n{path}")

    def load_game(self) -> None:
        path = filedialog.askopenfilename(title="Load game", filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            board = data.get("board")
            if not board or not isinstance(board, list):
                raise ValueError("Invalid or missing 'board'")
            self.current_board = [list(row) for row in board]
            self._ensure_locked_mask()
            if isinstance(data.get("tile_rules"), dict):
                self.tile_rules = {str(k): str(v) for k, v in data["tile_rules"].items()}
            if isinstance(data.get("tile_metadata"), dict):
                for sym, meta in data["tile_metadata"].items():
                    if isinstance(meta, dict) and len(str(sym)) == 1:
                        set_tile_metadata(str(sym), category=meta.get("category"), difficulty=meta.get("difficulty"), deck_id=meta.get("deck_id"))
            self.board_text = board_to_string(self.current_board)
            self._draw_board(self.current_board)
            self.refresh_legend()
            self._update_status_from_board()
            messagebox.showinfo("Loaded", f"Game loaded from:\n{path}")
        except Exception as e:
            messagebox.showerror("Load failed", str(e))

    def _copy_board(self) -> None:
        if not self.board_text.strip():
            messagebox.showwarning("Nothing to copy", "Generate a board first.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.board_text)
        self.status_label.configure(text="Board copied to clipboard")
        self.root.after(2000, self._update_status_from_board)

    def _validate_paths(self) -> None:
        if not self.current_board:
            messagebox.showwarning("No board", "Generate or load a board first.")
            return
        all_ok, unreachable = check_pathability(self.current_board)
        label, details = compute_route_quality(self.current_board)
        msg = f"\nRoute: {label} — {details}"
        if all_ok:
            messagebox.showinfo("Pathability", "All start positions can reach the goal." + msg)
        else:
            unreachable_str = ", ".join(str(i + 1) for i in unreachable)
            messagebox.showwarning("Pathability", f"Start(s) {unreachable_str} cannot reach the goal." + msg)

    # ---------- Dialogs ----------
    def _open_tile_metadata_editor(self) -> None:
        pad, fs = 12, THEME.get("font_secondary", 10)
        if self._ctk and ctk is not None:
            win = ctk.CTkToplevel(self.root)
            win.title("Tile metadata")
            win.configure(fg_color=THEME["bg_panel"])
            win.minsize(520, 360)
            win.geometry("540x380")
            f = ctk.CTkFrame(win, fg_color=THEME["bg_panel"], corner_radius=0)
            f.pack(fill="both", expand=True, padx=pad, pady=pad)
            ctk.CTkLabel(f, text="Symbol", font=ctk.CTkFont(size=fs, weight="bold"), text_color=THEME["fg_primary"], width=80).grid(row=0, column=0, padx=4, pady=4)
            ctk.CTkLabel(f, text="Category", font=ctk.CTkFont(size=fs, weight="bold"), text_color=THEME["fg_primary"], width=100).grid(row=0, column=1, padx=4, pady=4)
            ctk.CTkLabel(f, text="Difficulty", font=ctk.CTkFont(size=fs, weight="bold"), text_color=THEME["fg_primary"], width=80).grid(row=0, column=2, padx=4, pady=4)
            ctk.CTkLabel(f, text="Deck", font=ctk.CTkFont(size=fs, weight="bold"), text_color=THEME["fg_primary"], width=120).grid(row=0, column=3, padx=4, pady=4)
            entries = {}
            for i, sym in enumerate(sorted(TILE_COLORS.keys())):
                meta = get_tile_metadata(sym)
                ctk.CTkLabel(f, text=sym, font=ctk.CTkFont(size=10), text_color=THEME["fg_primary"]).grid(row=i + 1, column=0, padx=4, pady=4)
                cat_var = tk.StringVar(value=meta["category"])
                ctk.CTkOptionMenu(f, variable=cat_var, values=["terrain", "hazard", "special"], fg_color=THEME["border"], button_color=THEME["accent"], width=100).grid(row=i + 1, column=1, padx=4, pady=4)
                diff_var = tk.StringVar(value=str(meta["difficulty"]))
                ctk.CTkEntry(f, textvariable=diff_var, width=50, fg_color=THEME["border"]).grid(row=i + 1, column=2, padx=4, pady=4)
                deck_var = tk.StringVar(value=meta["deck_id"])
                ctk.CTkEntry(f, textvariable=deck_var, width=140, fg_color=THEME["border"]).grid(row=i + 1, column=3, padx=4, pady=4)
                entries[sym] = (cat_var, diff_var, deck_var)
            def save_and_close() -> None:
                for sym, (cv, dv, dkv) in entries.items():
                    try:
                        diff = max(0, min(3, int(dv.get())))
                    except ValueError:
                        diff = 0
                    set_tile_metadata(sym, category=cv.get(), difficulty=diff, deck_id=dkv.get().strip() or "Default")
                win.destroy()
            ctk.CTkButton(f, text="Save and close", command=save_and_close, fg_color=THEME["accent"], hover_color=THEME["accent_hover"], corner_radius=THEME.get("panel_radius", 8)).grid(row=len(entries) + 1, column=0, columnspan=4, pady=16)
        else:
            win = tk.Toplevel(self.root)
            win.title("Tile metadata")
            win.configure(bg=THEME["bg_panel"])
            win.minsize(520, 360)
            f = tk.Frame(win, bg=THEME["bg_panel"], padx=10, pady=10)
            f.pack(fill="both", expand=True)
            tk.Label(f, text="Symbol", bg=THEME["bg_panel"], fg=THEME["fg_primary"], font=("Segoe UI", 9, "bold"), width=8).grid(row=0, column=0, padx=2, pady=2)
            tk.Label(f, text="Category", bg=THEME["bg_panel"], fg=THEME["fg_primary"], font=("Segoe UI", 9, "bold"), width=10).grid(row=0, column=1, padx=2, pady=2)
            tk.Label(f, text="Difficulty", bg=THEME["bg_panel"], fg=THEME["fg_primary"], font=("Segoe UI", 9, "bold"), width=8).grid(row=0, column=2, padx=2, pady=2)
            tk.Label(f, text="Deck", bg=THEME["bg_panel"], fg=THEME["fg_primary"], font=("Segoe UI", 9, "bold"), width=12).grid(row=0, column=3, padx=2, pady=2)
            entries = {}
            for i, sym in enumerate(sorted(TILE_COLORS.keys())):
                meta = get_tile_metadata(sym)
                tk.Label(f, text=sym, bg=THEME["bg_panel"], fg=THEME["fg_primary"], font=("Consolas", 10)).grid(row=i + 1, column=0, padx=2, pady=2)
                cat_var = tk.StringVar(value=meta["category"])
                tk.OptionMenu(f, cat_var, "terrain", "hazard", "special").grid(row=i + 1, column=1, padx=2, pady=2)
                diff_var = tk.StringVar(value=str(meta["difficulty"]))
                tk.Spinbox(f, from_=0, to=3, width=4, textvariable=diff_var, bg=THEME["border"], fg=THEME["fg_primary"]).grid(row=i + 1, column=2, padx=2, pady=2)
                deck_var = tk.StringVar(value=meta["deck_id"])
                tk.Entry(f, textvariable=deck_var, width=14, bg=THEME["border"], fg=THEME["fg_primary"]).grid(row=i + 1, column=3, padx=2, pady=2)
                entries[sym] = (cat_var, diff_var, deck_var)

            def save_and_close() -> None:
                for sym, (cv, dv, dkv) in entries.items():
                    try:
                        diff = max(0, min(3, int(dv.get())))
                    except ValueError:
                        diff = 0
                    set_tile_metadata(sym, category=cv.get(), difficulty=diff, deck_id=dkv.get().strip() or "Default")
                win.destroy()

            tk.Button(f, text="Save and close", command=save_and_close, bg=THEME["accent"], fg=THEME["fg_primary"], relief="flat", padx=12, pady=4).grid(row=len(entries) + 1, column=0, columnspan=4, pady=12)
        win.transient(self.root)
        win.grab_set()

    def export_image(self) -> None:
        if not self.current_board:
            messagebox.showwarning("Nothing to export", "Generate a board first.")
            return
        path = filedialog.asksaveasfilename(title="Export image", defaultextension=".png", filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("All files", "*.*")], initialfile="generated_board.png")
        if not path:
            return
        if Image is not None and ImageDraw is not None:
            board_copy = [row[:] for row in self.current_board]
            tile_size = self.tile_size
            rules = dict(getattr(self, "tile_rules", TILE_RULES))
            self.status_label.configure(text="Exporting…")

            def worker() -> None:
                _export_board_image_to_path(path, board_copy, tile_size, rules)

            def on_done(_: Any) -> None:
                self._update_status_from_board()
                messagebox.showinfo("Export complete", f"Image saved to:\n{path}")

            def on_error(e: Exception) -> None:
                self._update_status_from_board()
                messagebox.showerror("Export failed", str(e))

            self._run_async(worker, on_done, on_error)
        else:
            _export_png_fallback(path, self.current_board, self.tile_size)
            messagebox.showinfo("Export complete", f"Image saved to:\n{path}")

    def _ask_export_print(self) -> None:
        if not self.current_board:
            messagebox.showwarning("Nothing to export", "Generate a board first.")
            return
        if Image is None:
            messagebox.showerror("Export", "PIL (Pillow) required for print export. pip install Pillow")
            return
        choice = tk.StringVar(value="tiled_a4")

        def do_export() -> None:
            c = choice.get()
            if c == "poster":
                path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")], initialfile="board_poster.png")
                if path:
                    _export_print_poster(path, self.current_board)
                    messagebox.showinfo("Export", f"Poster saved to:\n{path}")
            else:
                path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")], initialfile="board_tiled")
                if path:
                    n = _export_print_tiled(path, self.current_board, paper="A4" if c == "tiled_a4" else "Letter")
                    messagebox.showinfo("Export", f"Saved {n} page(s).")
            win.destroy()

        if self._ctk and ctk is not None:
            win = ctk.CTkToplevel(self.root)
            win.title("Export for print")
            win.configure(fg_color=THEME["bg_panel"])
            win.geometry("360x180")
            f = ctk.CTkFrame(win, fg_color=THEME["bg_panel"], corner_radius=0)
            f.pack(fill="both", expand=True, padx=12, pady=12)
            ctk.CTkRadioButton(f, text="Tiled pages (A4)", variable=choice, value="tiled_a4", fg_color=THEME["accent"], text_color=THEME["fg_primary"]).pack(anchor="w")
            ctk.CTkRadioButton(f, text="Tiled pages (Letter)", variable=choice, value="tiled_letter", fg_color=THEME["accent"], text_color=THEME["fg_primary"]).pack(anchor="w")
            ctk.CTkRadioButton(f, text="Poster (single image)", variable=choice, value="poster", fg_color=THEME["accent"], text_color=THEME["fg_primary"]).pack(anchor="w")
            ctk.CTkButton(f, text="Export", command=do_export, fg_color=THEME["accent"], hover_color=THEME["accent_hover"], corner_radius=THEME.get("panel_radius", 8)).pack(pady=12)
        else:
            win = tk.Toplevel(self.root)
            win.title("Export for print")
            win.configure(bg=THEME["bg_panel"])
            win.geometry("360x160")
            f = tk.Frame(win, bg=THEME["bg_panel"], padx=12, pady=12)
            f.pack(fill="both", expand=True)
            tk.Radiobutton(f, text="Tiled pages (A4)", variable=choice, value="tiled_a4", bg=THEME["bg_panel"], fg=THEME["fg_primary"], selectcolor=THEME["border"]).pack(anchor="w")
            tk.Radiobutton(f, text="Tiled pages (Letter)", variable=choice, value="tiled_letter", bg=THEME["bg_panel"], fg=THEME["fg_primary"], selectcolor=THEME["border"]).pack(anchor="w")
            tk.Radiobutton(f, text="Poster (single image)", variable=choice, value="poster", bg=THEME["bg_panel"], fg=THEME["fg_primary"], selectcolor=THEME["border"]).pack(anchor="w")
            tk.Button(f, text="Export", command=do_export, bg=THEME["accent"], fg=THEME["fg_primary"], relief="flat", padx=12, pady=4).pack(pady=8)
        win.transient(self.root)

    def _export_cards_dialog(self) -> None:
        if not self.current_board:
            messagebox.showwarning("Nothing to export", "Generate a board first.")
            return
        if Image is None or ImageDraw is None:
            messagebox.showerror("Export", "PIL (Pillow) required. pip install Pillow")
            return
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")], initialfile="cards_sheet.png")
        if path:
            _export_cards_image(path)
            messagebox.showinfo("Export", f"Card sheet saved to:\n{path}")

    def _lock_selection(self) -> None:
        if not self.selection_rect or not self.current_board:
            messagebox.showwarning("No selection", "Use Select mode and drag on the board to select a region, then Lock.")
            return
        self._ensure_locked_mask()
        x0, y0, x1, y1 = self.selection_rect
        h, w = len(self.locked_mask), len(self.locked_mask[0]) if self.locked_mask else 0
        for y in range(max(0, y0), min(h, y1 + 1)):
            for x in range(max(0, x0), min(w, x1 + 1)):
                self.locked_mask[y][x] = True
        messagebox.showinfo("Locked", "Selection locked. These cells will be preserved when you regenerate.")

    def _unlock_selection(self) -> None:
        if not self.selection_rect or not self.current_board:
            messagebox.showwarning("No selection", "Use Select mode and drag to select a region, then Unlock.")
            return
        self._ensure_locked_mask()
        x0, y0, x1, y1 = self.selection_rect
        h, w = len(self.locked_mask), len(self.locked_mask[0]) if self.locked_mask else 0
        for y in range(max(0, y0), min(h, y1 + 1)):
            for x in range(max(0, x0), min(w, x1 + 1)):
                self.locked_mask[y][x] = False
        messagebox.showinfo("Unlocked", "Selection unlocked.")

    def _regen_selection(self) -> None:
        if not self.current_board:
            messagebox.showwarning("No board", "Generate a board first.")
            return
        if not self.selection_rect:
            messagebox.showwarning("No selection", "Use Select mode and drag to select a region, then Regen selection.")
            return
        self.generate(regenerate_selection_only=True)

    def _run_simulator(self) -> None:
        if not self.current_board:
            messagebox.showwarning("No board", "Generate a board first.")
            return
        board_copy = [row[:] for row in self.current_board]
        self.status_label.configure(text="Simulating…")

        def worker() -> dict[str, Any]:
            return run_monte_carlo(board_copy, num_games=500, seed=42, max_roll=6)

        def on_done(result: dict[str, Any]) -> None:
            self._update_status_from_board()
            if self._ctk and ctk is not None:
                win = ctk.CTkToplevel(self.root)
                win.title("Simulation results")
                win.configure(fg_color=THEME["bg_panel"])
                win.minsize(380, 280)
                win.geometry("400x320")
                f = ctk.CTkFrame(win, fg_color=THEME["bg_panel"], corner_radius=0)
                f.pack(fill="both", expand=True, padx=12, pady=12)
                ctk.CTkLabel(f, text=f"Expected turns to finish: {result['expected_turns']:.1f}", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["fg_primary"]).pack(anchor="w")
                per_start = result.get("turns_per_start", [])
                if per_start:
                    ctk.CTkLabel(f, text="Per start: " + ", ".join(f"{t:.1f}" for t in per_start), font=ctk.CTkFont(size=10), text_color=THEME["fg_secondary"]).pack(anchor="w", pady=(4, 0))
                spikes = result.get("penalty_spikes", [])
                if spikes:
                    ctk.CTkLabel(f, text=f"Penalty spike tiles: {len(spikes)}", font=ctk.CTkFont(size=10), text_color=THEME["fg_primary"]).pack(anchor="w", pady=(8, 0))
                    preview = ", ".join(f"({x},{y})" for (x, y) in spikes[:8])
                    if len(spikes) > 8:
                        preview += " ..."
                    ctk.CTkLabel(f, text=preview, font=ctk.CTkFont(size=9), text_color=THEME["fg_secondary"], wraplength=340).pack(anchor="w")
                heatmap = result.get("heatmap", {})
                if heatmap:
                    top = sorted(heatmap.items(), key=lambda p: -p[1])[:5]
                    ctk.CTkLabel(f, text="Most visited: " + ", ".join(f"({x},{y}):{c}" for ((x, y), c) in top), font=ctk.CTkFont(size=9), text_color=THEME["fg_secondary"], wraplength=340).pack(anchor="w", pady=(4, 0))
                ctk.CTkButton(f, text="Close", command=win.destroy, fg_color=THEME["accent"], hover_color=THEME["accent_hover"], corner_radius=THEME.get("panel_radius", 8)).pack(pady=12)
            else:
                win = tk.Toplevel(self.root)
                win.title("Simulation results")
                win.configure(bg=THEME["bg_panel"])
                win.minsize(380, 280)
                f = tk.Frame(win, bg=THEME["bg_panel"], padx=12, pady=12)
                f.pack(fill="both", expand=True)
                tk.Label(f, text=f"Expected turns to finish: {result['expected_turns']:.1f}", bg=THEME["bg_panel"], fg=THEME["fg_primary"], font=("Segoe UI", 11, "bold")).pack(anchor="w")
                per_start = result.get("turns_per_start", [])
                if per_start:
                    tk.Label(f, text="Per start: " + ", ".join(f"{t:.1f}" for t in per_start), bg=THEME["bg_panel"], fg=THEME["fg_secondary"], font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))
                spikes = result.get("penalty_spikes", [])
                if spikes:
                    tk.Label(f, text=f"Penalty spike tiles: {len(spikes)}", bg=THEME["bg_panel"], fg=THEME["fg_primary"], font=("Segoe UI", 9)).pack(anchor="w", pady=(8, 0))
                    preview = ", ".join(f"({x},{y})" for (x, y) in spikes[:8])
                    if len(spikes) > 8:
                        preview += " ..."
                    tk.Label(f, text=preview, bg=THEME["bg_panel"], fg=THEME["fg_secondary"], font=("Segoe UI", 8), wraplength=340).pack(anchor="w")
                heatmap = result.get("heatmap", {})
                if heatmap:
                    top = sorted(heatmap.items(), key=lambda p: -p[1])[:5]
                    tk.Label(f, text="Most visited: " + ", ".join(f"({x},{y}):{c}" for ((x, y), c) in top), bg=THEME["bg_panel"], fg=THEME["fg_secondary"], font=("Segoe UI", 8), wraplength=340).pack(anchor="w", pady=(4, 0))
                tk.Button(f, text="Close", command=win.destroy, bg=THEME["accent"], fg=THEME["fg_primary"], relief="flat", padx=12, pady=4).pack(pady=12)

        def on_error(e: Exception) -> None:
            self._update_status_from_board()
            messagebox.showerror("Simulation failed", str(e))

        self._run_async(worker, on_done, on_error)


def run_app() -> None:
    if ctk is None:
        print("For the modern UI, install customtkinter: pip install -r requirements.txt")
        root = tk.Tk()
        BoardGeneratorApp(root, use_ctk=False)
    else:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        root = ctk.CTk()
        BoardGeneratorApp(root, use_ctk=True)
    root.mainloop()
