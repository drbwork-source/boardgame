/** API and app types matching the backend. */

export interface TileStyle {
  fg: string;
  bg: string;
  glyph: string;
}

export interface TileMetadataEntry {
  category?: string;
  difficulty?: number;
  deck_id?: string;
}

export interface DeckEntry {
  id: string;
  name: string;
  card_template_ids: string[];
}

export interface DeckImportResult {
  decks_created: number;
  decks_updated: number;
  cards_created: number;
}

export interface CardTemplateEntry {
  id: string;
  title: string;
  body: string;
  image_url?: string | null;
  back_text?: string | null;
}

export interface Config {
  board_presets: number[][];
  tileset_presets: Record<string, Record<string, number>>;
  tile_names: Record<string, string>;
  tile_colors: Record<string, string>;
  tile_styles: Record<string, TileStyle>;
  tile_rules: Record<string, string>;
  tile_metadata?: Record<string, TileMetadataEntry>;
  decks?: DeckEntry[];
  board_size_min: number;
  board_size_max: number;
  symmetry_choices: string[];
  goal_placement_choices: string[];
  start_placement_choices: string[];
}

export type Board = string[][];

export interface GenerateOptions {
  width: number;
  height: number;
  seed: number | null;
  terrain_weights: Record<string, number>;
  symmetry: string;
  smoothing_passes: number;
  cluster_bias: number;
  num_starts: number;
  goal_placement: string;
  start_placement: string;
  min_goal_distance: number;
  safe_segment_radius: number;
  num_checkpoints: number;
}

export interface GenerateResponse {
  board: Board;
  seed_used: number | null;
}

export interface PathabilityResponse {
  ok: boolean;
  unreachable: number[];
}

export interface BoardValidationResponse {
  goal_count: number;
  start_count: number;
  pathability_ok: boolean;
  unreachable: number[];
  min_start_goal_distance: number | null;
}

export interface RouteQualityResponse {
  label: string;
  details: string;
}

export interface BoardTextResponse {
  text: string;
}

export interface SimulateResponse {
  expected_turns: number;
  turns_per_start: number[];
  heatmap: { x: number; y: number; count: number }[];
  penalty_spikes: number[][];
  turn_spread: number;
  hotspot_count: number;
}

/** Unified saved game file shape (version, board, options, tile_rules, tile_metadata, locked_mask, layers). */
export interface GameSaveData {
  version?: number;
  board: Board;
  options?: GenerateOptions;
  tile_rules?: Record<string, string>;
  tile_metadata?: Record<string, { category?: string; difficulty?: number; deck_id?: string }>;
  locked_mask?: boolean[][];
  path_layer?: Board;
  events_layer?: Board;
}

/** Play mode: game state from backend (create, get, roll, move, end-turn). */
export interface PlayStateResponse {
  game_id?: string | null;
  board: Board;
  player_positions: number[][]; // [col, row] per player
  current_player_index: number;
  current_roll: number | null;
  remaining_steps: number;
  phase: "roll" | "moving" | "ended";
  winner: number | null;
  num_players: number;
  valid_moves: number[][]; // [col, row] for current player
}
