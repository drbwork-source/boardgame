import React, { useRef, useEffect, useCallback, useMemo } from "react";
import type { Board } from "../types";

export type SelectionRect = { x0: number; y0: number; x1: number; y1: number } | null;

/** Heatmap cell from simulation (x, y = col, row). */
export type HeatmapCell = { x: number; y: number; count: number };

/** Player token colors (match PlayPanel). */
const PLAYER_COLORS = ["#DC2626", "#2563EB", "#16A34A", "#9333EA"];

interface BoardCanvasProps {
  board: Board;
  tileColors: Record<string, string>;
  tileStyles: Record<string, { glyph: string }>;
  tileSize: number;
  editMode: boolean;
  selectMode: boolean;
  selectedSymbol: string;
  selectionRect: SelectionRect;
  /** Optional heatmap from simulation: overlay visit counts. */
  heatmap?: HeatmapCell[] | null;
  /** Optional penalty spike cells [x,y] to highlight. */
  penaltySpikes?: number[][] | null;
  /** Play mode: token positions and valid move cells (each [col, row]). */
  playMode?: boolean;
  playerPositions?: number[][];
  currentPlayerIndex?: number;
  validMoves?: number[][];
  /** Cell to highlight (e.g. landed on non-standard tile). */
  highlightCell?: { col: number; row: number } | null;
  /** Token move animation: from, to [col, row], progress 0..1. */
  tokenAnimation?: { from: [number, number]; to: [number, number]; progress: number } | null;
  onPlayCellClick?: (col: number, row: number) => void;
  onCellEdit?: (row: number, col: number, symbol: string) => void;
  onSelectionChange?: (x0: number, y0: number, x1: number, y1: number) => void;
}

