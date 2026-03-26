import { useState, useEffect, useCallback, useMemo } from "react";
import {
  getConfig,
  generateBoard as apiGenerate,
  generateBalancedBoard,
  boardAnalysis,
  getBoardText,
  exportBoardImageClientSide,
  exportPrint,
  runSimulation,
  exportGame,
  importGame,
  regenerate,
  patchTileMetadata,
} from "../api";
import type { Config, Board, GenerateOptions, GameSaveData, SimulateResponse } from "../types";
import { useBoardHistory } from "./useBoardHistory";
import { applyToSelectionRect } from "../utils/selection";

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

export function useBoardStudio(onError: (message: string) => void) {
  const [config, setConfig] = useState<Config | null>(null);
  const [options, setOptions] = useState<GenerateOptions>(DEFAULT_OPTIONS);
  const [tileSize, setTileSize] = useState(20);
  const [generating, setGenerating] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [selectedSymbol, setSelectedSymbol] = useState(".");
  const [pathabilityResult, setPathabilityResult] = useState<{ ok: boolean; unreachable: number[] } | null>(null);
  const [validationResult, setValidationResult] = useState<{
    goal_count: number;
    start_count: number;
    pathability_ok: boolean;
    unreachable: number[];
    min_start_goal_distance: number | null;
  } | null>(null);
  const [routeQuality, setRouteQuality] = useState<{ label: string; details: string } | null>(null);
  const [simulationResult, setSimulationResult] = useState<SimulateResponse | null>(null);
  const [simulating, setSimulating] = useState(false);
  const [selectMode, setSelectMode] = useState(false);
  const [selectionRect, setSelectionRect] = useState<{ x0: number; y0: number; x1: number; y1: number } | null>(
    null
  );
  const [lockedMask, setLockedMask] = useState<boolean[][] | null>(null);
  const [regenerating, setRegenerating] = useState(false);

  const clearAnalysis = useCallback(() => {
    setPathabilityResult(null);
    setValidationResult(null);
    setRouteQuality(null);
    setSimulationResult(null);
  }, []);

  const {
    board,
    history,
    historyIndex,
    pushBoard,
    undo: handleUndo,
    redo: handleRedo,
    handleCellEdit,
    resetHistory,
  } = useBoardHistory({ maxUndo: MAX_UNDO, onAfterBoardCommit: clearAnalysis });

  const refreshBoardAnalysis = useCallback(
    (b: Board) => {
      boardAnalysis(b)
        .then(({ pathability, routeQuality: rq, validation }) => {
          setPathabilityResult(pathability);
          setValidationResult(validation);
          setRouteQuality(rq);
        })
        .catch((err) => {
          console.error(err);
          onError(err?.message ?? "Could not analyze board.");
        });
    },
    [onError]
  );

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
      .catch((err) => {
        console.error(err);
        onError(err?.message ?? "Could not load app config.");
      });
  }, [onError]);

  const paintSymbols = useMemo(() => (config ? Object.keys(config.tile_colors) : []), [config]);

  const tileStyles = useMemo(
    () =>
      config
        ? Object.fromEntries(Object.entries(config.tile_styles).map(([k, v]) => [k, { glyph: v.glyph }]))
        : {},
    [config]
  );

  const handleGenerate = useCallback(() => {
    setGenerating(true);
    apiGenerate(options)
      .then((res) => {
        pushBoard(res.board);
        refreshBoardAnalysis(res.board);
      })
      .catch((err) => {
        console.error(err);
        onError(err?.message ?? "Board generation failed.");
      })
      .finally(() => setGenerating(false));
  }, [onError, options, pushBoard, refreshBoardAnalysis]);

  const handleLuckyBoard = useCallback(() => {
    setGenerating(true);
    generateBalancedBoard(options, "short/easy", 50)
      .then((res) => {
        pushBoard(res.board);
        refreshBoardAnalysis(res.board);
      })
      .catch((err) => {
        console.error(err);
        onError(err?.message ?? "Lucky board generation failed.");
      })
      .finally(() => setGenerating(false));
  }, [onError, options, pushBoard, refreshBoardAnalysis]);

  const handleCheckPathability = useCallback(() => {
    refreshBoardAnalysis(board);
  }, [board, refreshBoardAnalysis]);

  const handleRunSimulation = useCallback(() => {
    setSimulating(true);
    runSimulation(board)
      .then(setSimulationResult)
      .catch((err) => {
        console.error(err);
        onError(err?.message ?? "Simulation failed.");
      })
      .finally(() => setSimulating(false));
  }, [board, onError]);

  const handleSelectionChange = useCallback((x0: number, y0: number, x1: number, y1: number) => {
    setSelectionRect({ x0, y0, x1, y1 });
  }, []);

  const handleLockSelection = useCallback(() => {
    if (!selectionRect || !lockedMask || !board.length || !board[0].length) return;
    const next = applyToSelectionRect(selectionRect, lockedMask, true);
    if (next) setLockedMask(next);
  }, [selectionRect, lockedMask, board.length, board[0]?.length]);

  const handleUnlockSelection = useCallback(() => {
    if (!selectionRect || !lockedMask) return;
    const next = applyToSelectionRect(selectionRect, lockedMask, false);
    if (next) setLockedMask(next);
  }, [selectionRect, lockedMask]);

  const handleClearSelection = useCallback(() => {
    setSelectionRect(null);
  }, []);

  const handleLockAll = useCallback(() => {
    if (!lockedMask) return;
    setLockedMask(lockedMask.map((row) => row.map(() => true)));
  }, [lockedMask]);

  const handleUnlockAll = useCallback(() => {
    if (!lockedMask) return;
    setLockedMask(lockedMask.map((row) => row.map(() => false)));
  }, [lockedMask]);

  const handleFillSelection = useCallback(() => {
    if (!selectionRect || !board.length || !board[0].length) return;
    const xMin = Math.min(selectionRect.x0, selectionRect.x1);
    const xMax = Math.max(selectionRect.x0, selectionRect.x1);
    const yMin = Math.min(selectionRect.y0, selectionRect.y1);
    const yMax = Math.max(selectionRect.y0, selectionRect.y1);
    const next = board.map((row, y) =>
      row.map((cell, x) => (x >= xMin && x <= xMax && y >= yMin && y <= yMax ? selectedSymbol : cell))
    );
    pushBoard(next);
  }, [board, selectionRect, selectedSymbol, pushBoard]);

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
        refreshBoardAnalysis(res.board);
      })
      .catch((err) => {
        console.error(err);
        onError(err?.message ?? "Selection regeneration failed.");
      })
      .finally(() => setRegenerating(false));
  }, [board, onError, options, selectionRect, lockedMask, pushBoard, refreshBoardAnalysis]);

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
      .catch((err) => {
        console.error(err);
        onError(err?.message ?? "Could not save board text.");
      });
  }, [board, onError]);

  const handleExportImage = useCallback(() => {
    const colors = config?.tile_colors ?? {};
    exportBoardImageClientSide(board, colors, tileStyles, tileSize)
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "board.png";
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch((err) => {
        console.error(err);
        onError(err?.message ?? "Could not export image.");
      });
  }, [board, tileSize, config?.tile_colors, tileStyles, onError]);

  const handleExportPrint = useCallback(
    (paper: "a4" | "letter", mode: "tiled" | "poster") => {
      if (mode === "poster") {
        const colors = config?.tile_colors ?? {};
        exportBoardImageClientSide(board, colors, tileStyles, 24)
          .then((blob) => {
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "board_poster.png";
            a.click();
            URL.revokeObjectURL(url);
          })
          .catch((err) => {
            console.error(err);
            onError(err?.message ?? "Poster export failed.");
          });
        return;
      }
      exportPrint(board, { paper, mode })
        .then((blob) => {
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = "board_print.zip";
          a.click();
          URL.revokeObjectURL(url);
        })
        .catch((err) => {
          console.error(err);
          const raw = err?.message ?? String(err);
          const msg =
            raw.includes("501") || raw.includes("Pillow")
              ? "Tiled print requires the server to have Pillow installed. Run: pip install Pillow"
              : raw || "Print export failed.";
          onError(msg);
        });
    },
    [board, config?.tile_colors, tileStyles, onError]
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
      .catch((err) => {
        console.error(err);
        onError(err?.message ?? "Could not save game.");
      });
  }, [board, options, lockedMask, onError]);

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
              resetHistory(res.board);
              if (res.options) setOptions((prev) => ({ ...prev, ...res.options }));
              if (
                res.locked_mask &&
                res.locked_mask.length === res.board.length &&
                res.locked_mask[0]?.length === res.board[0]?.length
              ) {
                setLockedMask(res.locked_mask.map((row) => row.slice()));
              }
              setSimulationResult(null);
              refreshBoardAnalysis(res.board);
            })
            .catch((err) => {
              console.error(err);
              onError(err?.message ?? "Could not load game.");
            });
        } catch (e) {
          console.error(e);
          onError("Invalid game file.");
        }
      };
      reader.readAsText(file);
    },
    [resetHistory, refreshBoardAnalysis, onError]
  );

  const handleSaveTileMetadata = useCallback(
    (updates: Record<string, { category?: string; difficulty?: number; deck_id?: string }>) => {
      patchTileMetadata(updates)
        .then(() =>
          getConfig()
            .then(setConfig)
            .catch((err) => {
              console.error(err);
              onError(err?.message ?? "Saved metadata, but could not refresh config.");
            })
        )
        .catch((err) => {
          console.error(err);
          onError(err?.message ?? "Could not save tile metadata.");
        });
    },
    [onError]
  );

  return {
    config,
    setConfig,
    options,
    setOptions,
    tileSize,
    setTileSize,
    generating,
    editMode,
    setEditMode,
    selectedSymbol,
    setSelectedSymbol,
    pathabilityResult,
    validationResult,
    routeQuality,
    simulationResult,
    simulating,
    selectMode,
    setSelectMode,
    selectionRect,
    lockedMask,
    regenerating,
    board,
    history,
    historyIndex,
    paintSymbols,
    tileStyles,
    handleUndo,
    handleRedo,
    handleCellEdit,
    handleGenerate,
    handleLuckyBoard,
    handleCheckPathability,
    handleRunSimulation,
    handleSelectionChange,
    handleLockSelection,
    handleUnlockSelection,
    handleClearSelection,
    handleLockAll,
    handleUnlockAll,
    handleFillSelection,
    handleRegenerateSelection,
    handleSaveText,
    handleExportImage,
    handleExportPrint,
    handleSaveGame,
    handleLoadGame,
    handleSaveTileMetadata,
  };
}
