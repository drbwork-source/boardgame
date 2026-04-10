import { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { exportCards } from "../api";
import type { Board, Config, SimulateResponse, TileMetadataEntry } from "../types";

interface ActionsPanelProps {
  config: Config | null;
  onSaveTileMetadata: (updates: Record<string, TileMetadataEntry>) => void;
  board: Board;
  canUndo: boolean;
  canRedo: boolean;
  pathabilityResult: { ok: boolean; unreachable: number[] } | null;
  validationResult: {
    goal_count: number;
    start_count: number;
    pathability_ok: boolean;
    unreachable: number[];
    min_start_goal_distance: number | null;
  } | null;
  routeQuality: { label: string; details: string } | null;
  simulationResult: SimulateResponse | null;
  simulating: boolean;
  onRunSimulation: () => void;
  onUndo: () => void;
  onRedo: () => void;
  onCheckPathability: () => void;
  onSaveText: () => void;
  onExportImage: () => void;
  onExportPrint: (paper: "a4" | "letter", mode: "tiled" | "poster") => void;
  onSaveGame: () => void;
  onLoadGame: (file: File) => void;
  selectMode: boolean;
  onSelectModeChange: (v: boolean) => void;
  selectionRect: { x0: number; y0: number; x1: number; y1: number } | null;
  onLockSelection: () => void;
  onUnlockSelection: () => void;
  onClearSelection: () => void;
  onLockAll: () => void;
  onUnlockAll: () => void;
  onRegenerateSelection: () => void;
  onFillSelection: () => void;
  regenerating: boolean;
  editMode: boolean;
  selectedSymbol: string;
  paintSymbols: string[];
  onEditModeChange: (edit: boolean) => void;
  onSelectedSymbolChange: (symbol: string) => void;
  onError: (message: string) => void;
}

export function ActionsPanel({
  config,
  onSaveTileMetadata,
  board,
  canUndo,
  canRedo,
  pathabilityResult,
  validationResult,
  routeQuality,
  simulationResult,
  simulating,
  onRunSimulation,
  onUndo,
  onRedo,
  onCheckPathability,
  onSaveText,
  onExportImage,
  onExportPrint,
  onSaveGame,
  onLoadGame,
  selectMode,
  onSelectModeChange,
  selectionRect,
  onLockSelection,
  onUnlockSelection,
  onClearSelection,
  onLockAll,
  onUnlockAll,
  onRegenerateSelection,
  onFillSelection,
  regenerating,
  editMode,
  selectedSymbol,
  paintSymbols,
  onEditModeChange,
  onSelectedSymbolChange,
  onError,
}: ActionsPanelProps) {
  const hasBoard = board.length > 0 && board[0].length > 0;
  const [showTileMeta, setShowTileMeta] = useState(false);
  const [tileMetaEdit, setTileMetaEdit] = useState<Record<string, TileMetadataEntry>>({});
  const loadGameInputRef = useRef<HTMLInputElement>(null);
  const decks = config?.decks ?? [];
  const emptyAssignedDecks =
    config?.tile_metadata == null
      ? []
      : decks.filter((d) => {
          const cardCount = d.card_template_ids?.length ?? 0;
          if (cardCount > 0) return false;
          return Object.values(config.tile_metadata ?? {}).some((meta) => (meta.deck_id ?? "").trim() === d.id);
        });
  useEffect(() => {
    if (config?.tile_metadata && Object.keys(config.tile_metadata).length > 0) {
      setTileMetaEdit((prev) => {
        const next = { ...config.tile_metadata };
        return Object.keys(next).length > 0 ? next : prev;
      });
    }
  }, [config?.tile_metadata, showTileMeta]);

  return (
    <div className="panel actions-panel">
      <div className="panel-title">Actions</div>
      <div className="row">
        <button type="button" onClick={onUndo} disabled={!canUndo}>
          Undo
        </button>
        <button type="button" onClick={onRedo} disabled={!canRedo}>
          Redo
        </button>
      </div>
      <div className="row">
        <button
          type="button"
          onClick={onCheckPathability}
          disabled={!hasBoard}
        >
          Check pathability
        </button>
      </div>
      {pathabilityResult !== null && (
        <div
          className="pathability-result"
          style={{
            marginTop: 4,
            padding: 6,
            borderRadius: 4,
            background: pathabilityResult.ok ? "rgba(63,185,80,0.2)" : "rgba(248,81,73,0.2)",
            fontSize: 11,
          }}
        >
          {pathabilityResult.ok
            ? "All starts can reach the goal."
            : `Unreachable start(s): ${pathabilityResult.unreachable.join(", ")}`}
        </div>
      )}
      {validationResult && (
        <div
          className="board-validation-result"
          style={{
            marginTop: 4,
            padding: 6,
            borderRadius: 4,
            background:
              validationResult.goal_count === 1 &&
              validationResult.start_count >= 1 &&
              validationResult.pathability_ok
                ? "rgba(63,185,80,0.15)"
                : "rgba(248,81,73,0.14)",
            fontSize: 11,
            color: "var(--fg-secondary)",
          }}
        >
          Starts: {validationResult.start_count} · Goals: {validationResult.goal_count}
          {validationResult.min_start_goal_distance != null && (
            <> · Min distance: {validationResult.min_start_goal_distance}</>
          )}
          {validationResult.goal_count !== 1 && <div>Board should contain exactly one goal (G).</div>}
          {validationResult.start_count < 1 && <div>Board should contain at least one start (1-4).</div>}
          {!validationResult.pathability_ok && validationResult.unreachable.length > 0 && (
            <div>Unreachable starts detected: {validationResult.unreachable.join(", ")}</div>
          )}
        </div>
      )}
      {routeQuality !== null && (
        <div
          className="route-quality"
          style={{ marginTop: 4, fontSize: 11, color: "var(--fg-secondary)" }}
        >
          {routeQuality.label}: {routeQuality.details}
        </div>
      )}
      <div className="row" style={{ marginTop: 8 }}>
        <button
          type="button"
          onClick={onRunSimulation}
          disabled={!hasBoard || simulating}
        >
          {simulating ? "Running…" : "Run simulation"}
        </button>
      </div>
      {simulationResult !== null && (
        <div
          className="simulation-result"
          style={{
            marginTop: 6,
            padding: 8,
            borderRadius: 4,
            background: "rgba(59, 130, 246, 0.15)",
            fontSize: 11,
            color: "var(--fg-secondary)",
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 4 }}>
            Expected turns: {simulationResult.expected_turns.toFixed(1)}
          </div>
          {simulationResult.turns_per_start.length > 1 && (
            <div style={{ marginBottom: 4 }}>
              Per start: {simulationResult.turns_per_start.map((t, i) => `S${i + 1}: ${t.toFixed(1)}`).join(", ")}
            </div>
          )}
          {simulationResult.penalty_spikes.length > 0 && (
            <div>
              Penalty hotspots: {simulationResult.penalty_spikes.length} tile(s)
            </div>
          )}
          <div style={{ marginTop: 4 }}>
            Turn spread: {simulationResult.turn_spread.toFixed(1)} · Hotspot count: {simulationResult.hotspot_count}
          </div>
        </div>
      )}
      <div className="row" style={{ marginTop: 8 }}>
        <button type="button" onClick={onSaveText} disabled={!hasBoard}>
          Save as text
        </button>
      </div>
      <div className="row">
        <button type="button" onClick={onExportImage} disabled={!hasBoard}>
          Export PNG
        </button>
      </div>
      <div className="row" style={{ marginTop: 6, flexWrap: "wrap", gap: 4 }}>
        <span style={{ fontSize: 10, color: "var(--fg-secondary)" }}>Print:</span>
        <button
          type="button"
          onClick={() => onExportPrint("a4", "tiled")}
          disabled={!hasBoard}
        >
          Tiled (A4)
        </button>
        <button
          type="button"
          onClick={() => onExportPrint("letter", "tiled")}
          disabled={!hasBoard}
        >
          Tiled (Letter)
        </button>
        <button
          type="button"
          onClick={() => onExportPrint("a4", "poster")}
          disabled={!hasBoard}
        >
          Poster
        </button>
      </div>
      <div className="row" style={{ marginTop: 4 }}>
        <button
          type="button"
          onClick={() =>
            exportCards({ include_back: true })
              .then((blob) => {
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "cards_print.zip";
                a.click();
                URL.revokeObjectURL(url);
              })
              .catch((e) => {
                const msg = String(e?.message ?? e).includes("501") ? "Server needs Pillow: pip install Pillow" : String(e?.message ?? e);
                onError(msg);
              })
          }
        >
          Export cards (ZIP)
        </button>
      </div>
      <div className="row" style={{ marginTop: 6 }}>
        <button type="button" onClick={onSaveGame} disabled={!hasBoard}>
          Save game
        </button>
        <input
          ref={loadGameInputRef}
          type="file"
          accept=".json"
          style={{ display: "none" }}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onLoadGame(f);
            e.target.value = "";
          }}
        />
        <button
          type="button"
          onClick={() => loadGameInputRef.current?.click()}
        >
          Load game
        </button>
      </div>

      <div className="panel-title" style={{ marginTop: 16 }}>Selection</div>
      <div className="row">
        <label style={{ minWidth: "auto" }}>
          <input
            type="checkbox"
            checked={selectMode}
            onChange={(e) => onSelectModeChange(e.target.checked)}
          />
          Select mode
        </label>
      </div>
      <div className="row" style={{ flexWrap: "wrap", gap: 4 }}>
        <button
          type="button"
          onClick={onLockSelection}
          disabled={!hasBoard || !selectionRect || regenerating}
        >
          Lock selection
        </button>
        <button
          type="button"
          onClick={onUnlockSelection}
          disabled={!hasBoard || !selectionRect || regenerating}
        >
          Unlock selection
        </button>
        <button
          type="button"
          onClick={onClearSelection}
          disabled={!selectionRect}
        >
          Clear selection
        </button>
        <button
          type="button"
          onClick={onRegenerateSelection}
          disabled={!hasBoard || !selectionRect || regenerating}
        >
          {regenerating ? "Regenerating…" : "Regen selection"}
        </button>
        <button
          type="button"
          onClick={onFillSelection}
          disabled={!hasBoard || !selectionRect || !editMode}
          title="Fill selection with current paint symbol"
        >
          Fill selection
        </button>
      </div>
      <div className="row" style={{ flexWrap: "wrap", gap: 4, marginTop: 4 }}>
        <button type="button" onClick={onLockAll} disabled={!hasBoard || regenerating}>
          Lock all
        </button>
        <button type="button" onClick={onUnlockAll} disabled={!hasBoard || regenerating}>
          Unlock all
        </button>
      </div>

      <div className="panel-title" style={{ marginTop: 16 }}>Editor</div>
      <div className="row">
        <label style={{ minWidth: "auto" }}>
          <input
            type="checkbox"
            checked={editMode}
            onChange={(e) => onEditModeChange(e.target.checked)}
          />
          Edit mode
        </label>
      </div>
      {editMode && (
        <div className="paint-palette">
          <div style={{ fontSize: 10, color: "var(--fg-secondary)", marginBottom: 4 }}>
            Click symbol then paint on board (deck in parentheses):
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {paintSymbols.map((sym) => {
              const meta = config?.tile_metadata?.[sym];
              const deck = meta?.deck_id ?? "";
              return (
                <button
                  key={sym}
                  type="button"
                  onClick={() => onSelectedSymbolChange(sym)}
                  title={deck ? `Deck: ${deck}` : undefined}
                  style={{
                    padding: "4px 8px",
                    fontWeight: selectedSymbol === sym ? "bold" : "normal",
                    border: selectedSymbol === sym ? "2px solid var(--accent)" : "1px solid var(--border)",
                  }}
                >
                  {sym}{deck ? ` (${deck})` : ""}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div className="panel-title" style={{ marginTop: 16 }}>Decks & cards</div>
      {emptyAssignedDecks.length > 0 && (
        <div style={{ fontSize: 10, color: "#fbbf24", marginBottom: 6 }}>
          {emptyAssignedDecks.length} assigned deck(s) have no cards. Play mode will draw placeholders.
        </div>
      )}
      <div className="row">
        <Link to="/decks" className="deck-builder-nav-btn" title="Create and edit decks and cards">
          Open deck builder
        </Link>
      </div>

      <div className="panel-title" style={{ marginTop: 16 }}>Tile metadata</div>
      <div className="row">
        <button type="button" onClick={() => setShowTileMeta((v) => !v)} style={{ fontSize: 11 }}>
          {showTileMeta ? "Hide" : "Edit tile metadata"}
        </button>
      </div>
      {showTileMeta && config?.tile_metadata && (
        <div style={{ marginTop: 8, fontSize: 10 }}>
          <datalist id="deck-ids">
            {decks.map((d) => (
              <option key={d.id} value={d.id} />
            ))}
          </datalist>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 60px 1fr", gap: 4, marginBottom: 4, fontWeight: 600 }}>
            <span>Symbol</span>
            <span>Category</span>
            <span>Diff</span>
            <span>Deck</span>
          </div>
          {Object.keys(config.tile_metadata)
            .sort()
            .map((sym) => (
              <div key={sym} style={{ display: "grid", gridTemplateColumns: "1fr 1fr 60px 1fr", gap: 4, marginBottom: 4, alignItems: "center" }}>
                <span>{sym}</span>
                <input
                  type="text"
                  value={tileMetaEdit[sym]?.category ?? ""}
                  onChange={(e) =>
                    setTileMetaEdit((p) => ({ ...p, [sym]: { ...p[sym], category: e.target.value } }))
                  }
                  style={{ width: "100%", padding: 2, fontSize: 10 }}
                />
                <input
                  type="number"
                  min={0}
                  max={3}
                  value={tileMetaEdit[sym]?.difficulty ?? 0}
                  onChange={(e) =>
                    setTileMetaEdit((p) => ({
                      ...p,
                      [sym]: { ...p[sym], difficulty: parseInt(e.target.value, 10) || 0 },
                    }))
                  }
                  style={{ width: "100%", padding: 2, fontSize: 10 }}
                />
                <input
                  type="text"
                  list="deck-ids"
                  value={tileMetaEdit[sym]?.deck_id ?? ""}
                  onChange={(e) =>
                    setTileMetaEdit((p) => ({ ...p, [sym]: { ...p[sym], deck_id: e.target.value } }))
                  }
                  style={{ width: "100%", padding: 2, fontSize: 10 }}
                  placeholder="deck id"
                />
              </div>
            ))}
          <button
            type="button"
            onClick={() => onSaveTileMetadata(tileMetaEdit)}
            style={{ marginTop: 8, padding: "4px 12px" }}
          >
            Save metadata
          </button>
        </div>
      )}
    </div>
  );
}
