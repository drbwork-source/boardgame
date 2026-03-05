"""Interactive 50x50 board generator for desktop use.

- Default behavior (no args): launches a Tkinter app window.
- Optional CLI behavior: use --cli to print one board in terminal.
"""

from __future__ import annotations

import argparse
import binascii
from dataclasses import dataclass, field
from pathlib import Path
import random
import struct
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Sequence, Tuple
import importlib.util
import zlib

if importlib.util.find_spec("PIL") is not None:
    from PIL import Image, ImageDraw, ImageFont
else:  # Optional dependency for image export.
    Image = None
    ImageDraw = None
    ImageFont = None


CellType = str
Board = List[List[CellType]]

TILESET_PRESETS: Dict[str, Dict[CellType, float]] = {
    "Classic": {".": 0.65, "F": 0.17, "M": 0.10, "W": 0.08},
    "Archipelago": {"W": 0.45, ".": 0.30, "B": 0.15, "F": 0.10},
    "Desert Frontier": {"D": 0.45, ".": 0.25, "M": 0.15, "O": 0.15},
    "Volcanic": {"V": 0.35, "A": 0.25, "M": 0.20, "W": 0.20},
}

TILE_COLORS: Dict[CellType, str] = {
    ".": "#A7D676",  # plains
    "F": "#4F9D69",  # forest
    "M": "#A0AEC0",  # mountain
    "W": "#4EA8DE",  # water
    "B": "#F4D58D",  # beach
    "D": "#F4A261",  # desert
    "O": "#E9C46A",  # oasis
    "V": "#AE2012",  # volcanic ground
    "A": "#7D8597",  # ashlands
}

TILE_STYLES: Dict[CellType, Dict[str, str]] = {
    ".": {"fg": "#2F5233", "bg": "#CDE7A6", "glyph": "·"},
    "F": {"fg": "#0B3D20", "bg": "#7BC47F", "glyph": "♣"},
    "M": {"fg": "#2F3640", "bg": "#C7D0E0", "glyph": "▲"},
    "W": {"fg": "#0C4A6E", "bg": "#99D5E4", "glyph": "≈"},
    "B": {"fg": "#7A5C1E", "bg": "#F7E5A4", "glyph": "░"},
    "D": {"fg": "#7F3D00", "bg": "#F9C79B", "glyph": "▤"},
    "O": {"fg": "#155E75", "bg": "#FFE6AF", "glyph": "◉"},
    "V": {"fg": "#F8FAFC", "bg": "#7F1D1D", "glyph": "✹"},
    "A": {"fg": "#E5E7EB", "bg": "#4B5563", "glyph": "¤"},
}

TILE_NAMES: Dict[CellType, str] = {
    ".": "Plains",
    "F": "Forest",
    "M": "Mountain",
    "W": "Water",
    "B": "Beach",
    "D": "Desert",
    "O": "Oasis",
    "V": "Volcanic",
    "A": "Ashlands",
}


