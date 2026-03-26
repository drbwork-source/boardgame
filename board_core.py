"""
Board generation core: options, procedural generation, pathability, simulation, and tile data.
No UI dependencies. Used by the app, CLI, and programmatic API.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
import random
import re
from typing import Any, Sequence

# ---------------------------------------------------------------------------
# Types and constants
# ---------------------------------------------------------------------------

CellType = str
Board = list[list[CellType]]

BOARD_SIZE_MIN = 5
BOARD_SIZE_MAX = 100
BOARD_PRESETS: list[tuple[int, int]] = [(10, 10), (25, 25), (50, 50), (75, 75)]

GOAL_SYMBOL: CellType = "G"
START_SYMBOLS: list[CellType] = ["1", "2", "3", "4"]
CHECKPOINT_SYMBOL: CellType = "C"
SPECIAL_SYMBOLS: set[CellType] = {GOAL_SYMBOL} | set(START_SYMBOLS) | {CHECKPOINT_SYMBOL}
BLOCKED_TILES: set[CellType] = {"W"}

# ---------------------------------------------------------------------------
# Unified tile definitions (single source of truth)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TileDefinition:
    """Single definition for a tile's visual and rule data."""

    color: str
    fg: str
    bg: str
    glyph: str
    name: str
    rule: str


def _tile(color: str, fg: str, bg: str, glyph: str, name: str, rule: str) -> TileDefinition:
    return TileDefinition(color=color, fg=fg, bg=bg, glyph=glyph, name=name, rule=rule)


# Base terrain tiles (symbol -> TileDefinition)
_TERRAIN_DEFS: dict[CellType, TileDefinition] = {
    ".": _tile("#A7D676", "#2F5233", "#CDE7A6", "·", "Plains", "Safe"),
    "F": _tile("#4F9D69", "#0B3D20", "#7BC47F", "♣", "Forest", "1 sip"),
    "M": _tile("#A0AEC0", "#2F3640", "#C7D0E0", "▲", "Mountain", "2 sips"),
    "W": _tile("#4EA8DE", "#0C4A6E", "#99D5E4", "≈", "Water", "Blocked"),
    "B": _tile("#F4D58D", "#7A5C1E", "#F7E5A4", "░", "Beach", "1 sip"),
    "D": _tile("#F4A261", "#7F3D00", "#F9C79B", "▤", "Desert", "2 sips"),
    "O": _tile("#E9C46A", "#155E75", "#FFE6AF", "◉", "Oasis", "Safe"),
    "V": _tile("#AE2012", "#F8FAFC", "#7F1D1D", "✹", "Volcanic", "3 sips"),
    "A": _tile("#7D8597", "#E5E7EB", "#4B5563", "¤", "Ashlands", "2 sips"),
}

# Build unified registry and derived dicts for backward compatibility
TILE_DEFINITIONS: dict[CellType, TileDefinition] = dict(_TERRAIN_DEFS)

TILE_DEFINITIONS[GOAL_SYMBOL] = _tile("#EAB308", "#1C1917", "#FACC15", "★", "Goal", "Finish")
for i, sym in enumerate(START_SYMBOLS, 1):
    colors = ("#DC2626", "#2563EB", "#16A34A", "#9333EA")
    c = colors[(i - 1) % len(colors)]
    TILE_DEFINITIONS[sym] = _tile(c, "#F8FAFC", c, str(i), f"Start {i}", "Start")
TILE_DEFINITIONS[CHECKPOINT_SYMBOL] = _tile("#F59E0B", "#1C1917", "#FBBF24", "◆", "Checkpoint", "Save progress here")

TILE_COLORS: dict[CellType, str] = {s: t.color for s, t in TILE_DEFINITIONS.items()}
TILE_STYLES: dict[CellType, dict[str, str]] = {
    s: {"fg": t.fg, "bg": t.bg, "glyph": t.glyph} for s, t in TILE_DEFINITIONS.items()
}
TILE_NAMES: dict[CellType, str] = {s: t.name for s, t in TILE_DEFINITIONS.items()}
TILE_RULES: dict[CellType, str] = {s: t.rule for s, t in TILE_DEFINITIONS.items()}

