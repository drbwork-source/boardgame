"""
Board Generator Studio — entry point.

- Run with no arguments to open the desktop app (board-centred modern UI).
- Use --cli for terminal mode instead of the app.
- Import BoardOptions, generate_board, board_to_string, etc. for programmatic use.
"""

from __future__ import annotations

import argparse
import binascii
from collections import deque
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
    "S": "Start",
    "E": "End",
    "C": "Checkpoint",
}

TILE_COLORS.update({"S": "#22C55E", "E": "#F43F5E", "C": "#FBBF24"})
TILE_STYLES.update(
    {
        "S": {"fg": "#052E16", "bg": "#86EFAC", "glyph": "S"},
        "E": {"fg": "#4C0519", "bg": "#FDA4AF", "glyph": "E"},
        "C": {"fg": "#78350F", "bg": "#FDE68A", "glyph": "◆"},
    }
)


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
    auto_place_start_end: bool = False
    start_end_min_distance: int = 20
    safe_segment_length: int = 0
    checkpoint_interval: int = 0

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
        if self.start_end_min_distance < 0:
            raise ValueError("start_end_min_distance cannot be negative")
        if self.safe_segment_length < 0:
            raise ValueError("safe_segment_length cannot be negative")
        if self.checkpoint_interval < 0:
            raise ValueError("checkpoint_interval cannot be negative")


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
    if options.auto_place_start_end:
        _apply_progression_features(board, options, rng)
    return board


