"""Interactive 50x50 board generator for desktop use.

- Default behavior (no args): launches a Tkinter app window.
- Optional CLI behavior: use --cli to print one board in terminal.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
import random
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Sequence, Tuple


CellType = str
Board = List[List[CellType]]

TILESET_PRESETS: Dict[str, Dict[CellType, float]] = {
    "Classic": {".": 0.65, "F": 0.17, "M": 0.10, "W": 0.08},
    "Archipelago": {"W": 0.45, ".": 0.30, "B": 0.15, "F": 0.10},
    "Desert Frontier": {"D": 0.45, ".": 0.25, "M": 0.15, "O": 0.15},
    "Volcanic": {"V": 0.35, "A": 0.25, "M": 0.20, "W": 0.20},
}

TILE_COLORS: Dict[CellType, str] = {
    ".": "#9BC53D",  # plains
    "F": "#2E7D32",  # forest
    "M": "#8D99AE",  # mountain
    "W": "#219EBC",  # water
    "B": "#E9C46A",  # beach
    "D": "#E29578",  # desert
    "O": "#F4A261",  # oasis
    "V": "#9D0208",  # volcanic ground
    "A": "#6D6875",  # ashlands
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

        controls = tk.LabelFrame(
            root,
            text="Generation Controls",
            bg="#1C2541",
            fg="#F8F9FA",
            padx=8,
            pady=6,
            font=("Helvetica", 10, "bold"),
        )
        controls.pack(fill="x", padx=12, pady=8)

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

        legend = tk.LabelFrame(
            root,
            text="Tile Legend",
            bg="#1C2541",
            fg="#F8F9FA",
            padx=8,
            pady=8,
            font=("Helvetica", 10, "bold"),
        )
        legend.pack(fill="x", padx=12, pady=(2, 6))
        self.legend_frame = legend

        board_frame = tk.LabelFrame(
            root,
            text="Board Preview",
            bg="#1C2541",
            fg="#F8F9FA",
            padx=8,
            pady=8,
            font=("Helvetica", 10, "bold"),
        )
        board_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

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

        self.refresh_legend()
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
        self.refresh_legend()

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

        for y, row in enumerate(board):
            for x, symbol in enumerate(row):
                style = TILE_STYLES.get(symbol, {"fg": "#111827", "bg": "#F8FAFC", "glyph": symbol})
                color = TILE_COLORS.get(symbol, style["bg"])
                x0 = x * tile
                y0 = y * tile
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

        width = len(board[0]) * tile
        height = len(board) * tile
        self.board_canvas.configure(scrollregion=(0, 0, width, height))

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
