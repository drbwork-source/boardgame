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
from tkinter import filedialog, messagebox
from typing import Dict, List, Sequence, Tuple


CellType = str
Board = List[List[CellType]]


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


def parse_weights(text: str) -> Dict[CellType, float]:
    weights: Dict[CellType, float] = {}
    for part in text.split(","):
        symbol, raw_weight = part.split(":", maxsplit=1)
        weights[symbol.strip()] = float(raw_weight)
    return weights


class BoardGeneratorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Board Generator (50x50)")
        self.board_text = ""

        controls = tk.Frame(root)
        controls.pack(fill="x", padx=10, pady=8)

        self.width_var = tk.StringVar(value="50")
        self.height_var = tk.StringVar(value="50")
        self.seed_var = tk.StringVar(value="")
        self.weights_var = tk.StringVar(value=".:0.65,F:0.17,M:0.10,W:0.08")
        self.symmetry_var = tk.StringVar(value="none")
        self.smoothing_var = tk.StringVar(value="1")
        self.cluster_var = tk.StringVar(value="0.2")

        self._labeled_entry(controls, "Width", self.width_var, 0)
        self._labeled_entry(controls, "Height", self.height_var, 1)
        self._labeled_entry(controls, "Seed (optional)", self.seed_var, 2)
        self._labeled_entry(controls, "Weights", self.weights_var, 3, width=34)
        self._labeled_entry(controls, "Smoothing", self.smoothing_var, 4)
        self._labeled_entry(controls, "Cluster Bias", self.cluster_var, 5)

        tk.Label(controls, text="Symmetry").grid(row=0, column=6, padx=(12, 4), pady=2, sticky="w")
        tk.OptionMenu(controls, self.symmetry_var, "none", "horizontal", "vertical", "both").grid(
            row=0, column=7, padx=4, pady=2, sticky="w"
        )

        tk.Button(controls, text="Generate Board", command=self.generate).grid(
            row=1, column=6, columnspan=2, sticky="ew", padx=4, pady=2
        )
        tk.Button(controls, text="Save Board...", command=self.save_board).grid(
            row=2, column=6, columnspan=2, sticky="ew", padx=4, pady=2
        )

        self.output = tk.Text(root, wrap="none", width=120, height=40)
        self.output.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.generate()

    def _labeled_entry(self, parent: tk.Widget, label: str, var: tk.StringVar, col: int, width: int = 10) -> None:
        tk.Label(parent, text=label).grid(row=0, column=col, padx=4, pady=2, sticky="w")
        tk.Entry(parent, textvariable=var, width=width).grid(row=1, column=col, padx=4, pady=2, sticky="w")

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
            self.board_text = board_to_string(board)
            self.output.delete("1.0", tk.END)
            self.output.insert("1.0", self.board_text)
        except Exception as exc:
            messagebox.showerror("Invalid options", str(exc))

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
