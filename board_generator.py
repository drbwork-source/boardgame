"""Random 50x50 board generator with customizable layout options.

Run this file directly to print a generated board:
    python board_generator.py --seed 42 --symmetry horizontal
"""

from __future__ import annotations

from dataclasses import dataclass, field
import argparse
import random
import sys
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
            ".": 0.65,  # plain
            "F": 0.17,  # forest
            "M": 0.10,  # mountain
            "W": 0.08,  # water
        }
    )
    symmetry: str = "none"  # one of: none, horizontal, vertical, both
    smoothing_passes: int = 0
    cluster_bias: float = 0.0  # 0.0 (none) to 1.0 (strong clustering)

    def validate(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width and height must be positive")

        valid_symmetry = {"none", "horizontal", "vertical", "both"}
        if self.symmetry not in valid_symmetry:
            raise ValueError(f"symmetry must be one of {sorted(valid_symmetry)}")

        if self.smoothing_passes < 0:
            raise ValueError("smoothing_passes cannot be negative")

        if not (0.0 <= self.cluster_bias <= 1.0):
            raise ValueError("cluster_bias must be between 0.0 and 1.0")

        if not self.terrain_weights:
            raise ValueError("terrain_weights cannot be empty")

        total = sum(self.terrain_weights.values())
        if total <= 0:
            raise ValueError("terrain_weights must sum to a positive number")


def weighted_choice(rng: random.Random, weights: Dict[CellType, float]) -> CellType:
    choices = list(weights.keys())
    probs = list(weights.values())
    return rng.choices(choices, weights=probs, k=1)[0]


def neighbors(x: int, y: int, width: int, height: int) -> Sequence[Tuple[int, int]]:
    points = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height:
                points.append((nx, ny))
    return points


def generate_board(options: BoardOptions) -> Board:
    options.validate()
    rng = random.Random(options.seed)

    board: Board = [["" for _ in range(options.width)] for _ in range(options.height)]

    # First pass: fill board from weighted random choices.
    for y in range(options.height):
        for x in range(options.width):
            board[y][x] = weighted_choice(rng, options.terrain_weights)

    # Optional cluster bias: make cells more likely to copy an existing neighbor.
    if options.cluster_bias > 0:
        for y in range(options.height):
            for x in range(options.width):
                if rng.random() < options.cluster_bias:
                    n = neighbors(x, y, options.width, options.height)
                    if n:
                        nx, ny = rng.choice(list(n))
                        board[y][x] = board[ny][nx]

    # Optional smoothing: replace each cell with local majority terrain.
    for _ in range(options.smoothing_passes):
        next_board = [row[:] for row in board]
        for y in range(options.height):
            for x in range(options.width):
                counts: Dict[CellType, int] = {}
                for nx, ny in neighbors(x, y, options.width, options.height):
                    t = board[ny][nx]
                    counts[t] = counts.get(t, 0) + 1
                if counts:
                    next_board[y][x] = max(counts, key=counts.get)
        board = next_board

    apply_symmetry(board, options.symmetry)
    return board


def apply_symmetry(board: Board, symmetry: str) -> None:
    height = len(board)
    width = len(board[0]) if height else 0

    if symmetry in {"horizontal", "both"}:
        for y in range(height):
            for x in range(width // 2):
                board[y][width - 1 - x] = board[y][x]

    if symmetry in {"vertical", "both"}:
        for y in range(height // 2):
            for x in range(width):
                board[height - 1 - y][x] = board[y][x]


def board_to_string(board: Board) -> str:
    return "\n".join(" ".join(row) for row in board)


def parse_weights(text: str) -> Dict[CellType, float]:
    weights: Dict[CellType, float] = {}
    for part in text.split(","):
        symbol, raw_weight = part.split(":", maxsplit=1)
        weights[symbol] = float(raw_weight)
    return weights


def should_pause_on_exit(argv: Sequence[str]) -> bool:
    """Pause when launched by double-click so the window does not close instantly."""
    return len(argv) == 1 and sys.stdin.isatty() and sys.stdout.isatty()


def maybe_pause_on_exit(should_pause: bool) -> None:
    if should_pause:
        input("\nPress Enter to close...")


def main() -> None:
    pause_on_exit = should_pause_on_exit(sys.argv)

    parser = argparse.ArgumentParser(description="Generate a randomized board-game grid")
    parser.add_argument("--width", type=int, default=50)
    parser.add_argument("--height", type=int, default=50)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--weights",
        type=parse_weights,
        default=parse_weights(".:0.65,F:0.17,M:0.10,W:0.08"),
        help="terrain weights as comma-separated symbol:weight pairs, e.g. .:0.6,F:0.2,M:0.1,W:0.1",
    )
    parser.add_argument(
        "--symmetry",
        choices=["none", "horizontal", "vertical", "both"],
        default="none",
    )
    parser.add_argument("--smoothing", type=int, default=1)
    parser.add_argument("--cluster-bias", type=float, default=0.2)
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="optional file path to save the generated board text",
    )

    args = parser.parse_args()

    options = BoardOptions(
        width=args.width,
        height=args.height,
        seed=args.seed,
        terrain_weights=args.weights,
        symmetry=args.symmetry,
        smoothing_passes=args.smoothing,
        cluster_bias=args.cluster_bias,
    )

    board = generate_board(options)
    board_text = board_to_string(board)
    print(board_text)

    output_path = args.output
    if pause_on_exit and not output_path:
        output_path = "generated_board.txt"

    if output_path:
        with open(output_path, "w", encoding="utf-8") as output_file:
            output_file.write(board_text)
        print(f"\nSaved board to: {output_path}")

    maybe_pause_on_exit(pause_on_exit)


if __name__ == "__main__":
    main()
