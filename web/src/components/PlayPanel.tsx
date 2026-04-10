import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import type { PlayStateResponse } from "../types";
import { isSoundEnabled, setSoundEnabled, playDiceRoll, playWin, playLandOnSpecial } from "../utils/sound";

interface PlayPanelProps {
  gameState: PlayStateResponse | null;
  onRoll: () => void;
  onEndTurn: () => void;
  onPlayAgain: () => void;
  rolling?: boolean;
  endingTurn?: boolean;
  landingToast?: string | null;
  /** Shown with the landing toast when card draw failed (e.g. deck empty). */
  landingToastError?: string | null;
  moveHistory?: Array<{ playerIndex: number; roll?: number; to?: [number, number] }>;
}

const PLAYER_COLORS = ["#DC2626", "#2563EB", "#16A34A", "#9333EA"];
const DICE_REVEAL_MS = 700;
const DICE_CYCLE_MS = 80;
const POPUP_DURATION_MS = 2000;

export function PlayPanel({
  gameState,
  onRoll,
  onEndTurn,
  onPlayAgain,
  rolling = false,
  endingTurn = false,
  landingToast = null,
  landingToastError = null,
  moveHistory = [],
}: PlayPanelProps) {
  const [diceDisplayValue, setDiceDisplayValue] = useState<number | null>(null);
  const [diceAnimating, setDiceAnimating] = useState(false);
  const [showDicePopup, setShowDicePopup] = useState(false);
  const [showWinnerPopup, setShowWinnerPopup] = useState(false);
  const [soundOn, setSoundOn] = useState(isSoundEnabled);
  const prevRollingRef = useRef(false);
  const prevWinnerRef = useRef<number | null>(null);
  const dicePopupTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const winnerPopupTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const toggleSound = () => {
    const next = !soundOn;
    setSoundOn(next);
    setSoundEnabled(next);
  };

  useEffect(() => {
    if (!rolling && prevRollingRef.current && gameState?.phase === "moving" && gameState.current_roll != null) {
      prevRollingRef.current = false;
      const target = gameState.current_roll;
      playDiceRoll();
      setDiceAnimating(true);
      setDiceDisplayValue(target);
      setShowDicePopup(true);
      if (dicePopupTimeoutRef.current) clearTimeout(dicePopupTimeoutRef.current);
      dicePopupTimeoutRef.current = setTimeout(() => {
        setShowDicePopup(false);
        dicePopupTimeoutRef.current = null;
      }, POPUP_DURATION_MS);
      const interval = setInterval(() => {
        setDiceDisplayValue(() => Math.floor(Math.random() * 6) + 1);
      }, DICE_CYCLE_MS);
      const timeout = setTimeout(() => {
        clearInterval(interval);
        setDiceDisplayValue(target);
        setDiceAnimating(false);
      }, DICE_REVEAL_MS);
      return () => {
        clearInterval(interval);
        clearTimeout(timeout);
        /* Do not clear popupTimeoutRef here: the 2s hide must run. Clearing it when
           deps change (e.g. phase/current_roll) would prevent the popup from vanishing. */
      };
    }
    prevRollingRef.current = rolling;
  }, [rolling, gameState?.phase, gameState?.current_roll]);

  useEffect(() => {
    if (!gameState) return;
    if (gameState.winner !== null && gameState.winner !== prevWinnerRef.current) {
      prevWinnerRef.current = gameState.winner;
      playWin();
      setShowWinnerPopup(true);
      if (winnerPopupTimeoutRef.current) clearTimeout(winnerPopupTimeoutRef.current);
      winnerPopupTimeoutRef.current = setTimeout(() => {
        setShowWinnerPopup(false);
        winnerPopupTimeoutRef.current = null;
      }, POPUP_DURATION_MS);
    }
    if (gameState.winner == null) {
      prevWinnerRef.current = null;
      setShowWinnerPopup(false);
      if (winnerPopupTimeoutRef.current) clearTimeout(winnerPopupTimeoutRef.current);
    }
  }, [gameState?.winner, gameState]);

  useEffect(() => {
    if (landingToast && soundOn) playLandOnSpecial();
  }, [landingToast]);

  /* Hide dice popup when turn ends (phase back to roll) so it doesn't linger into next turn */
  useEffect(() => {
    if (gameState?.phase === "roll") {
      setShowDicePopup(false);
      if (dicePopupTimeoutRef.current) {
        clearTimeout(dicePopupTimeoutRef.current);
        dicePopupTimeoutRef.current = null;
      }
    }
  }, [gameState?.phase]);

  useEffect(() => {
    return () => {
      if (dicePopupTimeoutRef.current) clearTimeout(dicePopupTimeoutRef.current);
      if (winnerPopupTimeoutRef.current) clearTimeout(winnerPopupTimeoutRef.current);
    };
  }, []);

  if (!gameState) {
    return (
      <div className="panel play-panel">
        <div className="panel-title">Play</div>
        <p style={{ fontSize: 12, color: "var(--fg-secondary)" }}>
          Start a game from the board area.
        </p>
      </div>
    );
  }

  const { phase, current_roll, remaining_steps, current_player_index, winner, num_players } = gameState;
  const canRoll = phase === "roll" && winner === null;
  const canEndTurn = (phase === "moving" || phase === "roll") && winner === null;
  const diceValue = diceAnimating ? diceDisplayValue : current_roll;

  const overlay =
    showDicePopup && diceValue != null ? (
      <div className="play-popup-overlay play-popup-overlay--dice" role="presentation">
        <div
          className={`play-popup play-popup--dice ${diceAnimating ? "dice-rolling" : ""}`}
          aria-live="polite"
          aria-atomic="true"
          aria-label={`Rolled ${diceValue}`}
        >
          <span className="play-popup__label">Rolled</span>
          <span className="play-popup__value">{diceValue}</span>
        </div>
      </div>
    ) : showWinnerPopup && winner !== null ? (
      <div
        className="play-popup-overlay play-popup-overlay--winner"
        role="alert"
        aria-live="assertive"
        aria-label={`Player ${winner + 1} wins!`}
      >
        <div className="play-popup play-popup--winner winner-reveal">
          <div className="play-popup__title">Player {winner + 1} wins!</div>
        </div>
      </div>
    ) : landingToast ? (
      <div className="play-popup-overlay play-popup-overlay--landing" role="status" aria-live="polite">
        <div className="play-popup play-popup--landing play-landing-toast">
          Landed on {landingToast}!{landingToastError && (
            <span className="play-landing-toast-error"> {landingToastError}</span>
          )}
        </div>
      </div>
    ) : null;

  return (
    <>
      {typeof document !== "undefined" && overlay && createPortal(overlay, document.body)}
      <div className="panel play-panel">
        <div className="panel-title">Play</div>

        {landingToast && (
          <div className="play-panel-toast" role="status" aria-live="polite">
            Landed on {landingToast}!{landingToastError && (
              <span className="play-landing-toast-error"> {landingToastError}</span>
            )}
          </div>
        )}

        {winner !== null ? (
          <div
            className="winner-reveal"
            style={{
              marginTop: 8,
              padding: 12,
              borderRadius: 8,
              background: "rgba(234, 179, 8, 0.2)",
              border: "1px solid rgba(234, 179, 8, 0.5)",
            }}
          >
            <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 8 }}>
              Player {winner + 1} wins!
            </div>
            <button type="button" onClick={onPlayAgain} className="primary">
              Play again
            </button>
          </div>
        ) : (
          <>
            <div
              className="turn-indicator"
              style={{
                marginTop: 6,
                fontSize: 12,
                color: PLAYER_COLORS[current_player_index % PLAYER_COLORS.length],
                fontWeight: 600,
              }}
            >
              Player {current_player_index + 1}&apos;s turn
            </div>

            <div className="row" style={{ marginTop: 8, gap: 8, flexWrap: "wrap" }}>
              <button
                type="button"
                onClick={onRoll}
                disabled={!canRoll || rolling}
                aria-label="Roll dice"
              >
                {rolling || diceAnimating ? "Rolling…" : "Roll dice"}
              </button>
              <button
                type="button"
                onClick={onEndTurn}
                disabled={!canEndTurn || endingTurn}
                aria-label="End turn"
              >
                {endingTurn ? "…" : "End turn"}
              </button>
              <button
                type="button"
                onClick={toggleSound}
                className="exit-play-btn"
                style={{ marginLeft: "auto" }}
                aria-label={soundOn ? "Sound on" : "Sound off"}
                title={soundOn ? "Sound on" : "Sound off"}
              >
                {soundOn ? "🔊" : "🔇"}
              </button>
            </div>

            {current_roll !== null && (
              <div
                className="play-panel-dice"
                style={{
                  marginTop: 10,
                  padding: "12px 16px",
                  borderRadius: 8,
                  background: "var(--bg-panel)",
                  border: "1px solid var(--border)",
                  display: "inline-block",
                }}
                aria-live="polite"
                aria-label={`Rolled ${current_roll}`}
              >
                <span style={{ fontSize: 11, color: "var(--fg-secondary)", marginRight: 8 }}>
                  Rolled
                </span>
                <span style={{ fontSize: 24, fontWeight: 700 }}>{current_roll}</span>
              </div>
            )}

            {phase === "moving" && remaining_steps >= 0 && (
              <div style={{ marginTop: 8, fontSize: 12, color: "var(--fg-secondary)" }}>
                Moves left: {remaining_steps}
              </div>
            )}

            {moveHistory.length > 0 && (
              <div className="play-move-history" style={{ marginTop: 10, fontSize: 10, color: "var(--fg-secondary)" }}>
                {moveHistory.slice(-5).map((entry, i) => (
                  <div key={i}>
                    {entry.roll != null && `P${entry.playerIndex + 1} rolled ${entry.roll}`}
                    {entry.to != null && `P${entry.playerIndex + 1} → (${entry.to[0]}, ${entry.to[1]})`}
                  </div>
                ))}
              </div>
            )}

            <div style={{ marginTop: 12, fontSize: 11, color: "var(--fg-secondary)" }}>
              Players: {num_players} · Reach the goal to win
            </div>
          </>
        )}
      </div>
    </>
  );
}
