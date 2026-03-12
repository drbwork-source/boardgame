import { useState, useEffect, useCallback } from "react";
import { getConfig, generateBoard as apiGenerate, generateBalancedBoard, checkPathability, getRouteQuality, getBoardText, exportBoardImage, exportPrint, runSimulation, exportGame, importGame, regenerate, patchTileMetadata } from "./api";
import type { Config, Board, GenerateOptions, SimulateResponse, GameSaveData } from "./types";
import { BoardCanvas } from "./components/BoardCanvas";
import { OptionsPanel } from "./components/OptionsPanel";
import { ActionsPanel } from "./components/ActionsPanel";

const MAX_UNDO = 30;
const DEFAULT_OPTIONS: GenerateOptions = {
  width: 50,
  height: 50,
  seed: null,
  terrain_weights: {},
  symmetry: "none",
  smoothing_passes: 1,
  cluster_bias: 0.2,
  num_starts: 4,
  goal_placement: "center",
  start_placement: "corners",
  min_goal_distance: 0,
  safe_segment_radius: 0,
  num_checkpoints: 0,
};

function App() {
  const [config, setConfig] = useState<Config | null>(null);
  const [board, setBoard] = useState<Board>([]);
  const [history, setHistory] = useState<Board[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [options, setOptions] = useState<GenerateOptions>(DEFAULT_OPTIONS);
  const [tileSize, setTileSize] = useState(20);
  const [generating, setGenerating] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [selectedSymbol, setSelectedSymbol] = useState(".");
  const [pathabilityResult, setPathabilityResult] = useState<{ ok: boolean; unreachable: number[] } | null>(null);
  const [routeQuality, setRouteQuality] = useState<{ label: string; details: string } | null>(null);
  const [simulationResult, setSimulationResult] = useState<SimulateResponse | null>(null);
  const [simulating, setSimulating] = useState(false);
  const [selectMode, setSelectMode] = useState(false);
  const [selectionRect, setSelectionRect] = useState<{ x0: number; y0: number; x1: number; y1: number } | null>(null);
  const [lockedMask, setLockedMask] = useState<boolean[][] | null>(null);
  const [regenerating, setRegenerating] = useState(false);

  useEffect(() => {
    if (!board.length || !board[0].length) return;
    const h = board.length;
    const w = board[0].length;
    setLockedMask((prev) => {
      if (!prev || prev.length !== h || prev[0].length !== w) {
        return Array(h)
          .fill(null)
          .map(() => Array(w).fill(false));
      }
      return prev;
    });
    setSelectionRect(null);
  }, [board.length, board[0]?.length]);

  useEffect(() => {
    getConfig()
      .then((c) => {
        setConfig(c);
        setOptions((o) => {
          if (Object.keys(o.terrain_weights).length === 0 && c.tileset_presets["Classic"]) {
            return { ...o, terrain_weights: { ...c.tileset_presets["Classic"] } };
          }
          return o;
        });
      })
      .catch(console.error);
  }, []);

  const pushBoard = useCallback((newBoard: Board) => {
    setHistory((h) => {
      const next = h.slice(0, historyIndex + 1);
      next.push(newBoard.map((row) => row.slice()));
      return next.slice(-MAX_UNDO);
    });
    setHistoryIndex((i) => Math.min(i + 1, MAX_UNDO - 1));
    setBoard(newBoard.map((row) => row.slice()));
    setPathabilityResult(null);
    setRouteQuality(null);
    setSimulationResult(null);
  }, [historyIndex]);

  const handleGenerate = useCallback(() => {
    setGenerating(true);
    apiGenerate(options)
      .then((res) => {
        pushBoard(res.board);
        const b = res.board;
        checkPathability(b).then(setPathabilityResult).catch(console.error);
        getRouteQuality(b).then(setRouteQuality).catch(console.error);
      })
      .catch(console.error)
      .finally(() => setGenerating(false));
  }, [options, pushBoard]);

  const handleLuckyBoard = useCallback(() => {
    setGenerating(true);
    generateBalancedBoard(options, "short/easy", 50)
      .then((res) => {
        pushBoard(res.board);
        const b = res.board;
        checkPathability(b).then(setPathabilityResult).catch(console.error);
        getRouteQuality(b).then(setRouteQuality).catch(console.error);
      })
      .catch(console.error)
      .finally(() => setGenerating(false));
  }, [options, pushBoard]);

  const handleUndo = useCallback(() => {
    if (historyIndex <= 0) return;
    const prev = history[historyIndex - 1];
    setBoard(prev.map((row) => row.slice()));
    setHistoryIndex((i) => i - 1);
    setPathabilityResult(null);
    setRouteQuality(null);
    setSimulationResult(null);
  }, [history, historyIndex]);

  const handleRedo = useCallback(() => {
    if (historyIndex >= history.length - 1) return;
    const next = history[historyIndex + 1];
    setBoard(next.map((row) => row.slice()));
    setHistoryIndex((i) => i + 1);
    setPathabilityResult(null);
    setRouteQuality(null);
    setSimulationResult(null);
  }, [history, historyIndex]);

  const handleCellEdit = useCallback(
    (row: number, col: number, symbol: string) => {
      setBoard((b) => {
        const next = b.map((r, i) => (i === row ? r.slice() : r));
        if (next[row][col] === symbol) return b;
        next[row][col] = symbol;
        setHistory((h) => {
          const cut = h.slice(0, historyIndex + 1);
          cut.push(next.map((r) => r.slice()));
          return cut.slice(-MAX_UNDO);
        });
        setHistoryIndex((i) => Math.min(i + 1, MAX_UNDO - 1));
setPathabilityResult(null);
    setRouteQuality(null);
        setSimulationResult(null);
        return next;
      });
    },
    [historyIndex]
  );

  const handleCheckPathability = useCallback(() => {
    checkPathability(board).then(setPathabilityResult).catch(console.error);
    getRouteQuality(board).then(setRouteQuality).catch(console.error);
  }, [board]);

  const handleRunSimulation = useCallback(() => {
    setSimulating(true);
    runSimulation(board)
      .then(setSimulationResult)
      .catch(console.error)
      .finally(() => setSimulating(false));
  }, [board]);

  const handleSelectionChange = useCallback((x0: number, y0: number, x1: number, y1: number) => {
    setSelectionRect({ x0, y0, x1, y1 });
  }, []);

  const handleLockSelection = useCallback(() => {
    if (!selectionRect || !lockedMask || !board.length || !board[0].length) return;
    const { x0, y0, x1, y1 } = selectionRect;
    const xMin = Math.min(x0, x1);
    const xMax = Math.max(x0, x1);
    const yMin = Math.min(y0, y1);
    const yMax = Math.max(y0, y1);
    setLockedMask((prev) => {
      if (!prev) return prev;
      const next = prev.map((row) => row.slice());
      for (let y = yMin; y <= yMax; y++) {
        for (let x = xMin; x <= xMax; x++) {
          if (y < next.length && x < next[y].length) next[y][x] = true;
        }
      }
      return next;
    });
  }, [selectionRect, lockedMask, board.length, board[0]?.length]);

  const handleUnlockSelection = useCallback(() => {
    if (!selectionRect || !lockedMask) return;
    const { x0, y0, x1, y1 } = selectionRect;
    const xMin = Math.min(x0, x1);
    const xMax = Math.max(x0, x1);
    const yMin = Math.min(y0, y1);
    const yMax = Math.max(y0, y1);
    setLockedMask((prev) => {
      if (!prev) return prev;
      const next = prev.map((row) => row.slice());
      for (let y = yMin; y <= yMax; y++) {
        for (let x = xMin; x <= xMax; x++) {
          if (y < next.length && x < next[y].length) next[y][x] = false;
        }
      }
      return next;
    });
  }, [selectionRect, lockedMask]);

  const handleRegenerateSelection = useCallback(() => {
    if (!selectionRect || !board.length || !board[0].length || !lockedMask) return;
    setRegenerating(true);
    const [x0, y0, x1, y1] = [
      Math.min(selectionRect.x0, selectionRect.x1),
      Math.min(selectionRect.y0, selectionRect.y1),
      Math.max(selectionRect.x0, selectionRect.x1),
      Math.max(selectionRect.y0, selectionRect.y1),
    ];
    regenerate({
      board,
      options,
      selection_rect: [x0, y0, x1, y1],
      locked_mask: lockedMask,
      regenerate_selection_only: true,
    })
      .then((res) => {
        pushBoard(res.board);
        checkPathability(res.board).then(setPathabilityResult).catch(console.error);
        getRouteQuality(res.board).then(setRouteQuality).catch(console.error);
      })
      .catch(console.error)
      .finally(() => setRegenerating(false));
  }, [board, options, selectionRect, lockedMask, pushBoard]);

  const handleSaveText = useCallback(() => {
    getBoardText(board)
      .then((res) => {
        const blob = new Blob([res.text], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "board.txt";
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch(console.error);
  }, [board]);

  const handleExportImage = useCallback(() => {
    exportBoardImage(board, tileSize)
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "board.png";
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch(console.error);
  }, [board, tileSize]);

  const handleExportPrint = useCallback(
    (paper: "a4" | "letter", mode: "tiled" | "poster") => {
      exportPrint(board, { paper, mode })
        .then((blob) => {
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = mode === "poster" ? "board_poster.png" : "board_print.zip";
          a.click();
          URL.revokeObjectURL(url);
        })
        .catch(console.error);
    },
    [board]
  );

  const handleSaveGame = useCallback(() => {
    exportGame(board, options, lockedMask)
      .then((data) => {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "board_game.json";
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch(console.error);
  }, [board, options, lockedMask]);

  const handleLoadGame = useCallback(
    (file: File) => {
      const reader = new FileReader();
      reader.onload = () => {
        try {
          const data = JSON.parse(reader.result as string) as GameSaveData;
          if (!data.board || !Array.isArray(data.board)) {
            throw new Error("Invalid or missing board in file");
          }
          importGame(data)
            .then((res) => {
              setBoard(res.board.map((r) => r.slice()));
              if (res.options) setOptions((prev) => ({ ...prev, ...res.options }));
              if (res.locked_mask && res.locked_mask.length === res.board.length && res.locked_mask[0]?.length === res.board[0]?.length) {
                setLockedMask(res.locked_mask.map((row) => row.slice()));
              }
              setHistory([res.board.map((r) => r.slice())]);
              setHistoryIndex(0);
              setSimulationResult(null);
              checkPathability(res.board).then(setPathabilityResult).catch(console.error);
              getRouteQuality(res.board).then(setRouteQuality).catch(console.error);
            })
            .catch(console.error);
        } catch (e) {
          console.error(e);
        }
      };
      reader.readAsText(file);
    },
    []
  );

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) return;
      const ctrl = e.ctrlKey || e.metaKey;
      if (ctrl && e.key === "z") {
        e.preventDefault();
        if (e.shiftKey) handleRedo();
        else handleUndo();
      } else if (ctrl && e.key === "y") {
        e.preventDefault();
        handleRedo();
      } else if (ctrl && e.key === "g") {
        e.preventDefault();
        if (!generating) handleGenerate();
      } else if (ctrl && e.key === "s") {
        e.preventDefault();
        handleSaveGame();
      } else if (e.key === "e" && !ctrl) {
        e.preventDefault();
        setEditMode((prev) => !prev);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleUndo, handleRedo, handleGenerate, handleSaveGame, generating]);

  const handleSaveTileMetadata = useCallback(
    (updates: Record<string, { category?: string; difficulty?: number; deck_id?: string }>) => {
      patchTileMetadata(updates)
        .then(() => getConfig().then(setConfig).catch(console.error))
        .catch(console.error);
    },
    []
  );

  const paintSymbols = config ? Object.keys(config.tile_colors) : [];

  const tileStyles = config
    ? Object.fromEntries(
        Object.entries(config.tile_styles).map(([k, v]) => [k, { glyph: v.glyph }])
      )
    : {};

  return (
    <div className="app-layout">
      <header className="app-header">
        <h1>Board Generator Studio</h1>
        <div className="row" style={{ alignItems: "center", gap: 12 }}>
          <label>
            Tile size
            <input
              type="range"
              min={8}
              max={48}
              value={tileSize}
              onChange={(e) => setTileSize(Number(e.target.value))}
              style={{ marginLeft: 8, width: 80 }}
            />
            {tileSize}
          </label>
        </div>
      </header>
      <div className="app-body">
        <aside className="sidebar left">
          <OptionsPanel
            config={config}
            options={options}
            onOptionsChange={(o) => setOptions((prev) => ({ ...prev, ...o }))}
            onGenerate={handleGenerate}
            onLuckyBoard={handleLuckyBoard}
            generating={generating}
          />
        </aside>
        <main className="board-area">
          <BoardCanvas
            board={board}
            tileColors={config?.tile_colors ?? {}}
            tileStyles={tileStyles}
            tileSize={tileSize}
            editMode={editMode}
            selectMode={selectMode}
            selectedSymbol={selectedSymbol}
            selectionRect={selectionRect}
            onCellEdit={handleCellEdit}
            onSelectionChange={handleSelectionChange}
          />
        </main>
        <aside className="sidebar right">
          <ActionsPanel
            config={config}
            onSaveTileMetadata={handleSaveTileMetadata}
            board={board}
            canUndo={historyIndex > 0}
            canRedo={historyIndex < history.length - 1 && history.length > 0}
            pathabilityResult={pathabilityResult}
            routeQuality={routeQuality}
            simulationResult={simulationResult}
            simulating={simulating}
            onRunSimulation={handleRunSimulation}
            onUndo={handleUndo}
            onRedo={handleRedo}
            onCheckPathability={handleCheckPathability}
            onSaveText={handleSaveText}
            onExportImage={handleExportImage}
            onExportPrint={handleExportPrint}
            onSaveGame={handleSaveGame}
            onLoadGame={handleLoadGame}
            selectMode={selectMode}
            onSelectModeChange={setSelectMode}
            selectionRect={selectionRect}
            onLockSelection={handleLockSelection}
            onUnlockSelection={handleUnlockSelection}
            onRegenerateSelection={handleRegenerateSelection}
            regenerating={regenerating}
            editMode={editMode}
            selectedSymbol={selectedSymbol}
            paintSymbols={paintSymbols}
            onEditModeChange={setEditMode}
            onSelectedSymbolChange={setSelectedSymbol}
          />
        </aside>
      </div>
    </div>
  );
}

export default App;
