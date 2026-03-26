import { useState, useEffect, useCallback } from "react";
import { Routes, Route, Link } from "react-router-dom";
import { BoardCanvas } from "./components/BoardCanvas";
import { OptionsPanel } from "./components/OptionsPanel";
import { ActionsPanel } from "./components/ActionsPanel";
import { PlayPanel } from "./components/PlayPanel";
import { CardDrawModal } from "./components/CardDrawModal";
import { DeckBuilderPage } from "./pages/DeckBuilderPage";
import { usePlaySession } from "./hooks/usePlaySession";
import { useBoardStudio } from "./hooks/useBoardStudio";

export default function AppRoot() {
  const [appError, setAppError] = useState<string | null>(null);
  const reportError = useCallback((message: string) => setAppError(message), []);
  const studio = useBoardStudio(reportError);
  const play = usePlaySession(studio.board, studio.config, reportError);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) return;
      if (play.playMode && play.playGameState) {
        if (play.playGameState.winner !== null) return;
        if (e.key === " ") {
          e.preventDefault();
          if (play.playGameState.phase === "roll" && !play.playRolling) play.handlePlayRoll();
        } else if (e.key === "Enter") {
          e.preventDefault();
          if (
            (play.playGameState.phase === "roll" || play.playGameState.phase === "moving") &&
            !play.playEndingTurn
          ) {
            play.handlePlayEndTurn();
          }
        }
        return;
      }
      const ctrl = e.ctrlKey || e.metaKey;
      if (ctrl && e.key === "z") {
        e.preventDefault();
        if (e.shiftKey) studio.handleRedo();
        else studio.handleUndo();
      } else if (ctrl && e.key === "y") {
        e.preventDefault();
        studio.handleRedo();
      } else if (ctrl && e.key === "g") {
        e.preventDefault();
        if (!studio.generating) studio.handleGenerate();
      } else if (ctrl && e.key === "s") {
        e.preventDefault();
        studio.handleSaveGame();
      } else if (e.key === "e" && !ctrl) {
        e.preventDefault();
        studio.setEditMode((prev) => !prev);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [
    play.playMode,
    play.playGameState,
    play.playRolling,
    play.playEndingTurn,
    play.handlePlayRoll,
    play.handlePlayEndTurn,
    studio.handleRedo,
    studio.handleUndo,
    studio.generating,
    studio.handleGenerate,
    studio.handleSaveGame,
    studio.setEditMode,
  ]);

  return (
    <Routes>
      <Route path="/decks" element={<DeckBuilderPage />} />
      <Route
        path="/"
        element={
          <div className="app-layout">
            {play.drawnCard && (
              <CardDrawModal
                card={play.drawnCard}
                tileName={play.drawnCardTileName}
                onClose={play.handleCloseDrawnCard}
              />
            )}
            <header className="app-header">
              <h1>Board Generator Studio</h1>
              <div className="row" style={{ alignItems: "center", gap: 12 }}>
                <Link to="/decks" className="deck-builder-nav-btn" title="Create and edit decks and cards for board tiles">
                  Decks & cards
                </Link>
                <label>
                  Tile size
                  <input
                    type="range"
                    min={8}
                    max={48}
                    value={studio.tileSize}
                    onChange={(e) => studio.setTileSize(Number(e.target.value))}
                    style={{ marginLeft: 8, width: 80 }}
                  />
                  {studio.tileSize}
                </label>
                {play.playMode ? (
                  <button
                    type="button"
                    className="exit-play-btn"
                    onClick={play.handleExitPlay}
                    aria-label="Exit Play Mode and return to edit"
                  >
                    Exit Play Mode
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={play.handleStartPlay}
                    disabled={
                      !studio.board.length ||
                      !studio.board[0].length ||
                      play.playRolling ||
                      !play.hasGoalAndStart(studio.board)
                    }
                  >
                    {play.playRolling ? "Starting…" : "Play"}
                  </button>
                )}
              </div>
            </header>
            {appError && (
              <div className="app-error-banner" role="alert">
                <span>{appError}</span>
                <button type="button" className="exit-play-btn" onClick={() => setAppError(null)}>
                  Dismiss
                </button>
              </div>
            )}
            <div className="app-body">
              {!play.playMode && (
                <aside className="sidebar left">
                  <OptionsPanel
                    config={studio.config}
                    options={studio.options}
                    onOptionsChange={(o) => studio.setOptions((prev) => ({ ...prev, ...o }))}
                    onGenerate={studio.handleGenerate}
                    onLuckyBoard={studio.handleLuckyBoard}
                    generating={studio.generating}
                  />
                </aside>
              )}
              <main className="board-area">
                <BoardCanvas
                  board={play.playMode && play.playGameState ? play.playGameState.board : studio.board}
                  tileColors={studio.config?.tile_colors ?? {}}
                  tileStyles={studio.tileStyles}
                  tileSize={studio.tileSize}
                  editMode={!play.playMode && studio.editMode}
                  selectMode={!play.playMode && studio.selectMode}
                  selectedSymbol={studio.selectedSymbol}
                  selectionRect={studio.selectionRect}
                  heatmap={!play.playMode ? studio.simulationResult?.heatmap ?? null : null}
                  penaltySpikes={!play.playMode ? studio.simulationResult?.penalty_spikes ?? null : null}
                  playMode={play.playMode}
                  playerPositions={play.playGameState?.player_positions ?? []}
                  currentPlayerIndex={play.playGameState?.current_player_index ?? 0}
                  validMoves={play.playGameState?.valid_moves ?? []}
                  highlightCell={play.playMode ? play.playLandingCell : null}
                  tokenAnimation={play.playMode ? play.tokenAnimation : null}
                  onPlayCellClick={play.playMoving ? undefined : play.handlePlayMove}
                  onCellEdit={studio.handleCellEdit}
                  onSelectionChange={studio.handleSelectionChange}
                />
              </main>
              <aside className="sidebar right">
                {play.playMode ? (
                  <PlayPanel
                    gameState={play.playGameState}
                    onRoll={play.handlePlayRoll}
                    onEndTurn={play.handlePlayEndTurn}
                    onPlayAgain={play.handlePlayAgain}
                    rolling={play.playRolling}
                    endingTurn={play.playEndingTurn}
                    landingToast={play.playLandingTileName}
                    landingToastError={play.playLandingError}
                    moveHistory={play.playMoveHistory}
                  />
                ) : (
                  <ActionsPanel
                    config={studio.config}
                    onSaveTileMetadata={studio.handleSaveTileMetadata}
                    board={studio.board}
                    canUndo={studio.historyIndex > 0}
                    canRedo={studio.historyIndex < studio.history.length - 1 && studio.history.length > 0}
                    pathabilityResult={studio.pathabilityResult}
                    validationResult={studio.validationResult}
                    routeQuality={studio.routeQuality}
                    simulationResult={studio.simulationResult}
                    simulating={studio.simulating}
                    onRunSimulation={studio.handleRunSimulation}
                    onUndo={studio.handleUndo}
                    onRedo={studio.handleRedo}
                    onCheckPathability={studio.handleCheckPathability}
                    onSaveText={studio.handleSaveText}
                    onExportImage={studio.handleExportImage}
                    onExportPrint={studio.handleExportPrint}
                    onSaveGame={studio.handleSaveGame}
                    onLoadGame={studio.handleLoadGame}
                    selectMode={studio.selectMode}
                    onSelectModeChange={studio.setSelectMode}
                    selectionRect={studio.selectionRect}
                    onLockSelection={studio.handleLockSelection}
                    onUnlockSelection={studio.handleUnlockSelection}
                    onClearSelection={studio.handleClearSelection}
                    onLockAll={studio.handleLockAll}
                    onUnlockAll={studio.handleUnlockAll}
                    onRegenerateSelection={studio.handleRegenerateSelection}
                    regenerating={studio.regenerating}
                    onFillSelection={studio.handleFillSelection}
                    editMode={studio.editMode}
                    selectedSymbol={studio.selectedSymbol}
                    paintSymbols={studio.paintSymbols}
                    onEditModeChange={studio.setEditMode}
                    onSelectedSymbolChange={studio.setSelectedSymbol}
                    onError={reportError}
                  />
                )}
              </aside>
            </div>
          </div>
        }
      />
    </Routes>
  );
}
