"""
pytest tests for board_core: generate_board, check_pathability, compute_route_quality,
run_monte_carlo, board_to_string, parse_weights, apply_symmetry, generate_board_with_selection_or_locks.
"""

import pytest

from board_core import (
    BOARD_SIZE_MAX,
    BOARD_SIZE_MIN,
    BoardOptions,
    DEFAULT_TERRAIN_WEIGHTS,
    GOAL_SYMBOL,
    START_SYMBOLS,
    apply_symmetry,
    board_to_string,
    check_pathability,
    compute_route_quality,
    generate_board,
    generate_board_with_selection_or_locks,
    parse_weights,
    run_monte_carlo,
)


# ---------------------------------------------------------------------------
# generate_board
# ---------------------------------------------------------------------------


def test_generate_board_shape_and_seed():
    """Board has correct dimensions and is deterministic with seed."""
    options = BoardOptions(width=10, height=8, seed=42)
    board = generate_board(options)
    assert len(board) == 8
    assert all(len(row) == 10 for row in board)
    board2 = generate_board(options)
    assert board == board2


def test_generate_board_contains_goal_and_starts():
    """Generated board contains exactly one goal and num_starts start positions."""
    options = BoardOptions(width=15, height=15, seed=123, num_starts=2)
    board = generate_board(options)
    goals = sum(1 for row in board for c in row if c == GOAL_SYMBOL)
    assert goals == 1
    starts = sum(1 for row in board for c in row if c in START_SYMBOLS)
    assert starts == 2


def test_generate_board_invalid_options_raises():
    """Invalid options raise ValueError."""
    with pytest.raises(ValueError):
        generate_board(BoardOptions(width=0, height=10))
    with pytest.raises(ValueError):
        generate_board(BoardOptions(width=10, height=10, terrain_weights={}))


def test_generate_pathboard_single_start_goal_and_reachable():
    """Pathboard mode always uses one start/goal and keeps them connected."""
    options = BoardOptions(width=28, height=18, seed=99, generation_mode="pathboard", num_starts=4)
    board = generate_board(options)
    goals = sum(1 for row in board for c in row if c == GOAL_SYMBOL)
    starts = sum(1 for row in board for c in row if c in START_SYMBOLS)
    assert goals == 1
    assert starts == 1
    ok, unreachable = check_pathability(board)
    assert ok is True
    assert unreachable == []


def test_generate_pathboard_is_seed_deterministic():
    """Pathboard generation should be deterministic for the same seed."""
    options = BoardOptions(width=22, height=16, seed=12345, generation_mode="pathboard")
    board1 = generate_board(options)
    board2 = generate_board(options)
    assert board1 == board2


def test_generate_board_invalid_generation_mode_raises():
    """Unknown generation mode should fail validation."""
    with pytest.raises(ValueError):
        generate_board(BoardOptions(width=10, height=10, generation_mode="unknown"))


# ---------------------------------------------------------------------------
# check_pathability
# ---------------------------------------------------------------------------


def test_check_pathability_all_reachable():
    """Board where all starts can reach goal returns (True, [])."""
    # Simple 3x3: start at (0,0), goal at (2,2), all walkable
    board = [
        ["1", ".", "."],
        [".", ".", "."],
        [".", ".", "G"],
    ]
    ok, unreachable = check_pathability(board)
    assert ok is True
    assert unreachable == []


def test_check_pathability_unreachable():
    """Board with blocked path returns (False, [unreachable start indices])."""
    # Start 1 at (0,0), goal at (2,2), row 1 blocked by water
    board = [
        ["1", ".", "."],
        ["W", "W", "W"],
        [".", ".", "G"],
    ]
    ok, unreachable = check_pathability(board)
    assert ok is False
    assert 0 in unreachable


# ---------------------------------------------------------------------------
# compute_route_quality
# ---------------------------------------------------------------------------


def test_compute_route_quality_returns_label_and_details():
    """Route quality returns (label, details) tuple."""
    board = [
        ["1", ".", ".", "G"],
        [".", ".", ".", "."],
    ]
    label, details = compute_route_quality(board)
    assert isinstance(label, str)
    assert isinstance(details, str)
    assert "path" in details.lower() or "step" in details.lower() or "N/A" in label or "unreachable" in label


# ---------------------------------------------------------------------------
# run_monte_carlo
# ---------------------------------------------------------------------------


def test_run_monte_carlo_smoke():
    """Monte Carlo returns expected keys and types."""
    board = [
        ["1", ".", ".", "G"],
        [".", ".", ".", "."],
    ]
    result = run_monte_carlo(board, num_games=20, seed=1)
    assert "expected_turns" in result
    assert "turns_per_start" in result
    assert "heatmap" in result
    assert "penalty_spikes" in result
    assert isinstance(result["expected_turns"], (int, float))
    assert isinstance(result["turns_per_start"], list)
    assert isinstance(result["heatmap"], dict)
    assert isinstance(result["penalty_spikes"], list)


