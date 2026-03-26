/**
 * API client for Board Generator Studio backend.
 * Uses relative /api so Vite proxy works in dev.
 */

import type {
  Board,
  BoardValidationResponse,
  CardTemplateEntry,
  Config,
  DeckEntry,
  DeckImportResult,
  GameSaveData,
  GenerateOptions,
  GenerateResponse,
  PathabilityResponse,
  PlayStateResponse,
  RouteQualityResponse,
  BoardTextResponse,
  SimulateResponse,
} from "./types";

const API = "/api";

async function readApiErrorMessage(res: Response): Promise<string> {
  let text = "";
  try {
    text = await res.text();
  } catch {
    return `HTTP ${res.status}`;
  }
  if (!text) return `HTTP ${res.status}`;
  try {
    const parsed = JSON.parse(text) as { detail?: unknown };
    if (typeof parsed.detail === "string" && parsed.detail.trim()) return parsed.detail;
  } catch {
    // Response is plain text.
  }
  return text;
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    throw new Error(await readApiErrorMessage(res));
  }
  return res.json() as Promise<T>;
}

export async function getConfig(): Promise<Config> {
  return fetchJson<Config>(`${API}/config`);
}

export async function patchTileMetadata(
  updates: Record<string, { category?: string; difficulty?: number; deck_id?: string }>
): Promise<{ status: string }> {
  return fetchJson<{ status: string }>(`${API}/config/tile-metadata`, {
    method: "PATCH",
    body: JSON.stringify({ tile_metadata: updates }),
  });
}

export async function listDecks(): Promise<DeckEntry[]> {
  return fetchJson<DeckEntry[]>(`${API}/config/decks`);
}

export async function createDeck(name: string, cardTemplateIds: string[] = []): Promise<DeckEntry> {
  return fetchJson<DeckEntry>(`${API}/config/decks`, {
    method: "POST",
    body: JSON.stringify({ name, card_template_ids: cardTemplateIds }),
  });
}

export async function updateDeck(
  deckId: string,
  updates: { name?: string; card_template_ids?: string[] }
): Promise<DeckEntry> {
  return fetchJson<DeckEntry>(`${API}/config/decks/${encodeURIComponent(deckId)}`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

export async function deleteDeck(deckId: string): Promise<{ status: string }> {
  return fetchJson<{ status: string }>(`${API}/config/decks/${encodeURIComponent(deckId)}`, {
    method: "DELETE",
  });
}

/** Draw a random card from a deck. Throws if deck not found or has no cards. */
export async function drawCard(deckId: string): Promise<CardTemplateEntry> {
  return fetchJson<CardTemplateEntry>(`${API}/config/decks/${encodeURIComponent(deckId)}/draw`);
}

/** Draw a random card for a tile symbol (backend looks up deck from tile metadata). Throws if tile has no deck or deck empty. */
export async function drawCardForTile(symbol: string): Promise<CardTemplateEntry> {
  return fetchJson<CardTemplateEntry>(
    `${API}/config/draw-card-for-tile?symbol=${encodeURIComponent(symbol)}`
  );
}

export async function importDecksFromFile(file: File): Promise<DeckImportResult> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API}/config/decks/import`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    throw new Error(await readApiErrorMessage(res));
  }
  return res.json() as Promise<DeckImportResult>;
}

export async function listCardTemplates(deckId?: string): Promise<CardTemplateEntry[]> {
  const q = deckId != null ? `?deck_id=${encodeURIComponent(deckId)}` : "";
  return fetchJson<CardTemplateEntry[]>(`${API}/config/card-templates${q}`);
}

export async function createCardTemplate(data: {
  title?: string;
  body?: string;
  image_url?: string | null;
  back_text?: string | null;
}): Promise<CardTemplateEntry> {
  return fetchJson<CardTemplateEntry>(`${API}/config/card-templates`, {
    method: "POST",
    body: JSON.stringify({
      title: data.title ?? "",
      body: data.body ?? "",
      image_url: data.image_url ?? null,
      back_text: data.back_text ?? null,
    }),
  });
}

export async function updateCardTemplate(
  templateId: string,
  updates: { title?: string; body?: string; image_url?: string | null; back_text?: string | null }
): Promise<CardTemplateEntry> {
  return fetchJson<CardTemplateEntry>(
    `${API}/config/card-templates/${encodeURIComponent(templateId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(updates),
    }
  );
}

export async function deleteCardTemplate(templateId: string): Promise<{ status: string }> {
  return fetchJson<{ status: string }>(
    `${API}/config/card-templates/${encodeURIComponent(templateId)}`,
    { method: "DELETE" }
  );
}

