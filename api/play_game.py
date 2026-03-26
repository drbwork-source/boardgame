"""
Play mode: turn-based dice-and-move game state and actions.
Game state lives on the backend for multi-device multiplayer.
Uses board_core for board layout, walkability, and goal/start positions.

Game store: Active games are held in an in-memory dict (_games). Games are
lost on server restart. For long-running production servers, consider adding
a TTL or maximum number of games to avoid unbounded memory growth.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field

from board_core import (
    BLOCKED_TILES,
    Board,
    neighbors,
)
from board_core import _find_goal_and_starts


def _is_walkable(symbol: str) -> bool:
    return symbol not in BLOCKED_TILES


def get_valid_moves(
    board: Board,
    position: tuple[int, int],
    width: int,
    height: int,
    four_directions_only: bool = True,
) -> list[tuple[int, int]]:
    """Return list of (col, row) cells the player can move to from position."""
    x, y = position
    all_neighbors = neighbors(x, y, width, height)
    if four_directions_only:
        all_neighbors = [(nx, ny) for nx, ny in all_neighbors if abs(nx - x) + abs(ny - y) == 1]
    out: list[tuple[int, int]] = []
    for (nx, ny) in all_neighbors:
        if 0 <= ny < height and 0 <= nx < width and _is_walkable(board[ny][nx]):
            out.append((nx, ny))
    return out


@dataclass
class PlayState:
    """Immutable snapshot of game state for API responses."""

    board: Board
    player_positions: list[tuple[int, int]]  # (col, row) per player
    current_player_index: int
    current_roll: int | None
    remaining_steps: int
    phase: str  # 'roll' | 'moving' | 'ended'
    winner: int | None  # player index or None
    num_players: int
    valid_moves: list[tuple[int, int]]  # (col, row) for current player when phase == 'moving'


@dataclass
class _Game:
    """Mutable game state held in store."""

    board: Board
    width: int
    height: int
    goal_cell: tuple[int, int]
    player_positions: list[tuple[int, int]]
    current_player_index: int
    current_roll: int | None
    remaining_steps: int
    phase: str
    winner: int | None
    num_players: int
    four_directions_only: bool = True

    def to_state(self) -> PlayState:
        valid_moves: list[tuple[int, int]] = []
        if self.winner is None and self.phase == "moving" and self.remaining_steps > 0:
            pos = self.player_positions[self.current_player_index]
            valid_moves = get_valid_moves(
                self.board,
                pos,
                self.width,
                self.height,
                self.four_directions_only,
            )
        return PlayState(
            board=[row[:] for row in self.board],
            player_positions=list(self.player_positions),
            current_player_index=self.current_player_index,
            current_roll=self.current_roll,
            remaining_steps=self.remaining_steps,
            phase=self.phase,
            winner=self.winner,
            num_players=self.num_players,
            valid_moves=valid_moves,
        )


# In-memory game store (game_id -> _Game). Lost on process restart.
_games: dict[str, _Game] = {}


def create_game(
    board: Board,
    num_players: int | None = None,
    four_directions_only: bool = True,
) -> tuple[str, PlayState]:
    """Create a new game from board. Returns (game_id, initial state)."""
    goal_xy, start_positions = _find_goal_and_starts(board)
    if goal_xy is None or not start_positions:
        raise ValueError("Board must have a goal and at least one start position")
    height = len(board)
    width = len(board[0]) if board else 0
    n = num_players if num_players is not None else len(start_positions)
    n = min(n, len(start_positions))
    positions = [start_positions[i] for i in range(n)]
    game_id = str(uuid.uuid4())
    board_copy = [row[:] for row in board]
    g = _Game(
        board=board_copy,
        width=width,
        height=height,
        goal_cell=goal_xy,
        player_positions=positions,
        current_player_index=0,
        current_roll=None,
        remaining_steps=0,
        phase="roll",
        winner=None,
        num_players=n,
        four_directions_only=four_directions_only,
    )
    _games[game_id] = g
    return game_id, g.to_state()


def get_game(game_id: str) -> _Game | None:
    return _games.get(game_id)


def get_state(game_id: str) -> PlayState | None:
    g = _games.get(game_id)
    return g.to_state() if g else None


def roll(game_id: str) -> PlayState | None:
    """Active player rolls dice. Returns updated state or None if invalid."""
    g = _games.get(game_id)
    if not g or g.winner is not None or g.phase != "roll":
        return None
    g.current_roll = random.randint(1, 6)
    g.remaining_steps = g.current_roll
    g.phase = "moving"
    return g.to_state()


def move(game_id: str, col: int, row: int) -> PlayState | None:
    """Move current player to (col, row). Returns updated state or None if invalid."""
    g = _games.get(game_id)
    if not g or g.winner is not None or g.phase != "moving" or g.remaining_steps <= 0:
        return None
    pos = g.player_positions[g.current_player_index]
    valid = get_valid_moves(
        g.board, pos, g.width, g.height, g.four_directions_only
    )
    if (col, row) not in valid:
        return None
    g.player_positions[g.current_player_index] = (col, row)
    g.remaining_steps -= 1
    if (col, row) == g.goal_cell:
        g.winner = g.current_player_index
        g.phase = "ended"
    return g.to_state()


def end_turn(game_id: str) -> PlayState | None:
    """End current player's turn and advance to next. Returns updated state or None."""
    g = _games.get(game_id)
    if not g or g.winner is not None:
        return None
    g.current_player_index = (g.current_player_index + 1) % g.num_players
    g.phase = "roll"
    g.current_roll = None
    g.remaining_steps = 0
    return g.to_state()
