import { useState, useEffect, useCallback, useRef } from "react";
import { Link } from "react-router-dom";
import { getConfig, listDecks, createDeck, deleteDeck, importDecksFromFile, patchTileMetadata } from "../api";
import type { Config, DeckEntry, TileMetadataEntry } from "../types";
import { CardBuilder } from "../components/CardBuilder";

function getTilesForDeck(config: Config | null, deckId: string): string[] {
  if (!config?.tile_metadata) return [];
  return Object.entries(config.tile_metadata)
    .filter(([, meta]) => meta.deck_id === deckId)
    .map(([sym]) => sym);
}

export function DeckBuilderPage() {
  const [config, setConfig] = useState<Config | null>(null);
  const [decks, setDecks] = useState<DeckEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDeckId, setSelectedDeckId] = useState<string | null>(null);
  const [newDeckName, setNewDeckName] = useState("");
  const [creating, setCreating] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importMessage, setImportMessage] = useState<string | null>(null);
  const [importError, setImportError] = useState(false);
  const [tileMetaEdit, setTileMetaEdit] = useState<Record<string, TileMetadataEntry>>({});
  const [showTileTypes, setShowTileTypes] = useState(false);
  const [savingTileMeta, setSavingTileMeta] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);
  const importInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (config?.tile_metadata && Object.keys(config.tile_metadata).length > 0) {
      setTileMetaEdit({ ...config.tile_metadata });
    }
  }, [config?.tile_metadata]);

  const loadData = useCallback(() => {
    setLoading(true);
    return Promise.all([getConfig(), listDecks()])
      .then(([c, d]) => {
        setConfig(c);
        setDecks(d);
        setPageError(null);
      })
      .catch((err) => {
        console.error(err);
        setPageError(err?.message ?? "Could not load decks.");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Auto-select single deck so user goes straight to editing
  useEffect(() => {
    if (loading || decks.length === 0) return;
    if (decks.length === 1 && !selectedDeckId) {
      setSelectedDeckId(decks[0].id);
    }
  }, [loading, decks, selectedDeckId]);

  const handleCreateDeck = () => {
    const name = newDeckName.trim();
    if (!name) return;
    setCreating(true);
    createDeck(name)
      .then((deck) => {
        setNewDeckName("");
        setSelectedDeckId(deck.id);
        loadData();
      })
      .catch((err) => {
        console.error(err);
        setPageError(err?.message ?? "Could not create deck.");
      })
      .finally(() => setCreating(false));
  };

  const handleDeleteDeck = (e: React.MouseEvent, deckId: string, deckName: string) => {
    e.stopPropagation();
    if (!confirm(`Delete deck "${deckName}"?`)) return;
    deleteDeck(deckId)
      .then(() => {
        if (selectedDeckId === deckId) setSelectedDeckId(null);
        loadData();
      })
      .catch((err) => {
        console.error(err);
        setPageError(err?.message ?? "Could not delete deck.");
      });
  };

  const handleImportClick = () => {
    setImportMessage(null);
    setImportError(false);
    importInputRef.current?.click();
  };

  const handleImportFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setImporting(true);
    setImportMessage(null);
    setImportError(false);
    importDecksFromFile(file)
      .then((result) => {
        const parts = [];
        if (result.decks_created > 0) parts.push(`${result.decks_created} deck(s) created`);
        if (result.decks_updated > 0) parts.push(`${result.decks_updated} deck(s) updated`);
        if (result.cards_created > 0) parts.push(`${result.cards_created} card(s) added`);
        setImportMessage(parts.length ? parts.join(", ") : "Import complete.");
        setImportError(false);
        loadData();
      })
      .catch((err) => {
        setImportMessage(err?.message ?? "Import failed.");
        setImportError(true);
      })
      .finally(() => setImporting(false));
  };

  const selectedDeck = selectedDeckId ? decks.find((d) => d.id === selectedDeckId) : null;

  const handleSaveTileMetadata = () => {
    setSavingTileMeta(true);
    patchTileMetadata(tileMetaEdit)
      .then(() => loadData())
      .catch((err) => {
        console.error(err);
        setPageError(err?.message ?? "Could not save tile assignments.");
      })
      .finally(() => setSavingTileMeta(false));
  };

  if (loading) {
    return (
      <div className="app-layout" style={{ padding: 24 }}>
        <div style={{ color: "var(--fg-secondary)" }}>Loading…</div>
      </div>
    );
  }

  const emptyAssignedDecks = decks.filter((deck) => {
    const count = deck.card_template_ids?.length ?? 0;
    return count === 0 && getTilesForDeck(config, deck.id).length > 0;
  });

  return (
    <div className="app-layout deck-builder-page" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <header className="app-header" style={{ flexShrink: 0 }}>
        <h1 style={{ margin: 0 }}>Deck Builder</h1>
        <div className="row" style={{ alignItems: "center", gap: 12 }}>
          <Link to="/" className="deck-builder-back-link">
            ← Back to Board
          </Link>
        </div>
      </header>
      {pageError && (
        <div className="app-error-banner" role="alert" style={{ margin: "8px 16px 0" }}>
          <span>{pageError}</span>
          <button type="button" className="exit-play-btn" onClick={() => setPageError(null)}>
            Dismiss
          </button>
        </div>
      )}
      {emptyAssignedDecks.length > 0 && (
        <div className="app-warning-banner" role="status" style={{ margin: "8px 16px 0" }}>
          Assigned deck(s) with no cards:{" "}
          {emptyAssignedDecks
            .map((deck) => {
              const tiles = getTilesForDeck(config, deck.id)
                .map((s) => config?.tile_names?.[s] ?? s)
                .join(", ");
              return `${deck.name} (${tiles})`;
            })
            .join(" | ")}
          . Add at least one card to avoid placeholder draws.
        </div>
      )}
      <div style={{ flex: 1, display: "flex", overflow: "hidden", gap: 16, padding: 16 }}>
        <aside className="deck-builder-sidebar">
          <div className="deck-builder-sidebar-header">
            <strong>Decks</strong>
          </div>
          <div className="deck-builder-new-deck">
            <input
              type="text"
              placeholder="New deck name…"
              value={newDeckName}
              onChange={(e) => setNewDeckName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreateDeck()}
              disabled={creating}
              aria-label="New deck name"
            />
            <button
              type="button"
              onClick={handleCreateDeck}
              disabled={creating || !newDeckName.trim()}
              className="deck-builder-add-btn"
            >
              {creating ? "…" : "Add"}
            </button>
          </div>
          <div className="deck-builder-import-row">
            <input
              ref={importInputRef}
              type="file"
              accept=".csv,.xlsx"
              onChange={handleImportFile}
              style={{ display: "none" }}
              aria-label="Import file"
            />
            <button
              type="button"
              onClick={handleImportClick}
              disabled={importing}
              className="deck-builder-import-btn"
              title="Upload CSV or Excel with columns: Deck, Title, Body, Image URL, Back text"
            >
              {importing ? "Importing…" : "Import from file"}
            </button>
          </div>
          {importMessage && (
            <p className={`deck-builder-import-message ${importError ? "error" : "success"}`}>
              {importMessage}
            </p>
          )}
          <p style={{ marginTop: 8, marginBottom: 0, fontSize: 11, color: "var(--fg-secondary)" }}>
            Decks need at least one card to draw a non-placeholder card in Play mode.
          </p>
          <div style={{ marginTop: 12 }}>
            <button
              type="button"
              onClick={() => setShowTileTypes((v) => !v)}
              style={{ fontSize: 12, fontWeight: 600 }}
            >
              {showTileTypes ? "Hide" : "Show"} tile types (assign decks)
            </button>
          </div>
          {showTileTypes && config?.tile_metadata && (
            <div style={{ marginTop: 8, fontSize: 11 }}>
              <p style={{ marginBottom: 6, color: "var(--fg-secondary)" }}>
                Assign a deck to each tile type. When a player lands on that tile in Play mode, they draw a random card from the assigned deck.
              </p>
              <datalist id="deck-ids-deckbuilder">
                {decks.map((d) => (
                  <option key={d.id} value={d.id} />
                ))}
              </datalist>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 4, marginBottom: 4, fontWeight: 600 }}>
                <span>Tile</span>
                <span>Deck</span>
              </div>
              {Object.keys(config.tile_metadata)
                .sort()
                .map((sym) => (
                  <div
                    key={sym}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 2fr",
                      gap: 4,
                      marginBottom: 4,
                      alignItems: "center",
                    }}
                  >
                    <span title={config?.tile_names?.[sym] ?? sym}>
                      {sym} ({config?.tile_names?.[sym] ?? sym})
                    </span>
                    <input
                      type="text"
                      list="deck-ids-deckbuilder"
                      value={tileMetaEdit[sym]?.deck_id ?? ""}
                      onChange={(e) =>
                        setTileMetaEdit((p) => ({
                          ...p,
                          [sym]: { ...p[sym], deck_id: e.target.value },
                        }))
                      }
                      style={{ width: "100%", padding: 4, fontSize: 11 }}
                      placeholder="deck id"
                    />
                  </div>
                ))}
              <button
                type="button"
                onClick={handleSaveTileMetadata}
                disabled={savingTileMeta}
                style={{ marginTop: 8, padding: "6px 12px", fontSize: 11 }}
              >
                {savingTileMeta ? "Saving…" : "Save tile assignments"}
              </button>
            </div>
          )}
          {decks.length === 0 ? (
            <p className="deck-builder-empty-hint">
              Create a deck above, then assign it to tile types in <strong>Tile metadata</strong> on the board page.
            </p>
          ) : (
            <ul className="deck-builder-list">
              {decks.map((d) => {
                const tiles = getTilesForDeck(config, d.id);
                const isSelected = selectedDeckId === d.id;
                const cardCount = d.card_template_ids?.length ?? 0;
                return (
                  <li key={d.id}>
                    <button
                      type="button"
                      className={`deck-builder-deck-row ${isSelected ? "selected" : ""}`}
                      onClick={() => setSelectedDeckId(d.id)}
                    >
                      <span className="deck-builder-deck-name">{d.name}</span>
                      <span className="deck-builder-deck-meta">
                        {cardCount} card{cardCount !== 1 ? "s" : ""}
                        {tiles.length > 0 &&
                          ` · ${tiles.map((s) => config?.tile_names?.[s] ?? s).join(", ")}`}
                      </span>
                    </button>
                    <button
                      type="button"
                      className="deck-builder-delete-btn"
                      onClick={(e) => handleDeleteDeck(e, d.id, d.name)}
                      title={`Delete ${d.name}`}
                      aria-label={`Delete ${d.name}`}
                    >
                      Delete
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </aside>
        <main className="deck-builder-main">
          {selectedDeck ? (
            <div className="deck-builder-card-panel">
              <CardBuilder
                deck={selectedDeck}
                onClose={() => setSelectedDeckId(null)}
                onDeckUpdated={loadData}
                standalone
              />
            </div>
          ) : (
            <div className="deck-builder-empty-state">
              <p>Click a deck on the left to edit its cards.</p>
              <p className="deck-builder-empty-state-hint">Or create a new deck using the field above.</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