/** Build request body for generate/generate-balanced/regenerate (single source of truth for option defaults). */
function buildGenerateOptionsBody(options: Partial<GenerateOptions>): Record<string, unknown> {
  return {
    width: options.width ?? 50,
    height: options.height ?? 50,
    seed: options.seed ?? null,
    terrain_weights: options.terrain_weights ?? {},
    symmetry: options.symmetry ?? "none",
    smoothing_passes: options.smoothing_passes ?? 1,
    cluster_bias: options.cluster_bias ?? 0.2,
    num_starts: options.num_starts ?? 4,
    goal_placement: options.goal_placement ?? "center",
    start_placement: options.start_placement ?? "corners",
    min_goal_distance: options.min_goal_distance ?? 0,
    safe_segment_radius: options.safe_segment_radius ?? 0,
    num_checkpoints: options.num_checkpoints ?? 0,
  };
}

export async function generateBoard(options: Partial<GenerateOptions>): Promise<GenerateResponse> {
  return fetchJson<GenerateResponse>(`${API}/board/generate`, {
    method: "POST",
    body: JSON.stringify(buildGenerateOptionsBody(options)),
  });
}

export async function generateBalancedBoard(
  options: Partial<GenerateOptions>,
  targetQuality: "short/easy" | "medium" | "any" = "short/easy",
  maxAttempts: number = 50
): Promise<GenerateResponse> {
  const body = {
    ...buildGenerateOptionsBody(options),
    target_quality: targetQuality,
    max_attempts: maxAttempts,
  };
  return fetchJson<GenerateResponse>(`${API}/board/generate-balanced`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function checkPathability(board: Board): Promise<PathabilityResponse> {
  return fetchJson<PathabilityResponse>(`${API}/board/pathability`, {
    method: "POST",
    body: JSON.stringify({ board }),
  });
}

export async function validateBoard(board: Board): Promise<BoardValidationResponse> {
  return fetchJson<BoardValidationResponse>(`${API}/board/validate`, {
    method: "POST",
    body: JSON.stringify({ board }),
  });
}

export async function getRouteQuality(board: Board): Promise<RouteQualityResponse> {
  return fetchJson<RouteQualityResponse>(`${API}/board/route-quality`, {
    method: "POST",
    body: JSON.stringify({ board }),
  });
}

/** Pathability + route quality in one round-trip (parallel HTTP). */
export async function boardAnalysis(board: Board): Promise<{
  pathability: PathabilityResponse;
  routeQuality: RouteQualityResponse;
  validation: BoardValidationResponse;
}> {
  const [pathability, routeQuality, validation] = await Promise.all([
    checkPathability(board),
    getRouteQuality(board),
    validateBoard(board),
  ]);
  return { pathability, routeQuality, validation };
}

export async function runSimulation(
  board: Board,
  options?: { num_games?: number; seed?: number | null; max_roll?: number }
): Promise<SimulateResponse> {
  return fetchJson<SimulateResponse>(`${API}/board/simulate`, {
    method: "POST",
    body: JSON.stringify({
      board,
      num_games: options?.num_games ?? 500,
      seed: options?.seed ?? null,
      max_roll: options?.max_roll ?? 6,
    }),
  });
}

export async function exportGame(
  board: Board,
  options?: Partial<GenerateOptions> | null,
  lockedMask?: boolean[][] | null,
  pathLayer?: Board | null,
  eventsLayer?: Board | null
): Promise<GameSaveData> {
  const body: {
    board: Board;
    options?: Partial<GenerateOptions>;
    locked_mask?: boolean[][];
    path_layer?: Board;
    events_layer?: Board;
  } = { board };
  if (options && Object.keys(options).length > 0) {
    body.options = options;
  }
  if (lockedMask && lockedMask.length > 0 && lockedMask[0].length > 0) {
    body.locked_mask = lockedMask;
  }
  if (pathLayer && pathLayer.length > 0 && pathLayer[0].length > 0) {
    body.path_layer = pathLayer;
  }
  if (eventsLayer && eventsLayer.length > 0 && eventsLayer[0].length > 0) {
    body.events_layer = eventsLayer;
  }
  return fetchJson<GameSaveData>(`${API}/board/export-game`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function importGame(data: GameSaveData): Promise<GameSaveData> {
  return fetchJson<GameSaveData>(`${API}/board/import-game`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export interface RegenerateParams {
  board: Board;
  options: Partial<GenerateOptions>;
  selection_rect?: [number, number, number, number] | null;
  locked_mask?: boolean[][] | null;
  regenerate_selection_only?: boolean;
}

export async function regenerate(params: RegenerateParams): Promise<{ board: Board }> {
  const body = {
    board: params.board,
    options: buildGenerateOptionsBody(params.options),
    selection_rect: params.selection_rect ?? null,
    locked_mask: params.locked_mask ?? null,
    regenerate_selection_only: params.regenerate_selection_only ?? true,
  };
  return fetchJson<{ board: Board }>(`${API}/board/regenerate`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function exportPrint(
  board: Board,
  options: { paper?: "a4" | "letter"; mode?: "tiled" | "poster" }
): Promise<Blob> {
  const res = await fetch(`${API}/board/export-print`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      board,
      paper: options.paper ?? "a4",
      mode: options.mode ?? "tiled",
    }),
  });
  if (!res.ok) {
    throw new Error(await readApiErrorMessage(res));
  }
  return res.blob();
}

export async function exportCards(options?: {
  deck_ids?: string[];
  include_back?: boolean;
}): Promise<Blob> {
  const res = await fetch(`${API}/board/export-cards`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      deck_ids: options?.deck_ids ?? [],
      include_back: options?.include_back ?? true,
    }),
  });
  if (!res.ok) {
    throw new Error(await readApiErrorMessage(res));
  }
  return res.blob();
}

export async function getBoardText(board: Board): Promise<BoardTextResponse> {
  return fetchJson<BoardTextResponse>(`${API}/board/to-text`, {
    method: "POST",
    body: JSON.stringify({ board }),
  });
}

/** Client-side PNG export (no backend required). Renders board to canvas and returns PNG blob. */
export function exportBoardImageClientSide(
  board: Board,
  tileColors: Record<string, string>,
  tileStyles: Record<string, { glyph: string }>,
  tileSize: number
): Promise<Blob> {
  return new Promise((resolve, reject) => {
    if (!board.length || !board[0].length) {
      reject(new Error("Board is empty"));
      return;
    }
    const w = board[0].length * tileSize;
    const h = board.length * tileSize;
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      reject(new Error("Could not get canvas context"));
      return;
    }
    ctx.fillStyle = "#0a0e14";
    ctx.fillRect(0, 0, w, h);
    for (let y = 0; y < board.length; y++) {
      for (let x = 0; x < board[y].length; x++) {
        const symbol = board[y][x];
        const color = tileColors[symbol] ?? "#f8fafc";
        const glyph = tileStyles[symbol]?.glyph ?? symbol;
        ctx.fillStyle = color;
        ctx.fillRect(x * tileSize, y * tileSize, tileSize, tileSize);
        ctx.strokeStyle = "#262a33";
        ctx.lineWidth = 1;
        ctx.strokeRect(x * tileSize, y * tileSize, tileSize, tileSize);
        ctx.fillStyle = "#1f2937";
        ctx.font = `${Math.max(10, tileSize - 4)}px system-ui, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(
          glyph,
          x * tileSize + tileSize / 2,
          y * tileSize + tileSize / 2
        );
      }
    }
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("toBlob failed"))),
      "image/png"
    );
  });
}

export async function exportBoardImage(
  board: Board,
  tileSize: number = 20
): Promise<Blob> {
  const res = await fetch(`${API}/board/export-image`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ board, tile_size: tileSize }),
  });
  if (!res.ok) {
    throw new Error(await readApiErrorMessage(res));
  }
  return res.blob();
}

// ---------------------------------------------------------------------------
// Play mode (state on backend for multi-device)
// ---------------------------------------------------------------------------

export async function createPlayGame(
  board: Board,
  options?: { num_players?: number; four_directions_only?: boolean }
): Promise<PlayStateResponse> {
  return fetchJson<PlayStateResponse>(`${API}/board/play/create`, {
    method: "POST",
    body: JSON.stringify({
      board,
      num_players: options?.num_players ?? null,
      four_directions_only: options?.four_directions_only ?? true,
    }),
  });
}

export async function getPlayState(gameId: string): Promise<PlayStateResponse> {
  return fetchJson<PlayStateResponse>(`${API}/board/play/${encodeURIComponent(gameId)}`);
}

export async function rollDice(gameId: string): Promise<PlayStateResponse> {
  return fetchJson<PlayStateResponse>(`${API}/board/play/${encodeURIComponent(gameId)}/roll`, {
    method: "POST",
  });
}

export async function playMove(gameId: string, col: number, row: number): Promise<PlayStateResponse> {
  return fetchJson<PlayStateResponse>(`${API}/board/play/${encodeURIComponent(gameId)}/move`, {
    method: "POST",
    body: JSON.stringify({ col, row }),
  });
}

export async function endPlayTurn(gameId: string): Promise<PlayStateResponse> {
  return fetchJson<PlayStateResponse>(`${API}/board/play/${encodeURIComponent(gameId)}/end-turn`, {
    method: "POST",
  });
}