def _manhattan(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _find_start_end_positions(width: int, height: int, min_distance: int) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    corners = [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]
    valid_pairs: List[Tuple[Tuple[int, int], Tuple[int, int]]] = []
    for i, start in enumerate(corners):
        for end in corners[i + 1 :]:
            if _manhattan(start, end) >= min_distance:
                valid_pairs.append((start, end))
    if valid_pairs:
        return max(valid_pairs, key=lambda pair: _manhattan(pair[0], pair[1]))
    return (0, 0), (width - 1, height - 1)


def _build_path(start: Tuple[int, int], end: Tuple[int, int]) -> List[Tuple[int, int]]:
    sx, sy = start
    ex, ey = end
    path: List[Tuple[int, int]] = [(sx, sy)]
    x, y = sx, sy

    while x != ex:
        x += 1 if ex > x else -1
        path.append((x, y))
    while y != ey:
        y += 1 if ey > y else -1
        path.append((x, y))

    return path


def _apply_progression_features(board: Board, options: BoardOptions, rng: random.Random) -> None:
    height = len(board)
    width = len(board[0]) if height else 0
    if width == 0 or height == 0:
        return

    start, end = _find_start_end_positions(width, height, options.start_end_min_distance)
    base_path = _build_path(start, end)

    if rng.random() < 0.5:
        base_path.reverse()
        start, end = end, start

    safe_budget = options.safe_segment_length
    for idx, (x, y) in enumerate(base_path):
        if idx < safe_budget or idx >= len(base_path) - safe_budget:
            board[y][x] = "."

    if options.checkpoint_interval > 0:
        for idx in range(options.checkpoint_interval, len(base_path) - 1, options.checkpoint_interval):
            cx, cy = base_path[idx]
            board[cy][cx] = "C"

    sx, sy = start
    ex, ey = end
    board[sy][sx] = "S"
    board[ey][ex] = "E"


def validate_progression_path(board: Board) -> Tuple[bool, str]:
    height = len(board)
    width = len(board[0]) if height else 0
    starts = [(x, y) for y in range(height) for x in range(width) if board[y][x] == "S"]
    ends = [(x, y) for y in range(height) for x in range(width) if board[y][x] == "E"]

    if len(starts) != 1 or len(ends) != 1:
        return False, "Board must contain exactly one start tile (S) and one end tile (E)."

    start = starts[0]
    target = ends[0]
    seen = {start}
    queue = deque([(start, 0)])

    while queue:
        (x, y), dist = queue.popleft()
        if (x, y) == target:
            return True, f"Valid path found: start-to-end route length is {dist} steps."

        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in seen:
                seen.add((nx, ny))
                queue.append(((nx, ny), dist + 1))

    return False, "No valid route from start (S) to end (E)."


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

from board_core import (
    BOARD_PRESETS,
    BOARD_SIZE_MAX,
    BOARD_SIZE_MIN,
    BoardOptions,
    GENERATION_MODE_CHOICES,
    TILE_COLORS,
    TILE_NAMES,
    TILE_RULES,
    TILESET_PRESETS,
    board_to_display_string,
    board_to_string,
    check_pathability,
    compute_route_quality,
    default_weights_string,
    generate_board,
    parse_weights,
)


def run_cli(args: argparse.Namespace) -> None:
    """Generate a board from CLI args, print it (and optionally save), then exit with 1 if pathability fails."""
    if not (BOARD_SIZE_MIN <= args.width <= BOARD_SIZE_MAX):
        print(f"Error: width must be between {BOARD_SIZE_MIN} and {BOARD_SIZE_MAX}.", file=sys.stderr)
        sys.exit(1)
    if not (BOARD_SIZE_MIN <= args.height <= BOARD_SIZE_MAX):
        print(f"Error: height must be between {BOARD_SIZE_MIN} and {BOARD_SIZE_MAX}.", file=sys.stderr)
        sys.exit(1)
    if args.tileset is not None and args.tileset not in TILESET_PRESETS:
        print(f"Error: unknown tileset '{args.tileset}'. Choose from: {', '.join(TILESET_PRESETS.keys())}.", file=sys.stderr)
        sys.exit(1)
    terrain_weights = TILESET_PRESETS[args.tileset] if args.tileset else args.weights
    options = BoardOptions(
        width=args.width,
        height=args.height,
        seed=args.seed,
        terrain_weights=terrain_weights,
        symmetry=args.symmetry,
        smoothing_passes=args.smoothing,
        cluster_bias=args.cluster_bias,
        generation_mode=args.generation_mode,
        num_starts=args.num_starts,
        goal_placement=args.goal_placement,
        start_placement=args.start_placement,
        min_goal_distance=args.min_goal_distance,
        safe_segment_radius=args.safe_segment_radius,
        num_checkpoints=args.num_checkpoints,
    )
    board = generate_board(options)
    board_text = board_to_string(board)
    print(board_text)
    if args.auto_start_end:
        valid, summary = validate_progression_path(board)
        prefix = "[Path OK]" if valid else "[Path INVALID]"
        print(f"\n{prefix} {summary}")
    if args.output:
        Path(args.output).write_text(board_text, encoding="utf-8")
        print(f"\nSaved board to: {args.output}")
    ok, unreachable = check_pathability(board)
    if not ok:
        if not args.quiet:
            print(f"Warning: start(s) {[i+1 for i in unreachable]} cannot reach goal.", file=sys.stderr)
        sys.exit(1)
    if not args.quiet:
        label, details = compute_route_quality(board)
        print(f"Route quality: {label} — {details}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for CLI mode."""
    parser = argparse.ArgumentParser(description="Generate randomized board-game grids")
    parser.add_argument("--cli", action="store_true", help="run in terminal mode instead of the app")
    parser.add_argument("--width", type=int, default=50, help=f"board width ({BOARD_SIZE_MIN}-{BOARD_SIZE_MAX})")
    parser.add_argument("--height", type=int, default=50, help=f"board height ({BOARD_SIZE_MIN}-{BOARD_SIZE_MAX})")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--weights",
        type=parse_weights,
        default=parse_weights(default_weights_string()),
        help="terrain weights e.g. .:0.65,F:0.17 (ignored if --tileset is set)",
    )
    parser.add_argument(
        "--tileset",
        type=str,
        default=None,
        metavar="NAME",
        help="use a preset tileset (e.g. Classic, Archipelago, Desert Frontier, Volcanic); overrides --weights",
    )
    parser.add_argument("--symmetry", choices=["none", "horizontal", "vertical", "both"], default="none")
    parser.add_argument("--smoothing", type=int, default=1)
    parser.add_argument("--cluster-bias", type=float, default=0.2)
    parser.add_argument("--generation-mode", choices=list(GENERATION_MODE_CHOICES), default="grid")
    parser.add_argument("--num-starts", type=int, default=4, choices=[1, 2, 3, 4], help="number of start positions")
    parser.add_argument("--goal-placement", choices=["center", "random"], default="center")
    parser.add_argument("--start-placement", choices=["corners", "random"], default="corners")
    parser.add_argument("--min-goal-distance", type=int, default=0)
    parser.add_argument("--safe-segment-radius", type=int, default=0)
    parser.add_argument("--num-checkpoints", type=int, default=0)
    parser.add_argument("--output", type=str, default="")
    parser.add_argument("--quiet", action="store_true", help="only print board; no route/pathability messages; exit 1 if unreachable")
    parser.add_argument("--web", action="store_true", help="start the web API server (open http://localhost:5173 after running 'npm run dev' in web/)")
    return parser


def run_web_server() -> None:
    """Start the FastAPI backend for the web UI."""
    try:
        import uvicorn
    except ImportError:
        print("Install web dependencies: pip install fastapi 'uvicorn[standard]'", file=sys.stderr)
        sys.exit(1)
    print("Starting Board Generator Studio API at http://localhost:8000")
    print("API docs: http://localhost:8000/docs")
    print("Run the frontend with: cd web && npm install && npm run dev")
    print("Then open http://localhost:5173")
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.cli:
        run_cli(args)
    elif args.web:
        run_web_server()
    else:
        from app import run_app
        run_app()


if __name__ == "__main__":
    main()