@dataclass
class BoardOptions:
    width: int = 50
    height: int = 50
    seed: int | None = None
    terrain_weights: Dict[CellType, float] = field(
        default_factory=lambda: {
            ".": 0.65,
            "F": 0.17,
            "M": 0.10,
            "W": 0.08,
        }
    )
    symmetry: str = "none"  # none|horizontal|vertical|both
    smoothing_passes: int = 1
    cluster_bias: float = 0.2

    def validate(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width and height must be positive")
        if self.symmetry not in {"none", "horizontal", "vertical", "both"}:
            raise ValueError("invalid symmetry")
        if self.smoothing_passes < 0:
            raise ValueError("smoothing_passes cannot be negative")
        if not (0.0 <= self.cluster_bias <= 1.0):
            raise ValueError("cluster_bias must be between 0.0 and 1.0")
        if not self.terrain_weights:
            raise ValueError("terrain_weights cannot be empty")
        if sum(self.terrain_weights.values()) <= 0:
            raise ValueError("terrain_weights must sum to a positive number")


def weighted_choice(rng: random.Random, weights: Dict[CellType, float]) -> CellType:
    return rng.choices(list(weights.keys()), weights=list(weights.values()), k=1)[0]


def neighbors(x: int, y: int, width: int, height: int) -> Sequence[Tuple[int, int]]:
    out = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height:
                out.append((nx, ny))
    return out


def apply_symmetry(board: Board, symmetry: str) -> None:
    h = len(board)
    w = len(board[0]) if h else 0

    if symmetry in {"horizontal", "both"}:
        for y in range(h):
            for x in range(w // 2):
                board[y][w - 1 - x] = board[y][x]

    if symmetry in {"vertical", "both"}:
        for y in range(h // 2):
            for x in range(w):
                board[h - 1 - y][x] = board[y][x]


def generate_board(options: BoardOptions) -> Board:
    options.validate()
    rng = random.Random(options.seed)
    board: Board = [["" for _ in range(options.width)] for _ in range(options.height)]

    for y in range(options.height):
        for x in range(options.width):
            board[y][x] = weighted_choice(rng, options.terrain_weights)

    if options.cluster_bias > 0:
        for y in range(options.height):
            for x in range(options.width):
                if rng.random() < options.cluster_bias:
                    n = neighbors(x, y, options.width, options.height)
                    if n:
                        nx, ny = rng.choice(list(n))
                        board[y][x] = board[ny][nx]

    for _ in range(options.smoothing_passes):
        next_board = [row[:] for row in board]
        for y in range(options.height):
            for x in range(options.width):
                counts: Dict[CellType, int] = {}
                for nx, ny in neighbors(x, y, options.width, options.height):
                    terrain = board[ny][nx]
                    counts[terrain] = counts.get(terrain, 0) + 1
                if counts:
                    next_board[y][x] = max(counts, key=counts.get)
        board = next_board

    apply_symmetry(board, options.symmetry)
    return board


def board_to_string(board: Board) -> str:
    return "\n".join(" ".join(row) for row in board)


def board_to_display_string(board: Board) -> str:
    display_rows: List[str] = []
    for row in board:
        glyph_row = [TILE_STYLES.get(symbol, {"glyph": symbol})["glyph"] for symbol in row]
        display_rows.append(" ".join(glyph_row))
    return "\n".join(display_rows)


def parse_weights(text: str) -> Dict[CellType, float]:
    weights: Dict[CellType, float] = {}
    for part in text.split(","):
        item = part.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(f"Invalid weight entry '{item}'. Expected format symbol:value")

        symbol, raw_weight = item.split(":", maxsplit=1)
        symbol = symbol.strip()
        if not symbol:
            raise ValueError("Weight symbol cannot be empty")

        try:
            weight = float(raw_weight)
        except ValueError as exc:
            raise ValueError(f"Invalid numeric weight for '{symbol}': {raw_weight}") from exc
        if weight < 0:
            raise ValueError(f"Weight for '{symbol}' cannot be negative")

        weights[symbol] = weight

    if not weights:
        raise ValueError("At least one terrain weight is required")

    return weights


class BoardGeneratorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Board Generator (50x50)")
        self.root.configure(bg="#0B132B")
        self.board_text = ""
        self.current_board: Board = []
        self.tile_size = 20
        self.mode_var = tk.StringVar(value="viewer")
        self.paint_tile_var = tk.StringVar(value=".")
        self.board_origin_x = 0
        self.board_origin_y = 0

        header = tk.Frame(root, bg="#0B132B")
        header.pack(fill="x", padx=14, pady=(12, 2))
        tk.Label(
            header,
            text="Board Generator Studio",
            font=("Helvetica", 16, "bold"),
            bg="#0B132B",
            fg="#FAF9F6",
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Build colorful procedural maps with tile presets, custom terrain symbols, and export support.",
            font=("Helvetica", 10),
            bg="#0B132B",
            fg="#C8D3F5",
        ).pack(anchor="w", pady=(2, 6))

        app_body = tk.Frame(root, bg="#0B132B")
        app_body.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        sidebar = tk.LabelFrame(
            app_body,
            text="Mode",
            bg="#1C2541",
            fg="#F8F9FA",
            padx=10,
            pady=8,
            font=("Helvetica", 10, "bold"),
        )
        sidebar.pack(side="left", fill="y", padx=(0, 10))

        tk.Label(
            sidebar,
            text="Select how you use the board",
            bg="#1C2541",
            fg="#C8D3F5",
            font=("Helvetica", 9),
        ).pack(anchor="w", pady=(0, 8))

        tk.Radiobutton(
            sidebar,
            text="Viewer Mode",
            variable=self.mode_var,
            value="viewer",
            command=self._update_mode_ui,
            bg="#1C2541",
            fg="#F8F9FA",
            activebackground="#1C2541",
            activeforeground="#F8F9FA",
            selectcolor="#0F172A",
            highlightthickness=0,
        ).pack(anchor="w", pady=2)
        tk.Radiobutton(
            sidebar,
            text="Editor Mode",
            variable=self.mode_var,
            value="editor",
            command=self._update_mode_ui,
            bg="#1C2541",
            fg="#F8F9FA",
            activebackground="#1C2541",
            activeforeground="#F8F9FA",
            selectcolor="#0F172A",
            highlightthickness=0,
        ).pack(anchor="w", pady=2)

        self.editor_hint_label = tk.Label(
            sidebar,
            text="Use editor mode to paint on tiles.",
            bg="#1C2541",
            fg="#C8D3F5",
            font=("Helvetica", 9),
            justify="left",
            wraplength=170,
        )
        self.editor_hint_label.pack(anchor="w", pady=(8, 4))

        tk.Label(sidebar, text="Paint Tile", bg="#1C2541", fg="#F8F9FA").pack(anchor="w", pady=(6, 2))
        self.paint_tile_menu = tk.OptionMenu(sidebar, self.paint_tile_var, *sorted(TILE_COLORS.keys()))
        self.paint_tile_menu.pack(anchor="w", fill="x")

        main_content = tk.Frame(app_body, bg="#0B132B")
        main_content.pack(side="left", fill="both", expand=True)

        controls = tk.LabelFrame(
            main_content,
            text="Generation Controls",
            bg="#1C2541",
            fg="#F8F9FA",
            padx=8,
            pady=6,
            font=("Helvetica", 10, "bold"),
        )
        controls.pack(fill="x", padx=0, pady=(0, 8))

        self.width_var = tk.StringVar(value="50")
        self.height_var = tk.StringVar(value="50")
        self.seed_var = tk.StringVar(value="")
        self.weights_var = tk.StringVar(value=".:0.65,F:0.17,M:0.10,W:0.08")
        self.symmetry_var = tk.StringVar(value="none")
        self.smoothing_var = tk.StringVar(value="1")
        self.cluster_var = tk.StringVar(value="0.2")
        self.tileset_var = tk.StringVar(value="Classic")
        self.custom_tile_var = tk.StringVar(value="")
        self.custom_weight_var = tk.StringVar(value="0.10")

        self._labeled_entry(controls, "Board Width", self.width_var, 0)
        self._labeled_entry(controls, "Board Height", self.height_var, 1)
        self._labeled_entry(controls, "Seed (optional)", self.seed_var, 2)
        self._labeled_entry(controls, "Terrain Weights", self.weights_var, 3, width=34)
        self._labeled_entry(controls, "Smoothing Passes", self.smoothing_var, 4)
        self._labeled_entry(controls, "Cluster Bias (0-1)", self.cluster_var, 5)

        tk.Label(controls, text="Symmetry", bg="#1C2541", fg="#F8F9FA").grid(row=0, column=6, padx=(12, 4), pady=2, sticky="w")
        tk.OptionMenu(controls, self.symmetry_var, "none", "horizontal", "vertical", "both").grid(
            row=0, column=7, padx=4, pady=2, sticky="w"
        )

        tk.Label(controls, text="Tile Theme", bg="#1C2541", fg="#F8F9FA").grid(row=0, column=8, padx=(12, 4), pady=2, sticky="w")
        tk.OptionMenu(controls, self.tileset_var, *TILESET_PRESETS.keys()).grid(
            row=0, column=9, padx=4, pady=2, sticky="w"
        )
        self._styled_button(controls, "Apply Theme", self.apply_tileset).grid(
            row=1, column=8, columnspan=2, sticky="ew", padx=4, pady=2
        )

        tk.Label(controls, text="Add Custom Tile", bg="#1C2541", fg="#F8F9FA").grid(row=2, column=0, padx=4, pady=(8, 2), sticky="w")
        tk.Entry(controls, textvariable=self.custom_tile_var, width=5).grid(row=2, column=1, padx=4, pady=(8, 2), sticky="w")
        tk.Label(controls, text="Weight", bg="#1C2541", fg="#F8F9FA").grid(row=2, column=2, padx=4, pady=(8, 2), sticky="e")
        tk.Entry(controls, textvariable=self.custom_weight_var, width=8).grid(row=2, column=3, padx=4, pady=(8, 2), sticky="w")
        self._styled_button(controls, "Add Tile", self.add_custom_tile).grid(row=2, column=4, padx=4, pady=(8, 2), sticky="w")

        tk.Label(
            controls,
            text="Weights format: Symbol:Weight separated by commas (example: .:0.5,F:0.2,W:0.3)",
            bg="#1C2541",
            fg="#C8D3F5",
            font=("Helvetica", 9),
        ).grid(row=3, column=0, columnspan=10, padx=4, pady=(6, 2), sticky="w")

        self._styled_button(controls, "Generate Board", self.generate).grid(
            row=1, column=6, columnspan=2, sticky="ew", padx=4, pady=2
        )
        self._styled_button(controls, "Save Board...", self.save_board).grid(
            row=2, column=6, columnspan=2, sticky="ew", padx=4, pady=2
        )
        self._styled_button(controls, "Export Image...", self.export_image).grid(
            row=3, column=6, columnspan=2, sticky="ew", padx=4, pady=(2, 6)
        )

        legend = tk.LabelFrame(
            main_content,
            text="Tile Legend",
            bg="#1C2541",
            fg="#F8F9FA",
            padx=8,
            pady=8,
            font=("Helvetica", 10, "bold"),
        )
        legend.pack(fill="x", padx=0, pady=(2, 6))
        self.legend_frame = legend

        board_frame = tk.LabelFrame(
            main_content,
            text="Board Preview",
            bg="#1C2541",
            fg="#F8F9FA",
            padx=8,
            pady=8,
            font=("Helvetica", 10, "bold"),
        )
        board_frame.pack(fill="both", expand=True, padx=0, pady=(0, 0))

        preview_header = tk.Frame(board_frame, bg="#1C2541")
        preview_header.pack(fill="x", pady=(0, 6))
        tk.Label(
            preview_header,
            text="Uniform square tiles with high-contrast borders for clear readability.",
            bg="#1C2541",
            fg="#C8D3F5",
            font=("Helvetica", 9),
        ).pack(side="left")

        self.size_var = tk.IntVar(value=self.tile_size)
        tk.Label(preview_header, text="Tile Size", bg="#1C2541", fg="#F8F9FA").pack(side="right", padx=(8, 4))
        size_scale = tk.Scale(
            preview_header,
            variable=self.size_var,
            from_=12,
            to=32,
            orient="horizontal",
            command=self._on_tile_size_change,
            bg="#1C2541",
            fg="#F8F9FA",
            highlightthickness=0,
            troughcolor="#0F172A",
            activebackground="#3A86FF",
            length=140,
        )
        size_scale.pack(side="right")

        canvas_shell = tk.Frame(board_frame, bg="#0F172A")
        canvas_shell.pack(fill="both", expand=True)

        self.board_canvas = tk.Canvas(
            canvas_shell,
            bg="#0B1020",
            highlightthickness=0,
            relief="flat",
        )
        x_scroll = ttk.Scrollbar(canvas_shell, orient="horizontal", command=self.board_canvas.xview)
        y_scroll = ttk.Scrollbar(canvas_shell, orient="vertical", command=self.board_canvas.yview)
        self.board_canvas.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)

        self.board_canvas.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        canvas_shell.grid_columnconfigure(0, weight=1)
        canvas_shell.grid_rowconfigure(0, weight=1)

        self.board_canvas.bind("<Button-1>", self._paint_tile)
        self.board_canvas.bind("<B1-Motion>", self._paint_tile)
        self.board_canvas.bind("<Configure>", self._on_canvas_resize)

        self.refresh_legend()
        self._update_mode_ui()
        self.generate()

    def _labeled_entry(self, parent: tk.Widget, label: str, var: tk.StringVar, col: int, width: int = 10) -> None:
        tk.Label(parent, text=label, bg="#1C2541", fg="#F8F9FA").grid(row=0, column=col, padx=4, pady=2, sticky="w")
        tk.Entry(parent, textvariable=var, width=width).grid(row=1, column=col, padx=4, pady=2, sticky="w")

    def _styled_button(self, parent: tk.Widget, label: str, command) -> tk.Button:
        return tk.Button(
            parent,
            text=label,
            command=command,
            bg="#3A86FF",
            fg="white",
            activebackground="#2667CC",
            activeforeground="white",
            relief="flat",
            padx=8,
            pady=5,
            cursor="hand2",
            font=("Helvetica", 10, "bold"),
        )

    def apply_tileset(self) -> None:
        chosen = TILESET_PRESETS[self.tileset_var.get()]
        self.weights_var.set(",".join(f"{symbol}:{weight:.2f}" for symbol, weight in chosen.items()))
        self._refresh_editor_tile_options()
        self.refresh_legend()

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
            messagebox.showerror("Invalid weight", "Custom tile weight cannot be negative.")
            return

        weights = parse_weights(self.weights_var.get())
        weights[symbol] = weight
        self.weights_var.set(",".join(f"{tile}:{value:.2f}" for tile, value in weights.items()))
        if symbol not in TILE_COLORS:
            TILE_COLORS[symbol] = "#E2E8F0"
            TILE_NAMES[symbol] = f"Tile '{symbol}'"
            TILE_STYLES[symbol] = {"fg": "#111827", "bg": "#F8FAFC", "glyph": symbol}
        self._refresh_editor_tile_options()
        self.refresh_legend()

    def _refresh_editor_tile_options(self) -> None:
        menu = self.paint_tile_menu["menu"]
        menu.delete(0, "end")
        for symbol in sorted(TILE_COLORS.keys()):
            menu.add_command(label=symbol, command=lambda value=symbol: self.paint_tile_var.set(value))
        if self.paint_tile_var.get() not in TILE_COLORS:
            self.paint_tile_var.set(sorted(TILE_COLORS.keys())[0])

    def _update_mode_ui(self) -> None:
        state = "normal" if self.mode_var.get() == "editor" else "disabled"
        self.paint_tile_menu.configure(state=state)
        if state == "disabled":
            self.editor_hint_label.configure(text="Viewer mode selected. Switch to editor mode to paint tiles.")
        else:
            self.editor_hint_label.configure(text="Editor mode selected. Click or drag on the grid to paint tiles.")

    def refresh_legend(self) -> None:
        for child in self.legend_frame.winfo_children():
            child.destroy()

        tk.Label(
            self.legend_frame,
            text="Visual map key for terrain symbols",
            bg="#1C2541",
            fg="#C8D3F5",
            font=("Helvetica", 9),
        ).pack(anchor="w")

        row = tk.Frame(self.legend_frame, bg="#1C2541")
        row.pack(fill="x", pady=(6, 0))
        for symbol, color in TILE_COLORS.items():
            style = TILE_STYLES.get(symbol, {"fg": "#111827", "glyph": symbol})
            chip = tk.Label(
                row,
                text=f" {style['glyph']} {symbol} {TILE_NAMES.get(symbol, 'Custom')} ",
                bg=color,
                fg=style["fg"],
                padx=5,
                pady=3,
                font=("Helvetica", 9, "bold"),
            )
            chip.pack(side="left", padx=(0, 6), pady=2)

    def _build_options(self) -> BoardOptions:
        seed_text = self.seed_var.get().strip()
        seed = int(seed_text) if seed_text else None
        return BoardOptions(
            width=int(self.width_var.get()),
            height=int(self.height_var.get()),
            seed=seed,
            terrain_weights=parse_weights(self.weights_var.get()),
            symmetry=self.symmetry_var.get(),
            smoothing_passes=int(self.smoothing_var.get()),
            cluster_bias=float(self.cluster_var.get()),
        )

    def generate(self) -> None:
        try:
            options = self._build_options()
            board = generate_board(options)
            self.current_board = board
            self.board_text = board_to_string(board)
            self._refresh_editor_tile_options()
            self._draw_board(board)
            self.refresh_legend()
        except Exception as exc:
            messagebox.showerror("Invalid options", str(exc))

    def _on_tile_size_change(self, _value: str) -> None:
        self.tile_size = self.size_var.get()
        if self.current_board:
            self._draw_board(self.current_board)

    def _draw_board(self, board: Board) -> None:
        self.board_canvas.delete("all")
        if not board:
            self.board_canvas.configure(scrollregion=(0, 0, 0, 0))
            return

        tile = self.tile_size
        border_color = "#0F172A"

        width = len(board[0]) * tile
        height = len(board) * tile
        canvas_w = max(1, self.board_canvas.winfo_width())
        canvas_h = max(1, self.board_canvas.winfo_height())
        self.board_origin_x = max(12, (canvas_w - width) // 2)
        self.board_origin_y = max(12, (canvas_h - height) // 2)

        for y, row in enumerate(board):
            for x, symbol in enumerate(row):
                style = TILE_STYLES.get(symbol, {"fg": "#111827", "bg": "#F8FAFC", "glyph": symbol})
                color = TILE_COLORS.get(symbol, style["bg"])
                x0 = self.board_origin_x + (x * tile)
                y0 = self.board_origin_y + (y * tile)
                x1 = x0 + tile
                y1 = y0 + tile
                self.board_canvas.create_rectangle(
                    x0,
                    y0,
                    x1,
                    y1,
                    fill=color,
                    outline=border_color,
                    width=1,
                )
                self.board_canvas.create_text(
                    x0 + tile / 2,
                    y0 + tile / 2,
                    text=style.get("glyph", symbol),
                    fill=style["fg"],
                    font=("Consolas", max(8, tile // 2), "bold"),
                )

        scroll_w = self.board_origin_x + width + 12
        scroll_h = self.board_origin_y + height + 12
        self.board_canvas.configure(scrollregion=(0, 0, scroll_w, scroll_h))

    def _on_canvas_resize(self, _event: tk.Event) -> None:
        if self.current_board:
            self._draw_board(self.current_board)

    def _paint_tile(self, event: tk.Event) -> None:
        if self.mode_var.get() != "editor" or not self.current_board:
            return

        tile = self.tile_size
        canvas_x = self.board_canvas.canvasx(event.x) - self.board_origin_x
        canvas_y = self.board_canvas.canvasy(event.y) - self.board_origin_y
        x = int(canvas_x // tile)
        y = int(canvas_y // tile)
        if not (0 <= y < len(self.current_board) and 0 <= x < len(self.current_board[0])):
            return

        selected = self.paint_tile_var.get()
        if not selected:
            return
        self.current_board[y][x] = selected
        self.board_text = board_to_string(self.current_board)
        self._draw_board(self.current_board)

    def save_board(self) -> None:
        if not self.board_text.strip():
            messagebox.showwarning("Nothing to save", "Generate a board first.")
            return

        path = filedialog.asksaveasfilename(
            title="Save generated board",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile="generated_board.txt",
        )
        if not path:
            return

        Path(path).write_text(self.board_text, encoding="utf-8")
        messagebox.showinfo("Saved", f"Board saved to:\n{path}")

    def export_image(self) -> None:
        if not self.current_board:
            messagebox.showwarning("Nothing to export", "Generate a board first.")
            return
        pillow_available = Image is not None and ImageDraw is not None
        filetypes = [("PNG image", "*.png")]
        if pillow_available:
            filetypes.append(("JPEG image", "*.jpg;*.jpeg"))
        path = filedialog.asksaveasfilename(
            title="Export board image",
            defaultextension=".png",
            filetypes=filetypes,
            initialfile="generated_board.png",
        )
        if not path:
            return

        if pillow_available:
            self._export_with_pillow(path)
        else:
            self._export_png_without_pillow(path)
        messagebox.showinfo("Export complete", f"Board image exported to:\n{path}")

    def _export_with_pillow(self, path: str) -> None:
        tile = self.tile_size
        width = len(self.current_board[0]) * tile
        height = len(self.current_board) * tile
        image = Image.new("RGB", (width, height), "#0B1020")
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default() if ImageFont is not None else None

        for y, row in enumerate(self.current_board):
            for x, symbol in enumerate(row):
                style = TILE_STYLES.get(symbol, {"fg": "#111827", "glyph": symbol})
                color = TILE_COLORS.get(symbol, "#F8FAFC")
                x0, y0 = x * tile, y * tile
                x1, y1 = x0 + tile, y0 + tile
                draw.rectangle([x0, y0, x1, y1], fill=color, outline="#0F172A", width=1)

                glyph = style.get("glyph", symbol)
                if font is not None:
                    bbox = draw.textbbox((0, 0), glyph, font=font)
                    text_w = bbox[2] - bbox[0]
                    text_h = bbox[3] - bbox[1]
                    tx = x0 + (tile - text_w) / 2
                    ty = y0 + (tile - text_h) / 2
                    draw.text((tx, ty), glyph, fill=style["fg"], font=font)

        image.save(path)

    def _export_png_without_pillow(self, path: str) -> None:
        tile = self.tile_size
        width = len(self.current_board[0]) * tile
        height = len(self.current_board) * tile
        pixels = bytearray(width * height * 3)

        for y, row in enumerate(self.current_board):
            for x, symbol in enumerate(row):
                color = TILE_COLORS.get(symbol, "#F8FAFC")
                r, g, b = self._hex_to_rgb(color)
                for py in range(y * tile, (y + 1) * tile):
                    row_start = py * width * 3
                    for px in range(x * tile, (x + 1) * tile):
                        idx = row_start + px * 3
                        pixels[idx : idx + 3] = bytes((r, g, b))

        self._write_png(path, width, height, bytes(pixels))

    def _hex_to_rgb(self, color: str) -> Tuple[int, int, int]:
        value = color.lstrip("#")
        if len(value) == 3:
            value = "".join(ch * 2 for ch in value)
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)

    def _write_png(self, path: str, width: int, height: int, rgb_data: bytes) -> None:
        scanlines = bytearray()
        stride = width * 3
        for y in range(height):
            scanlines.append(0)
            start = y * stride
            scanlines.extend(rgb_data[start : start + stride])

        def chunk(chunk_type: bytes, data: bytes) -> bytes:
            crc = binascii.crc32(chunk_type)
            crc = binascii.crc32(data, crc) & 0xFFFFFFFF
            return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)

        png = bytearray()
        png.extend(b"\x89PNG\r\n\x1a\n")
        ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        png.extend(chunk(b"IHDR", ihdr))
        png.extend(chunk(b"IDAT", zlib.compress(bytes(scanlines), level=9)))
        png.extend(chunk(b"IEND", b""))
        Path(path).write_bytes(bytes(png))


def run_gui() -> None:
    root = tk.Tk()
    BoardGeneratorApp(root)
    root.mainloop()


def run_cli(args: argparse.Namespace) -> None:
    options = BoardOptions(
        width=args.width,
        height=args.height,
        seed=args.seed,
        terrain_weights=args.weights,
        symmetry=args.symmetry,
        smoothing_passes=args.smoothing,
        cluster_bias=args.cluster_bias,
    )
    board_text = board_to_string(generate_board(options))
    print(board_text)
    if args.output:
        Path(args.output).write_text(board_text, encoding="utf-8")
        print(f"\nSaved board to: {args.output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate randomized board-game grids")
    parser.add_argument("--cli", action="store_true", help="run in terminal mode instead of interactive app")
    parser.add_argument("--width", type=int, default=50)
    parser.add_argument("--height", type=int, default=50)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--weights", type=parse_weights, default=parse_weights(".:0.65,F:0.17,M:0.10,W:0.08"))
    parser.add_argument("--symmetry", choices=["none", "horizontal", "vertical", "both"], default="none")
    parser.add_argument("--smoothing", type=int, default=1)
    parser.add_argument("--cluster-bias", type=float, default=0.2)
    parser.add_argument("--output", type=str, default="")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.cli:
        run_cli(args)
    else:
        run_gui()


if __name__ == "__main__":
    main()