# Single source of default terrain weights (used by BoardOptions, CLI, and app)
DEFAULT_TERRAIN_WEIGHTS: dict[CellType, float] = {".": 0.65, "F": 0.17, "M": 0.10, "W": 0.08}


def default_weights_string() -> str:
    """Return the default terrain weights as a string for CLI/app display."""
    return ",".join(f"{s}:{w:.2f}" for s, w in DEFAULT_TERRAIN_WEIGHTS.items())


# Tileset presets (symbol -> weight)
TILESET_PRESETS: dict[str, dict[CellType, float]] = {
    "Classic": dict(DEFAULT_TERRAIN_WEIGHTS),
    "Archipelago": {"W": 0.45, ".": 0.30, "B": 0.15, "F": 0.10},
    "Desert Frontier": {"D": 0.45, ".": 0.25, "M": 0.15, "O": 0.15},
    "Volcanic": {"V": 0.35, "A": 0.25, "M": 0.20, "W": 0.20},
}

# Tile metadata (category, difficulty, deck_id)
TILE_METADATA: dict[CellType, dict[str, Any]] = {}
_DEFAULT_CATEGORY = "terrain"
_DEFAULT_DECK = "Default"


def _deck_id_from_name(name: str, symbol: CellType) -> str:
    """Normalize tile name to deck id (must match API seed_decks logic)."""
    normalized = re.sub(r"[^a-z0-9_]", "_", (name or "").lower()).strip("_") or f"deck_{symbol}"
    return normalized if normalized else "default"


def _init_tile_metadata() -> None:
    for symbol in TILE_COLORS:
        if symbol not in TILE_METADATA:
            cat = "special" if symbol in SPECIAL_SYMBOLS else _DEFAULT_CATEGORY
            deck_id = "default"
            if symbol in ("F", "M", "W", "B", "D", "O", "V", "A"):
                name = TILE_NAMES.get(symbol, symbol)
                deck_id = _deck_id_from_name(name, symbol)
            TILE_METADATA[symbol] = {"category": cat, "difficulty": 0, "deck_id": deck_id}


def get_tile_metadata(symbol: CellType) -> dict[str, Any]:
    """Return metadata dict for a tile symbol (category, difficulty, deck_id)."""
    if symbol not in TILE_METADATA:
        TILE_METADATA[symbol] = {"category": _DEFAULT_CATEGORY, "difficulty": 0, "deck_id": _DEFAULT_DECK}
    return dict(TILE_METADATA[symbol])


def set_tile_metadata(
    symbol: CellType,
    category: str | None = None,
    difficulty: int | None = None,
    deck_id: str | None = None,
) -> None:
    """Update metadata for a tile symbol."""
    meta = get_tile_metadata(symbol)
    if category is not None:
        meta["category"] = category
    if difficulty is not None:
        meta["difficulty"] = max(0, min(3, difficulty))
    if deck_id is not None:
        meta["deck_id"] = deck_id or _DEFAULT_DECK
    TILE_METADATA[symbol] = meta


_init_tile_metadata()

# ---------------------------------------------------------------------------
# Board options and validation
# ---------------------------------------------------------------------------


