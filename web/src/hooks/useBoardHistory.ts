import { useState, useCallback, useRef, useEffect } from "react";
import type { Board } from "../types";

export interface UseBoardHistoryOptions {
  maxUndo?: number;
  /** Called after board changes from push, undo, redo, or cell edit. */
  onAfterBoardCommit?: () => void;
}

export function useBoardHistory(options: UseBoardHistoryOptions = {}) {
  const { maxUndo = 30, onAfterBoardCommit } = options;
  const [board, setBoard] = useState<Board>([]);
  const [history, setHistory] = useState<Board[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const historyIndexRef = useRef(historyIndex);
  useEffect(() => {
    historyIndexRef.current = historyIndex;
  }, [historyIndex]);

  const notify = useCallback(() => {
    onAfterBoardCommit?.();
  }, [onAfterBoardCommit]);

  const pushBoard = useCallback(
    (newBoard: Board) => {
      setHistory((h) => {
        const next = h.slice(0, historyIndexRef.current + 1);
        next.push(newBoard.map((row) => row.slice()));
        return next.slice(-maxUndo);
      });
      setHistoryIndex((i) => Math.min(i + 1, maxUndo - 1));
      setBoard(newBoard.map((row) => row.slice()));
      notify();
    },
    [maxUndo, notify]
  );

  const undo = useCallback(() => {
    if (historyIndex <= 0) return;
    const prev = history[historyIndex - 1];
    setBoard(prev.map((row) => row.slice()));
    setHistoryIndex((i) => i - 1);
    notify();
  }, [history, historyIndex, notify]);

  const redo = useCallback(() => {
    if (historyIndex >= history.length - 1) return;
    const next = history[historyIndex + 1];
    setBoard(next.map((row) => row.slice()));
    setHistoryIndex((i) => i + 1);
    notify();
  }, [history, historyIndex, notify]);

  const handleCellEdit = useCallback(
    (row: number, col: number, symbol: string) => {
      setBoard((b) => {
        const next = b.map((r, i) => (i === row ? r.slice() : r));
        if (next[row][col] === symbol) return b;
        next[row][col] = symbol;
        const nextCopy = next.map((r) => r.slice());
        setHistory((h) => {
          const idx = historyIndexRef.current;
          const cut = h.slice(0, idx + 1);
          cut.push(nextCopy);
          return cut.slice(-maxUndo);
        });
        setHistoryIndex((i) => Math.min(i + 1, maxUndo - 1));
        notify();
        return next;
      });
    },
    [maxUndo, notify]
  );

  const resetHistory = useCallback((nextBoard: Board) => {
    setBoard(nextBoard.map((r) => r.slice()));
    setHistory([nextBoard.map((r) => r.slice())]);
    setHistoryIndex(0);
    notify();
  }, [notify]);

  return {
    board,
    setBoard,
    history,
    historyIndex,
    pushBoard,
    undo,
    redo,
    handleCellEdit,
    resetHistory,
  };
}