export function BoardCanvas({
  board,
  tileColors,
  tileStyles,
  tileSize,
  editMode,
  selectMode,
  selectedSymbol,
  selectionRect,
  heatmap,
  penaltySpikes,
  playMode = false,
  playerPositions = [],
  currentPlayerIndex = 0,
  validMoves = [],
  highlightCell = null,
  tokenAnimation = null,
  onPlayCellClick,
  onCellEdit,
  onSelectionChange,
}: BoardCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const isDrawing = useRef(false);
  const selectStart = useRef<{ col: number; row: number } | null>(null);
  const [pulsePhase, setPulsePhase] = React.useState(0);
  React.useEffect(() => {
    if (!playMode || tokenAnimation) return;
    const id = setInterval(() => setPulsePhase((p) => (p + 0.08) % 1), 50);
    return () => clearInterval(id);
  }, [playMode, tokenAnimation]);

  const heatmapMaxCount = useMemo(
    () => (heatmap?.length ? Math.max(...heatmap.map((c) => c.count), 1) : 1),
    [heatmap]
  );

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !board.length || !board[0].length) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const w = board[0].length * tileSize;
    const h = board.length * tileSize;
    canvas.width = w;
    canvas.height = h;
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
    if (heatmap?.length) {
      for (const { x, y, count } of heatmap) {
        if (y >= 0 && y < board.length && x >= 0 && x < board[0].length) {
          const alpha = 0.15 + 0.35 * (count / heatmapMaxCount);
          ctx.fillStyle = `rgba(59, 130, 246, ${alpha})`;
          ctx.fillRect(x * tileSize, y * tileSize, tileSize, tileSize);
        }
      }
    }
    if (penaltySpikes?.length) {
      for (const [px, py] of penaltySpikes) {
        if (py >= 0 && py < board.length && px >= 0 && px < board[0].length) {
          ctx.strokeStyle = "rgba(239, 68, 68, 0.9)";
          ctx.lineWidth = 2;
          ctx.strokeRect(px * tileSize, py * tileSize, tileSize, tileSize);
          ctx.fillStyle = "rgba(239, 68, 68, 0.2)";
          ctx.fillRect(px * tileSize, py * tileSize, tileSize, tileSize);
        }
      }
    }
    if (selectionRect && !playMode) {
      const { x0, y0, x1, y1 } = selectionRect;
      const left = Math.min(x0, x1) * tileSize;
      const top = Math.min(y0, y1) * tileSize;
      const width = (Math.abs(x1 - x0) + 1) * tileSize;
      const height = (Math.abs(y1 - y0) + 1) * tileSize;
      ctx.strokeStyle = "rgba(59, 130, 246, 0.9)";
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 4]);
      ctx.strokeRect(left, top, width, height);
      ctx.setLineDash([]);
      ctx.fillStyle = "rgba(59, 130, 246, 0.15)";
      ctx.fillRect(left, top, width, height);
    }
    if (highlightCell) {
      const { col: hc, row: hr } = highlightCell;
      if (hr >= 0 && hr < board.length && hc >= 0 && hc < board[0].length) {
        ctx.fillStyle = "rgba(234, 179, 8, 0.4)";
        ctx.fillRect(hc * tileSize, hr * tileSize, tileSize, tileSize);
        ctx.strokeStyle = "rgba(234, 179, 8, 0.95)";
        ctx.lineWidth = 3;
        ctx.strokeRect(hc * tileSize, hr * tileSize, tileSize, tileSize);
      }
    }
    if (playMode && validMoves.length > 0) {
      for (const [col, row] of validMoves) {
        if (row >= 0 && row < board.length && col >= 0 && col < board[0].length) {
          ctx.fillStyle = "rgba(34, 197, 94, 0.35)";
          ctx.fillRect(col * tileSize, row * tileSize, tileSize, tileSize);
          ctx.strokeStyle = "rgba(34, 197, 94, 0.9)";
          ctx.lineWidth = 2;
          ctx.strokeRect(col * tileSize, row * tileSize, tileSize, tileSize);
        }
      }
    }
    const radius = Math.max(4, tileSize * 0.35);
    const animatingPlayerIndex = tokenAnimation ? currentPlayerIndex : -1;
    if (playMode && playerPositions.length > 0) {
      for (let i = 0; i < playerPositions.length; i++) {
        const isAnimating = i === animatingPlayerIndex && tokenAnimation;
        let cx: number;
        let cy: number;
        if (isAnimating && tokenAnimation) {
          const [fromCol, fromRow] = tokenAnimation.from;
          const [toCol, toRow] = tokenAnimation.to;
          const t = tokenAnimation.progress;
          const ease = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
          cx = (fromCol + (toCol - fromCol) * ease) * tileSize + tileSize / 2;
          cy = (fromRow + (toRow - fromRow) * ease) * tileSize + tileSize / 2;
        } else {
          const [col, row] = playerPositions[i];
          if (row < 0 || row >= board.length || col < 0 || col >= board[0].length) continue;
          cx = col * tileSize + tileSize / 2;
          cy = row * tileSize + tileSize / 2;
        }
        const color = PLAYER_COLORS[i % PLAYER_COLORS.length];
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx.fill();
        if (i === currentPlayerIndex) {
          ctx.strokeStyle = "#FACC15";
          ctx.lineWidth = 2;
          ctx.stroke();
          const pulseOpacity = 0.25 + 0.15 * Math.sin(pulsePhase * Math.PI * 2);
          ctx.strokeStyle = `rgba(250, 204, 21, ${pulseOpacity})`;
          ctx.lineWidth = 3;
          ctx.beginPath();
          ctx.arc(cx, cy, radius + 3, 0, Math.PI * 2);
          ctx.stroke();
        }
        ctx.fillStyle = "#fff";
        ctx.font = `${Math.max(10, tileSize * 0.5)}px system-ui, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(String(i + 1), cx, cy);
      }
    }
  }, [
    board,
    tileColors,
    tileStyles,
    tileSize,
    selectionRect,
    heatmap,
    heatmapMaxCount,
    penaltySpikes,
    playMode,
    playerPositions,
    currentPlayerIndex,
    validMoves,
    highlightCell,
    tokenAnimation,
    pulsePhase,
  ]);

  useEffect(() => {
    draw();
  }, [draw]);

  const getCell = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current;
      if (!canvas || !board.length || !board[0].length) return null;
      const rect = canvas.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return null;
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;
      const x = Math.floor(((e.clientX - rect.left) * scaleX) / tileSize);
      const y = Math.floor(((e.clientY - rect.top) * scaleY) / tileSize);
      if (y >= 0 && y < board.length && x >= 0 && x < board[0].length) return { row: y, col: x };
      return null;
    },
    [board.length, board[0]?.length, tileSize]
  );

  const getCellFromClientCoords = useCallback(
    (clientX: number, clientY: number) => {
      const canvas = canvasRef.current;
      if (!canvas || !board.length || !board[0].length) return null;
      const rect = canvas.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return null;
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;
      let x = Math.floor(((clientX - rect.left) * scaleX) / tileSize);
      let y = Math.floor(((clientY - rect.top) * scaleY) / tileSize);
      const maxCol = board[0].length - 1;
      const maxRow = board.length - 1;
      x = Math.max(0, Math.min(maxCol, x));
      y = Math.max(0, Math.min(maxRow, y));
      return { row: y, col: x };
    },
    [board.length, board[0]?.length, tileSize]
  );

  const isValidMove = useCallback(
    (col: number, row: number) =>
      validMoves.some(([c, r]) => c === col && r === row),
    [validMoves]
  );

  const handlePointerDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const cell = getCell(e);
    if (!cell) return;
    if (playMode && onPlayCellClick && isValidMove(cell.col, cell.row)) {
      e.preventDefault();
      onPlayCellClick(cell.col, cell.row);
      return;
    }
    if (!playMode && editMode && onCellEdit) {
      e.preventDefault();
      isDrawing.current = true;
      onCellEdit(cell.row, cell.col, selectedSymbol);
      return;
    }
    if (!playMode && selectMode && onSelectionChange) {
      e.preventDefault();
      selectStart.current = { col: cell.col, row: cell.row };
      const onWindowMouseUp = (up: MouseEvent) => {
        window.removeEventListener("mouseup", onWindowMouseUp);
        if (!selectStart.current) return;
        const endCell = getCellFromClientCoords(up.clientX, up.clientY);
        if (endCell) {
          const { col: c0, row: r0 } = selectStart.current;
          onSelectionChange(c0, r0, endCell.col, endCell.row);
        }
        selectStart.current = null;
      };
      window.addEventListener("mouseup", onWindowMouseUp);
    }
  };

  const handlePointerMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing.current || !editMode || !onCellEdit) return;
    const cell = getCell(e);
    if (cell) onCellEdit(cell.row, cell.col, selectedSymbol);
  };

  const handlePointerUp = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!editMode && selectMode && selectStart.current && onSelectionChange) {
      const cell = getCell(e);
      if (cell) {
        const { col: c0, row: r0 } = selectStart.current;
        onSelectionChange(c0, r0, cell.col, cell.row);
      }
      selectStart.current = null;
    }
    isDrawing.current = false;
  };

  const handlePointerLeave = () => {
    isDrawing.current = false;
  };

  if (!board.length || !board[0].length) {
    return (
      <div className="board-placeholder">
        Set size and click Generate to create a board.
      </div>
    );
  }

  return (
    <canvas
      ref={canvasRef}
      onMouseDown={handlePointerDown}
      onMouseMove={handlePointerMove}
      onMouseUp={handlePointerUp}
      onMouseLeave={handlePointerLeave}
      style={{
        cursor: playMode
          ? validMoves.length > 0
            ? "pointer"
            : "default"
          : editMode
            ? "crosshair"
            : selectMode
              ? "crosshair"
              : "default",
        maxWidth: "100%",
        height: "auto",
      }}
    />
  );
}