@dataclass
class BoardOptions:
    """
    Options for procedural board generation.
    Use with generate_board() for programmatic or CLI use.
    """

    width: int = 50
    height: int = 50
    seed: int | None = None
    terrain_weights: dict[CellType, float] = field(
        default_factory=lambda: dict(DEFAULT_TERRAIN_WEIGHTS)
    )
    symmetry: str = "none"
    smoothing_passes: int = 1
    cluster_bias: float = 0.2
    num_starts: int = 4
    goal_placement: str = "center"
    start_placement: str = "corners"
    min_goal_distance: int = 0
    safe_segment_radius: int = 0
    num_checkpoints: int = 0

    def validate(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width and height must be positive")
        if self.symmetry not in {"none", "horizontal", "vertical", "both"}:
            raise ValueError("invalid symmetry")
        if self.smoothing_passes < 0:
            raise ValueError("smoothing_passes cannot be negative")
        if not (0.0 <= self.cluster_bias <= 1.0):
            raise ValueError("cluster_bias must be between 0.0 and 1.0")
        if not self.terrain_weights or sum(self.terrain_weights.values()) <= 0:
            raise ValueError("terrain_weights must sum to a positive number")
        if not (1 <= self.num_starts <= len(START_SYMBOLS)):
            raise ValueError(f"num_starts must be 1..{len(START_SYMBOLS)}")
        if self.goal_placement not in {"center", "random"}:
            raise ValueError("goal_placement must be 'center' or 'random'")
        if self.start_placement not in {"corners", "random"}:
            raise ValueError("start_placement must be 'corners' or 'random'")
        if self.min_goal_distance < 0 or self.safe_segment_radius < 0 or self.num_checkpoints < 0:
            raise ValueError("min_goal_distance, safe_segment_radius, num_checkpoints cannot be negative")


# ---------------------------------------------------------------------------
# Generation helpers
# ---------------------------------------------------------------------------


def weighted_choice(rng: random.Random, weights: dict[CellType, float]) -> CellType:
    return rng.choices(list(weights.keys()), weights=list(weights.values()), k=1)[0]


def neighbors(x: int, y: int, width: int, height: int) -> Sequence[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height:
                out.append((nx, ny))
    return out


def _manhattan(x1: int, y1: int, x2: int, y2: int) -> int:
    return abs(x1 - x2) + abs(y1 - y2)


def _cells_in_radius(cx: int, cy: int, radius: int, width: int, height: int) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for y in range(max(0, cy - radius), min(height, cy + radius + 1)):
        for x in range(max(0, cx - radius), min(width, cx + radius + 1)):
            if _manhattan(x, y, cx, cy) <= radius:
                out.append((x, y))
    return out


def apply_symmetry(board: Board, symmetry: str) -> None:
    h, w = len(board), len(board[0]) if board else 0
    if symmetry in {"horizontal", "both"}:
        for y in range(h):
            for x in range(w // 2):
                board[y][w - 1 - x] = board[y][x]
    if symmetry in {"vertical", "both"}:
        for y in range(h // 2):
            for x in range(w):
                board[h - 1 - y][x] = board[y][x]


def _terrain_only_weights(weights: dict[CellType, float]) -> dict[CellType, float]:
    return {k: v for k, v in weights.items() if k not in SPECIAL_SYMBOLS}


def _is_walkable(symbol: CellType) -> bool:
    return symbol not in BLOCKED_TILES


def _bfs_reachable_set(board: Board, start_xy: tuple[int, int], width: int, height: int) -> set[tuple[int, int]]:
    out: set[tuple[int, int]] = set()
    q = deque([start_xy])
    out.add(start_xy)
    while q:
        x, y = q.popleft()
        for nx, ny in neighbors(x, y, width, height):
            if (nx, ny) in out or not _is_walkable(board[ny][nx]):
                continue
            out.add((nx, ny))
            q.append((nx, ny))
    return out


def _get_path_cells(
    board: Board,
    width: int,
    height: int,
    start_cells: list[tuple[int, int]],
    goal_cell: tuple[int, int],
) -> list[tuple[int, int]]:
    from_starts: set[tuple[int, int]] = set()
    for s in start_cells:
        from_starts |= _bfs_reachable_set(board, s, width, height)
    from_goal = _bfs_reachable_set(board, goal_cell, width, height)
    return list(from_starts & from_goal)


def _apply_goal_and_starts(
    board: Board,
    width: int,
    height: int,
    num_starts: int,
    goal_placement: str,
    start_placement: str,
    min_goal_distance: int,
    safe_segment_radius: int,
    num_checkpoints: int,
    rng: random.Random,
) -> None:
    corners = [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]
    all_cells = [(x, y) for y in range(height) for x in range(width)]

    if start_placement == "corners":
        start_cells = [corners[i] for i in range(min(num_starts, len(corners)))]
        needed = num_starts - len(start_cells)
        if needed > 0:
            candidates = [c for c in all_cells if c not in start_cells]
            start_cells.extend(rng.sample(candidates, min(needed, len(candidates))))
    else:
        start_cells = list(rng.sample(all_cells, min(num_starts, len(all_cells))))

    for i, (sx, sy) in enumerate(start_cells):
        if i < len(START_SYMBOLS):
            board[sy][sx] = START_SYMBOLS[i]

    if goal_placement == "center":
        gx, gy = width // 2, height // 2
        if min_goal_distance > 0:
            ok = all(_manhattan(gx, gy, sx, sy) >= min_goal_distance for (sx, sy) in start_cells)
            if not ok:
                candidates = [
                    (x, y) for x in range(width) for y in range(height)
                    if all(_manhattan(x, y, sx, sy) >= min_goal_distance for (sx, sy) in start_cells)
                ]
                if candidates:
                    gx, gy = rng.choice(candidates)
    else:
        candidates = [
            (x, y) for x in range(width) for y in range(height)
            if all(_manhattan(x, y, sx, sy) >= min_goal_distance for (sx, sy) in start_cells)
        ]
        if not candidates:
            candidates = all_cells
        gx, gy = rng.choice(candidates)

    board[gy][gx] = GOAL_SYMBOL
    goal_cell = (gx, gy)

    if safe_segment_radius > 0:
        safe_cells: set[tuple[int, int]] = set()
        for sx, sy in start_cells:
            safe_cells.update(_cells_in_radius(sx, sy, safe_segment_radius, width, height))
        safe_cells.update(_cells_in_radius(gx, gy, safe_segment_radius, width, height))
        for (x, y) in safe_cells:
            if board[y][x] not in (set(START_SYMBOLS) | {GOAL_SYMBOL}):
                board[y][x] = "."

    if num_checkpoints > 0:
        path_cells = _get_path_cells(board, width, height, start_cells, goal_cell)
        path_cells = [
            c for c in path_cells
            if c not in start_cells and c != goal_cell
            and board[c[1]][c[0]] not in (set(START_SYMBOLS) | {GOAL_SYMBOL})
        ]
        n = min(num_checkpoints, len(path_cells))
        for (cx, cy) in rng.sample(path_cells, n):
            board[cy][cx] = CHECKPOINT_SYMBOL


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------


def generate_board(options: BoardOptions) -> Board:
    """
    Generate a new board from the given options.
    Returns a 2D list of cell symbols (Board). Validates options first.
    """
    options.validate()
    rng = random.Random(options.seed)
    terrain_weights = _terrain_only_weights(options.terrain_weights)
    if not terrain_weights:
        raise ValueError("terrain_weights must include at least one non-goal/start symbol")
    symbols = list(terrain_weights.keys())
    weight_list = list(terrain_weights.values())

    board: Board = [["" for _ in range(options.width)] for _ in range(options.height)]
    for y in range(options.height):
        for x in range(options.width):
            board[y][x] = rng.choices(symbols, weights=weight_list, k=1)[0]

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
                counts: dict[CellType, int] = {}
                for nx, ny in neighbors(x, y, options.width, options.height):
                    t = board[ny][nx]
                    counts[t] = counts.get(t, 0) + 1
                if counts:
                    next_board[y][x] = max(counts, key=counts.get)
        board = next_board

    apply_symmetry(board, options.symmetry)
    _apply_goal_and_starts(
        board, options.width, options.height,
        options.num_starts, options.goal_placement, options.start_placement,
        options.min_goal_distance, options.safe_segment_radius, options.num_checkpoints,
        rng,
    )
    return board


# ---------------------------------------------------------------------------
# Pathability and route quality
# ---------------------------------------------------------------------------


_START_INDEX: dict[CellType, int] = {s: i for i, s in enumerate(START_SYMBOLS)}


def _find_goal_and_starts(board: Board) -> tuple[tuple[int, int] | None, list[tuple[int, int]]]:
    goal_xy = None
    starts: list[tuple[int, int] | None] = [None] * len(START_SYMBOLS)
    h, w = len(board), len(board[0]) if board else 0
    for y in range(h):
        for x in range(w):
            c = board[y][x]
            if c == GOAL_SYMBOL:
                goal_xy = (x, y)
            elif c in _START_INDEX:
                starts[_START_INDEX[c]] = (x, y)
    return goal_xy, [s for s in starts if s is not None]


def _bfs_reachable(board: Board, start_xy: tuple[int, int], goal_xy: tuple[int, int]) -> bool:
    h, w = len(board), len(board[0]) if board else 0
    if not h or not w:
        return False
    seen = {start_xy}
    q = deque([start_xy])
    while q:
        x, y = q.popleft()
        if (x, y) == goal_xy:
            return True
        for nx, ny in neighbors(x, y, w, h):
            if (nx, ny) in seen or not _is_walkable(board[ny][nx]):
                continue
            seen.add((nx, ny))
            q.append((nx, ny))
    return False


def check_pathability(board: Board) -> tuple[bool, list[int]]:
    """
    Check whether all start positions can reach the goal.
    Returns (all_reachable, list of unreachable start indices).
    """
    goal_xy, start_positions = _find_goal_and_starts(board)
    if goal_xy is None or not start_positions:
        return True, []
    unreachable: list[int] = []
    for i, start_xy in enumerate(start_positions):
        if not _bfs_reachable(board, start_xy, goal_xy):
            unreachable.append(i)
    return len(unreachable) == 0, unreachable


_SAFE_TILES = {".", "O", GOAL_SYMBOL, CHECKPOINT_SYMBOL} | set(START_SYMBOLS)


def _bfs_shortest_path(
    board: Board,
    start_xy: tuple[int, int],
    goal_xy: tuple[int, int],
) -> list[tuple[int, int]] | None:
    h, w = len(board), len(board[0]) if board else 0
    if not h or not w:
        return None
    parent: dict[tuple[int, int], tuple[int, int] | None] = {start_xy: None}
    q = deque([start_xy])
    while q:
        x, y = q.popleft()
        if (x, y) == goal_xy:
            path: list[tuple[int, int]] = []
            cur: tuple[int, int] | None = (x, y)
            while cur is not None:
                path.append(cur)
                cur = parent[cur]
            path.reverse()
            return path
        for nx, ny in neighbors(x, y, w, h):
            if (nx, ny) in parent or not _is_walkable(board[ny][nx]):
                continue
            parent[(nx, ny)] = (x, y)
            q.append((nx, ny))
    return None


def compute_route_quality(board: Board) -> tuple[str, str]:
    """
    Compute a route quality label and details string from start(s) to goal.
    Returns (label, details) e.g. ("short/easy", "avg path 12 steps, 1 penalty tiles").
    """
    goal_xy, start_positions = _find_goal_and_starts(board)
    if goal_xy is None or not start_positions:
        return "N/A", "No goal or starts"
    lengths: list[int] = []
    penalties: list[int] = []
    for start_xy in start_positions:
        path = _bfs_shortest_path(board, start_xy, goal_xy)
        if path is None:
            return "unreachable", "At least one start cannot reach goal"
        lengths.append(len(path) - 1)
        penalty = sum(1 for (x, y) in path if board[y][x] not in _SAFE_TILES)
        penalties.append(penalty)
    avg_len = sum(lengths) / len(lengths)
    avg_penalty = sum(penalties) / len(penalties)
    if avg_len <= 15 and avg_penalty <= 2:
        label = "short/easy"
    elif avg_len >= 35 or avg_penalty >= 8:
        label = "brutal"
    else:
        label = "medium"
    return label, f"avg path {int(avg_len)} steps, {int(avg_penalty)} penalty tiles"


# ---------------------------------------------------------------------------
# Monte Carlo simulation
# ---------------------------------------------------------------------------


def run_one_simulated_game(
    board: Board,
    start_xy: tuple[int, int],
    goal_xy: tuple[int, int],
    rng: random.Random,
    max_roll: int = 6,
) -> tuple[int, list[tuple[int, int]]]:
    path = _bfs_shortest_path(board, start_xy, goal_xy)
    if not path or len(path) <= 1:
        return 0, list(path) if path else []
    visited = [path[0]]
    path_idx = 0
    turns = 0
    while path_idx < len(path) - 1:
        turns += 1
        roll = rng.randint(1, max_roll)
        next_idx = min(path_idx + roll, len(path) - 1)
        for i in range(path_idx + 1, next_idx + 1):
            visited.append(path[i])
        path_idx = next_idx
    return turns, visited


def run_monte_carlo(
    board: Board,
    num_games: int = 500,
    seed: int | None = None,
    max_roll: int = 6,
) -> dict[str, Any]:
    """
    Run Monte Carlo simulation: many simulated games from each start to goal.
    Returns dict with expected_turns, turns_per_start, heatmap, penalty_spikes.
    """
    goal_xy, start_positions = _find_goal_and_starts(board)
    if goal_xy is None or not start_positions:
        return {"expected_turns": 0.0, "turns_per_start": [], "heatmap": {}, "penalty_spikes": []}
    rng = random.Random(seed)
    h, w = len(board), len(board[0])
    # Sparse counts: only visited cells (avoids O(w*h) dict init on large boards).
    heatmap: defaultdict[tuple[int, int], int] = defaultdict(int)
    turns_per_start: list[float] = [0.0] * len(start_positions)
    for start_idx, start_xy in enumerate(start_positions):
        game_turns: list[int] = []
        for _ in range(num_games):
            turns, visited = run_one_simulated_game(board, start_xy, goal_xy, rng, max_roll)
            game_turns.append(turns)
            for cell in set(visited):
                heatmap[cell] += 1
        turns_per_start[start_idx] = sum(game_turns) / len(game_turns) if game_turns else 0
    expected_turns = sum(turns_per_start) / len(turns_per_start) if turns_per_start else 0
    max_visits = max(heatmap.values()) if heatmap else 1
    penalty_spikes = [
        (x, y) for (x, y), count in heatmap.items()
        if count >= max_visits * 0.3 and board[y][x] not in _SAFE_TILES
        and board[y][x] not in (set(START_SYMBOLS) | {GOAL_SYMBOL})
    ]
    return {
        "expected_turns": expected_turns,
        "turns_per_start": turns_per_start,
        "heatmap": heatmap,
        "penalty_spikes": penalty_spikes[:20],
    }


# ---------------------------------------------------------------------------
# Regenerate selection / locked mask (for app)
# ---------------------------------------------------------------------------


def generate_board_with_selection_or_locks(
    options: BoardOptions,
    regenerate_selection_only: bool,
    current_board: Board | None,
    selection_rect: tuple[int, int, int, int] | None,
    locked_mask: list[list[bool]] | None,
) -> Board:
    """
    Generate a board, optionally preserving locked cells or only regenerating
    the selected region. Used by the GUI for lock/regen selection.
    """
    new_board = generate_board(options)
    if regenerate_selection_only and selection_rect and current_board and locked_mask:
        x0, y0, x1, y1 = selection_rect
        h, w = len(current_board), len(current_board[0])
        result = [row[:] for row in current_board]
        for y in range(max(0, y0), min(h, y1 + 1)):
            for x in range(max(0, x0), min(w, x1 + 1)):
                if y < len(locked_mask) and x < len(locked_mask[0]) and not locked_mask[y][x]:
                    result[y][x] = new_board[y][x]
        return result
    if current_board and locked_mask:
        h, w = len(new_board), len(new_board[0])
        for y in range(h):
            for x in range(w):
                if y < len(locked_mask) and x < len(locked_mask[0]) and locked_mask[y][x]:
                    if y < len(current_board) and x < len(current_board[0]):
                        new_board[y][x] = current_board[y][x]
    return new_board


# ---------------------------------------------------------------------------
# String and parse helpers
# ---------------------------------------------------------------------------


def board_to_string(board: Board) -> str:
    """Serialize board to text (one row per line, space-separated symbols)."""
    return "\n".join(" ".join(row) for row in board)


def board_to_display_string(board: Board) -> str:
    """Serialize board using glyphs from TILE_STYLES for display."""
    rows: list[str] = []
    for row in board:
        glyph_row = [TILE_STYLES.get(s, {"glyph": s})["glyph"] for s in row]
        rows.append(" ".join(glyph_row))
    return "\n".join(rows)


def parse_weights(text: str) -> dict[CellType, float]:
    """
    Parse a weight string like ".:0.65,F:0.17,M:0.10,W:0.08" into symbol -> weight dict.
    Raises ValueError on invalid format.
    """
    weights: dict[CellType, float] = {}
    for part in text.split(","):
        item = part.strip()
        if not item or ":" not in item:
            if item:
                raise ValueError(f"Invalid weight entry '{item}'. Expected symbol:value")
            continue
        symbol, raw = item.split(":", maxsplit=1)
        symbol = symbol.strip()
        if not symbol:
            raise ValueError("Weight symbol cannot be empty")
        try:
            weight = float(raw)
        except ValueError as e:
            raise ValueError(f"Invalid numeric weight for '{symbol}': {raw}") from e
        if weight < 0:
            raise ValueError(f"Weight for '{symbol}' cannot be negative")
        weights[symbol] = weight
    if not weights:
        raise ValueError("At least one terrain weight is required")
    return weights