# ---------------------------------------------------------------------------
# board_to_string / parse_weights
# ---------------------------------------------------------------------------


def test_board_to_string_roundtrip():
    """board_to_string produces parseable-looking grid (one char per cell)."""
    board = [["1", ".", "G"], [".", "F", "."]]
    s = board_to_string(board)
    assert "1" in s and "." in s and "G" in s and "F" in s
    lines = s.splitlines()
    assert len(lines) == 2
    assert len(lines[0].split()) == 3


def test_parse_weights_valid():
    """parse_weights parses valid weight string."""
    w = parse_weights(".:0.65,F:0.17,M:0.10,W:0.08")
    assert w["."] == 0.65
    assert w["F"] == 0.17
    assert w["M"] == 0.10
    assert w["W"] == 0.08


def test_parse_weights_invalid_raises():
    """parse_weights raises on invalid format."""
    with pytest.raises(ValueError):
        parse_weights("invalid")
    with pytest.raises(ValueError):
        parse_weights(".:abc")
    with pytest.raises(ValueError):
        parse_weights("")


@pytest.mark.parametrize(
    "text,expected",
    [
        (".:0.5", {".": 0.5}),
        ("A:0.1,B:0.9", {"A": 0.1, "B": 0.9}),
        ("X:1.0", {"X": 1.0}),
    ],
)
def test_parse_weights_parametrized_valid(text, expected):
    """parse_weights parses various valid weight strings."""
    assert parse_weights(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "no_colon",
        ".:not_a_number",
        ":0.5",
        ".:-1",
        "",
    ],
)
def test_parse_weights_parametrized_invalid(text):
    """parse_weights raises ValueError for invalid strings."""
    with pytest.raises(ValueError):
        parse_weights(text)


# ---------------------------------------------------------------------------
# apply_symmetry
# ---------------------------------------------------------------------------


def test_apply_symmetry_horizontal():
    """Horizontal symmetry mirrors left half to right half."""
    board = [
        ["1", ".", "x", "y"],
        ["F", "M", "a", "b"],
    ]
    apply_symmetry(board, "horizontal")
    assert board[0] == ["1", ".", ".", "1"]
    assert board[1] == ["F", "M", "M", "F"]


def test_apply_symmetry_vertical():
    """Vertical symmetry mirrors top half to bottom half."""
    board = [
        ["1", "."],
        ["F", "M"],
        ["a", "b"],
        ["x", "y"],
    ]
    apply_symmetry(board, "vertical")
    assert board[0] == ["1", "."]
    assert board[1] == ["F", "M"]
    assert board[2] == ["F", "M"]
    assert board[3] == ["1", "."]


# ---------------------------------------------------------------------------
# generate_board_with_selection_or_locks
# ---------------------------------------------------------------------------


def test_generate_board_with_selection_or_locks_preserves_locked():
    """Locked cells are preserved from current_board when generating with locked_mask."""
    options = BoardOptions(width=3, height=3, seed=999)
    current_board = [
        ["1", ".", "."],
        [".", "G", "."],
        [".", ".", "F"],
    ]
    locked_mask = [
        [False, False, False],
        [False, True, False],
        [False, False, True],
    ]
    result = generate_board_with_selection_or_locks(
        options, regenerate_selection_only=False, current_board=current_board, selection_rect=None, locked_mask=locked_mask
    )
    assert result[1][1] == "G"
    assert result[2][2] == "F"


def test_generate_board_with_selection_or_locks_regenerate_selection_only():
    """When regenerate_selection_only is True, only non-locked cells in selection are regenerated."""
    options = BoardOptions(width=4, height=4, seed=42)
    current_board = [
        ["1", ".", ".", "."],
        [".", "X", "Y", "."],
        [".", ".", "G", "."],
        [".", ".", ".", "."],
    ]
    locked_mask = [
        [False, False, False, False],
        [False, True, True, False],
        [False, False, True, False],
        [False, False, False, False],
    ]
    selection_rect = (1, 1, 2, 2)
    result = generate_board_with_selection_or_locks(
        options, regenerate_selection_only=True, current_board=current_board, selection_rect=selection_rect, locked_mask=locked_mask
    )
    assert result[1][1] == "X"
    assert result[1][2] == "Y"
    assert result[2][2] == "G"


def test_board_size_limits():
    """Board size constants are consistent."""
    assert BOARD_SIZE_MIN >= 1
    assert BOARD_SIZE_MAX >= BOARD_SIZE_MIN
