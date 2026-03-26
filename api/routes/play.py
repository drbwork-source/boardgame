"""
Play mode API: create game, get state, roll, move, end-turn.
Game state is stored on the backend for multi-device multiplayer.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.play_game import PlayState, create_game, end_turn, get_state, move, roll
from api.schemas import PlayCreateRequest, PlayMoveRequest, PlayStateResponse

router = APIRouter(prefix="/board/play", tags=["play"])


def _state_to_response(state: PlayState, game_id: str | None = None) -> PlayStateResponse:
    return PlayStateResponse(
        game_id=game_id,
        board=state.board,
        player_positions=[[p[0], p[1]] for p in state.player_positions],
        current_player_index=state.current_player_index,
        current_roll=state.current_roll,
        remaining_steps=state.remaining_steps,
        phase=state.phase,
        winner=state.winner,
        num_players=state.num_players,
        valid_moves=[[m[0], m[1]] for m in state.valid_moves],
    )


@router.post("/create", response_model=PlayStateResponse)
def post_create(req: PlayCreateRequest) -> PlayStateResponse:
    """Create a new play game from a board. Returns game_id and initial state."""
    if not req.board or not req.board[0]:
        raise HTTPException(status_code=400, detail="Board must have at least one row and column")
    try:
        game_id, state = create_game(
            req.board,
            num_players=req.num_players,
            four_directions_only=req.four_directions_only,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _state_to_response(state, game_id=game_id)


@router.get("/{game_id}", response_model=PlayStateResponse)
def get_play_state(game_id: str) -> PlayStateResponse:
    """Return current game state (for polling / multi-device)."""
    state = get_state(game_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return _state_to_response(state, game_id=game_id)


@router.post("/{game_id}/roll", response_model=PlayStateResponse)
def post_roll(game_id: str) -> PlayStateResponse:
    """Active player rolls the dice. Returns updated state."""
    state = roll(game_id)
    if state is None:
        raise HTTPException(status_code=400, detail="Cannot roll (wrong phase, game over, or game not found)")
    return _state_to_response(state, game_id=game_id)


@router.post("/{game_id}/move", response_model=PlayStateResponse)
def post_move(game_id: str, req: PlayMoveRequest) -> PlayStateResponse:
    """Move current player to (col, row). Returns updated state."""
    state = move(game_id, req.col, req.row)
    if state is None:
        raise HTTPException(status_code=400, detail="Invalid move (wrong phase, cell not valid, or game not found)")
    return _state_to_response(state, game_id=game_id)


@router.post("/{game_id}/end-turn", response_model=PlayStateResponse)
def post_end_turn(game_id: str) -> PlayStateResponse:
    """End current player's turn. Returns updated state."""
    state = end_turn(game_id)
    if state is None:
        raise HTTPException(status_code=400, detail="Cannot end turn (game over or game not found)")
    return _state_to_response(state, game_id=game_id)
