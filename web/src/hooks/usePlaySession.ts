import { useState, useCallback, useRef } from "react";
import {
  createPlayGame,
  rollDice,
  playMove,
  endPlayTurn,
  drawCardForTile,
} from "../api";
import { CARD_DRAW_TILE_SYMBOLS } from "../constants";
import type { Board, Config, CardTemplateEntry, PlayStateResponse } from "../types";

export function usePlaySession(
  board: Board,
  config: Config | null,
  onError?: (message: string) => void
) {
  const [playMode, setPlayMode] = useState(false);
  const [playGameId, setPlayGameId] = useState<string | null>(null);
  const [playGameState, setPlayGameState] = useState<PlayStateResponse | null>(null);
  const [playRolling, setPlayRolling] = useState(false);
  const [playEndingTurn, setPlayEndingTurn] = useState(false);
  const [playMoving, setPlayMoving] = useState(false);
  const [playLandingCell, setPlayLandingCell] = useState<{ col: number; row: number } | null>(null);
  const [playLandingTileName, setPlayLandingTileName] = useState<string | null>(null);
  const [drawnCard, setDrawnCard] = useState<CardTemplateEntry | null>(null);
  const [drawnCardTileName, setDrawnCardTileName] = useState<string | null>(null);
  const [playLandingError, setPlayLandingError] = useState<string | null>(null);
  const [tokenAnimation, setTokenAnimation] = useState<{
    from: [number, number];
    to: [number, number];
    progress: number;
  } | null>(null);
  const [playMoveHistory, setPlayMoveHistory] = useState<
    Array<{ playerIndex: number; roll?: number; to?: [number, number] }>
  >([]);
  const landingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const tokenAnimationRef = useRef<number | null>(null);

  const hasGoalAndStart = useCallback((b: Board) => {
    if (!b.length || !b[0].length) return false;
    let hasGoal = false;
    let hasStart = false;
    for (const row of b) {
      for (const cell of row) {
        if (cell === "G") hasGoal = true;
        if (cell === "1" || cell === "2" || cell === "3" || cell === "4") hasStart = true;
        if (hasGoal && hasStart) return true;
      }
    }
    return hasGoal && hasStart;
  }, []);

  const handleExitPlay = useCallback(() => {
    setPlayMode(false);
    setPlayGameId(null);
    setPlayGameState(null);
    setPlayLandingCell(null);
    setPlayLandingTileName(null);
    setTokenAnimation(null);
    setPlayMoveHistory([]);
    if (landingTimeoutRef.current) clearTimeout(landingTimeoutRef.current);
    if (tokenAnimationRef.current) cancelAnimationFrame(tokenAnimationRef.current);
  }, []);

  const handleStartPlay = useCallback(() => {
    if (!hasGoalAndStart(board)) {
      onError?.("Board needs a goal (G) and at least one start (1-4) to play.");
      return;
    }
    setPlayRolling(true);
    createPlayGame(board)
      .then((state) => {
        setPlayGameId(state.game_id ?? null);
        setPlayGameState(state);
        setPlayMode(true);
      })
      .catch((err) => {
        console.error(err);
        onError?.(err?.message ?? "Failed to start game.");
      })
      .finally(() => setPlayRolling(false));
  }, [board, hasGoalAndStart, onError]);

  const handlePlayRoll = useCallback(() => {
    if (!playGameId) return;
    setPlayRolling(true);
    rollDice(playGameId)
      .then((state) => {
        setPlayGameState(state);
        setPlayMoveHistory((h) => [
          ...h.slice(-9),
          { playerIndex: state.current_player_index, roll: state.current_roll ?? undefined },
        ]);
      })
      .catch(console.error)
      .finally(() => setPlayRolling(false));
  }, [playGameId]);

  const handlePlayMove = useCallback(
    (col: number, row: number) => {
      if (!playGameId || !playGameState) return;
      const from = playGameState.player_positions[playGameState.current_player_index] as [number, number];
      setPlayMoving(true);
      setTokenAnimation({ from: [from[0], from[1]], to: [col, row], progress: 0 });
      playMove(playGameId, col, row)
        .then((state) => {
          setPlayGameState(state);
          setPlayMoveHistory((h) => [
            ...h.slice(-9),
            { playerIndex: state.current_player_index, to: [col, row] },
          ]);
          const symbol = state.board[row]?.[col];
          const deckId = (config?.tile_metadata?.[symbol]?.deck_id ?? "").trim();
          const shouldDrawCard =
            symbol && (deckId !== "" || (!config && CARD_DRAW_TILE_SYMBOLS.has(symbol)));
          if (shouldDrawCard) {
            setPlayLandingCell({ col, row });
            const tileName = config?.tile_names?.[symbol] ?? symbol;
            setPlayLandingTileName(tileName);
            setDrawnCardTileName(tileName);
            drawCardForTile(symbol)
              .then((card) => {
                setDrawnCard(card);
                setPlayLandingTileName(null);
                if (card.id === "__placeholder") {
                  setPlayLandingError("No playable card. Add cards in Deck Builder.");
                } else {
                  setPlayLandingError(null);
                }
              })
              .catch(() => {
                setPlayLandingError("Could not draw card");
                setDrawnCard({
                  id: "__placeholder",
                  title: "Nothing happens",
                  body: "No card could be drawn for this tile.",
                  image_url: null,
                  back_text: null,
                });
                setDrawnCardTileName(tileName);
              });
          }
          const start = performance.now();
          const duration = 350;
          const tick = () => {
            const elapsed = performance.now() - start;
            const progress = Math.min(1, elapsed / duration);
            setTokenAnimation((prev) => (prev ? { ...prev, progress } : null));
            if (progress < 1) {
              tokenAnimationRef.current = requestAnimationFrame(tick);
            } else {
              setTokenAnimation(null);
              tokenAnimationRef.current = null;
              setPlayMoving(false);
            }
          };
          tokenAnimationRef.current = requestAnimationFrame(tick);
        })
        .catch(() => setPlayMoving(false));
    },
    [playGameId, playGameState, config?.tile_names, config?.tile_metadata]
  );

  const handlePlayEndTurn = useCallback(() => {
    if (!playGameId) return;
    setPlayEndingTurn(true);
    endPlayTurn(playGameId)
      .then(setPlayGameState)
      .catch(console.error)
      .finally(() => setPlayEndingTurn(false));
  }, [playGameId]);

  const handleCloseDrawnCard = useCallback(() => {
    setDrawnCard(null);
    setDrawnCardTileName(null);
    setPlayLandingCell(null);
    setPlayLandingTileName(null);
    setPlayLandingError(null);
  }, []);

  const handlePlayAgain = useCallback(() => {
    if (!board.length || !board[0].length) return;
    setPlayLandingCell(null);
    setPlayLandingTileName(null);
    setPlayLandingError(null);
    setDrawnCard(null);
    setDrawnCardTileName(null);
    setTokenAnimation(null);
    setPlayMoveHistory([]);
    createPlayGame(board)
      .then((state) => {
        setPlayGameId(state.game_id ?? null);
        setPlayGameState(state);
      })
      .catch(console.error);
  }, [board]);

  return {
    playMode,
    playGameId,
    playGameState,
    playRolling,
    playEndingTurn,
    playMoving,
    playLandingCell,
    playLandingTileName,
    drawnCard,
    drawnCardTileName,
    playLandingError,
    tokenAnimation,
    playMoveHistory,
    handleStartPlay,
    handleExitPlay,
    handlePlayRoll,
    handlePlayMove,
    handlePlayEndTurn,
    handleCloseDrawnCard,
    handlePlayAgain,
    hasGoalAndStart,
  };
}
