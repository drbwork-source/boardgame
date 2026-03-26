"""
Pydantic schemas for the Board Generator API.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Config (responses)
# ---------------------------------------------------------------------------


class TileStyle(BaseModel):
    fg: str
    bg: str
    glyph: str


class DeckEntry(BaseModel):
    """A card deck (e.g. Forest Deck, Mountain Deck) for per-tile events."""
    id: str
    name: str
    card_template_ids: list[str] = Field(default_factory=list)


class CardTemplateEntry(BaseModel):
    """A single card template with content for export."""
    id: str
    title: str
    body: str
    image_url: str | None = None
    back_text: str | None = None


class CardTemplateCreateRequest(BaseModel):
    title: str = ""
    body: str = ""
    image_url: str | None = None
    back_text: str | None = None


class CardTemplateUpdateRequest(BaseModel):
    title: str | None = None
    body: str | None = None
    image_url: str | None = None
    back_text: str | None = None


class ConfigResponse(BaseModel):
    board_presets: list[list[int]]  # [[10,10], [25,25], ...]
    tileset_presets: dict[str, dict[str, float]]
    tile_names: dict[str, str]
    tile_colors: dict[str, str]
    tile_styles: dict[str, TileStyle]
    tile_rules: dict[str, str]
    tile_metadata: dict[str, dict[str, Any]] = {}  # symbol -> {category, difficulty, deck_id}
    decks: list[DeckEntry] = Field(default_factory=list)
    board_size_min: int
    board_size_max: int
    symmetry_choices: list[str] = ["none", "horizontal", "vertical", "both"]
    goal_placement_choices: list[str] = ["center", "random"]
    start_placement_choices: list[str] = ["corners", "random"]


class DeckCreateRequest(BaseModel):
    name: str
    card_template_ids: list[str] = Field(default_factory=list)


class DeckUpdateRequest(BaseModel):
    name: str | None = None
    card_template_ids: list[str] | None = None


class DeckImportResult(BaseModel):
    """Result of importing decks/cards from Excel or CSV."""
    decks_created: int = 0
    decks_updated: int = 0
    cards_created: int = 0


class TileMetadataUpdate(BaseModel):
    category: str | None = None
    difficulty: int | None = None
    deck_id: str | None = None


class TileMetadataPatchRequest(BaseModel):
    """Bulk update tile metadata: symbol -> { category?, difficulty?, deck_id? }."""
    tile_metadata: dict[str, TileMetadataUpdate]


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    width: int = Field(ge=5, le=100, default=50)
    height: int = Field(ge=5, le=100, default=50)
    seed: int | None = None
    terrain_weights: dict[str, float] = Field(default_factory=dict)
    symmetry: str = "none"
    smoothing_passes: int = Field(ge=0, default=1)
    cluster_bias: float = Field(ge=0.0, le=1.0, default=0.2)
    num_starts: int = Field(ge=1, le=4, default=4)
    goal_placement: str = "center"
    start_placement: str = "corners"
    min_goal_distance: int = Field(ge=0, default=0)
    safe_segment_radius: int = Field(ge=0, default=0)
    num_checkpoints: int = Field(ge=0, default=0)


class GenerateResponse(BaseModel):
    board: list[list[str]]
    seed_used: int | None


class GenerateBalancedRequest(BaseModel):
    """Same as GenerateRequest with optional target_quality and max_attempts."""
    width: int = Field(ge=5, le=100, default=50)
    height: int = Field(ge=5, le=100, default=50)
    terrain_weights: dict[str, float] = Field(default_factory=dict)
    symmetry: str = "none"
    smoothing_passes: int = Field(ge=0, default=1)
    cluster_bias: float = Field(ge=0.0, le=1.0, default=0.2)
    num_starts: int = Field(ge=1, le=4, default=4)
    goal_placement: str = "center"
    start_placement: str = "corners"
    min_goal_distance: int = Field(ge=0, default=0)
    safe_segment_radius: int = Field(ge=0, default=0)
    num_checkpoints: int = Field(ge=0, default=0)
    target_quality: str = "short/easy"  # "short/easy" | "medium" | "any"
    max_attempts: int = Field(ge=1, le=200, default=50)


# ---------------------------------------------------------------------------
# Pathability / route quality / board text
# ---------------------------------------------------------------------------


class BoardRequest(BaseModel):
    board: list[list[str]]


class PathabilityResponse(BaseModel):
    ok: bool
    unreachable: list[int]


class BoardValidationResponse(BaseModel):
    goal_count: int
    start_count: int
    pathability_ok: bool
    unreachable: list[int]
    min_start_goal_distance: int | None


class RouteQualityResponse(BaseModel):
    label: str
    details: str


class BoardTextResponse(BaseModel):
    text: str


# ---------------------------------------------------------------------------
# Export image
# ---------------------------------------------------------------------------


class ExportImageRequest(BaseModel):
    board: list[list[str]]
    tile_size: int = Field(ge=8, le=48, default=20)


# ---------------------------------------------------------------------------
# Monte Carlo simulation
# ---------------------------------------------------------------------------


class SimulateRequest(BaseModel):
    board: list[list[str]]
    num_games: int = Field(ge=10, le=5000, default=500)
    seed: int | None = None
    max_roll: int = Field(ge=1, le=12, default=6)


class SimulateResponse(BaseModel):
    expected_turns: float
    turns_per_start: list[float]
    heatmap: list[dict[str, Any]]  # [{"x": int, "y": int, "count": int}, ...]
    penalty_spikes: list[list[int]]  # [[x, y], ...]
    turn_spread: float
    hotspot_count: int


# ---------------------------------------------------------------------------
# Save / load game (unified JSON format)
# ---------------------------------------------------------------------------

GAME_SAVE_VERSION = 1


class GameExportRequest(BaseModel):
    board: list[list[str]]
    options: GenerateRequest | None = None
    tile_rules: dict[str, str] | None = None
    tile_metadata: dict[str, dict[str, Any]] | None = None
    locked_mask: list[list[bool]] | None = None
    path_layer: list[list[str]] | None = None
    events_layer: list[list[str]] | None = None


class GameExportResponse(BaseModel):
    """Unified saved game file shape (version, board, options, tile_rules, tile_metadata, locked_mask, layers)."""
    version: int = GAME_SAVE_VERSION
    board: list[list[str]]
    options: GenerateRequest | None = None
    tile_rules: dict[str, str] | None = None
    tile_metadata: dict[str, dict[str, Any]] | None = None
    locked_mask: list[list[bool]] | None = None
    path_layer: list[list[str]] | None = None
    events_layer: list[list[str]] | None = None


class GameImportRequest(BaseModel):
    """Uploaded game file content (unified schema)."""
    version: int | None = None
    board: list[list[str]]
    options: GenerateRequest | None = None
    tile_rules: dict[str, str] | None = None
    tile_metadata: dict[str, dict[str, Any]] | None = None
    locked_mask: list[list[bool]] | None = None
    path_layer: list[list[str]] | None = None
    events_layer: list[list[str]] | None = None


class GameImportResponse(BaseModel):
    """Parsed game for frontend state."""
    board: list[list[str]]
    options: GenerateRequest | None = None
    tile_rules: dict[str, str] | None = None
    tile_metadata: dict[str, dict[str, Any]] | None = None
    locked_mask: list[list[bool]] | None = None
    path_layer: list[list[str]] | None = None
    events_layer: list[list[str]] | None = None


# ---------------------------------------------------------------------------
# Regenerate (selection / locked mask)
# ---------------------------------------------------------------------------


class RegenerateRequest(BaseModel):
    board: list[list[str]]
    options: GenerateRequest
    selection_rect: list[int] | None = None  # [x0, y0, x1, y1]
    locked_mask: list[list[bool]] | None = None
    regenerate_selection_only: bool = True


class RegenerateResponse(BaseModel):
    board: list[list[str]]


# ---------------------------------------------------------------------------
# Print export (tiled pages or poster)
# ---------------------------------------------------------------------------


class ExportPrintRequest(BaseModel):
    board: list[list[str]]
    paper: str = "a4"  # "a4" | "letter"
    mode: str = "tiled"  # "tiled" | "poster"


class ExportCardsRequest(BaseModel):
    """Export print-ready card sheets for given decks (placeholder fronts + optional back, cut lines)."""
    deck_ids: list[str] = Field(default_factory=list)  # empty = all decks
    include_back: bool = True


# ---------------------------------------------------------------------------
# Play mode (turn-based dice game; state on backend for multi-device)
# ---------------------------------------------------------------------------


class PlayCreateRequest(BaseModel):
    """Create a new play game from a board."""
    board: list[list[str]]
    num_players: int | None = None  # default: number of starts on board
    four_directions_only: bool = True


class PlayStateResponse(BaseModel):
    """Play game state (create, get, roll, move, end-turn)."""
    game_id: str | None = None  # present on create, optional on others
    board: list[list[str]]
    player_positions: list[list[int]]  # [[col, row], ...]
    current_player_index: int
    current_roll: int | None
    remaining_steps: int
    phase: str
    winner: int | None
    num_players: int
    valid_moves: list[list[int]]  # [[col, row], ...]


class PlayMoveRequest(BaseModel):
    """Target cell for a move (col, row)."""
    col: int
    row: int
