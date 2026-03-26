"""
Board Generator Studio — entry point.

- Run with no arguments to open the desktop app (board-centred modern UI).
- Use --cli for terminal mode instead of the app.
- Import BoardOptions, generate_board, board_to_string, etc. for programmatic use.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from board_core import (
    BOARD_PRESETS,
    BOARD_SIZE_MAX,
    BOARD_SIZE_MIN,
    BoardOptions,
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
