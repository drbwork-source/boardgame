import type { Config, GenerateOptions } from "../types";

interface OptionsPanelProps {
  config: Config | null;
  options: GenerateOptions;
  onOptionsChange: (o: Partial<GenerateOptions>) => void;
  onGenerate: () => void;
  onLuckyBoard: () => void;
  generating: boolean;
}

export function OptionsPanel({
  config,
  options,
  onOptionsChange,
  onGenerate,
  onLuckyBoard,
  generating,
}: OptionsPanelProps) {
  const presets = config?.board_presets ?? [];
  const tilesets = config ? Object.keys(config.tileset_presets) : [];
  const minSize = config?.board_size_min ?? 5;
  const maxSize = config?.board_size_max ?? 100;

  const setTileset = (name: string) => {
    const weights = config?.tileset_presets[name];
    if (weights) onOptionsChange({ ...options, terrain_weights: { ...weights } });
  };

  return (
    <div className="panel options-panel">
      <div className="panel-title">Size</div>
      <div className="row">
        <label>Width</label>
        <input
          type="number"
          min={minSize}
          max={maxSize}
          value={options.width}
          onChange={(e) =>
            onOptionsChange({ ...options, width: parseInt(e.target.value, 10) || minSize })
          }
          style={{ width: 60 }}
        />
      </div>
      <div className="row">
        <label>Height</label>
        <input
          type="number"
          min={minSize}
          max={maxSize}
          value={options.height}
          onChange={(e) =>
            onOptionsChange({ ...options, height: parseInt(e.target.value, 10) || minSize })
          }
          style={{ width: 60 }}
        />
      </div>
      <div className="row" style={{ flexWrap: "wrap", gap: 4 }}>
        {presets.map(([w, h]) => (
          <button
            key={`${w}x${h}`}
            type="button"
            onClick={() => onOptionsChange({ ...options, width: w, height: h })}
            style={{ padding: "4px 8px", fontSize: 10 }}
          >
            {w}×{h}
          </button>
        ))}
      </div>

      <div className="panel-title" style={{ marginTop: 12 }}>Generation</div>
      <div className="row">
        <label>Tileset</label>
        <select
          onChange={(e) => setTileset(e.target.value)}
          value={
            tilesets.find(
              (t) =>
                JSON.stringify(config?.tileset_presets[t]) ===
                JSON.stringify(options.terrain_weights)
            ) ?? ""
          }
          style={{ minWidth: 140 }}
        >
          {tilesets.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>
      <div className="row">
        <label>Seed</label>
        <input
          type="number"
          placeholder="random"
          value={options.seed ?? ""}
          onChange={(e) => {
            const v = e.target.value.trim();
            onOptionsChange({
              ...options,
              seed: v === "" ? null : parseInt(v, 10) || null,
            });
          }}
          style={{ width: 80 }}
        />
      </div>
      <div className="row">
        <label>Symmetry</label>
        <select
          value={options.symmetry}
          onChange={(e) => onOptionsChange({ ...options, symmetry: e.target.value })}
          style={{ minWidth: 100 }}
        >
          {(config?.symmetry_choices ?? ["none", "horizontal", "vertical", "both"]).map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>
      <div className="row">
        <label>Mode</label>
        <select
          value={options.generation_mode}
          onChange={(e) => onOptionsChange({ ...options, generation_mode: e.target.value })}
          style={{ minWidth: 120 }}
        >
          {(config?.generation_mode_choices ?? ["grid", "pathboard"]).map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>
      <div className="row">
        <label>Smoothing</label>
        <input
          type="number"
          min={0}
          value={options.smoothing_passes}
          onChange={(e) =>
            onOptionsChange({
              ...options,
              smoothing_passes: parseInt(e.target.value, 10) || 0,
            })
          }
          style={{ width: 50 }}
        />
      </div>
      <div className="row">
        <label>Cluster</label>
        <input
          type="number"
          min={0}
          max={1}
          step={0.1}
          value={options.cluster_bias}
          onChange={(e) =>
            onOptionsChange({
              ...options,
              cluster_bias: parseFloat(e.target.value) || 0,
            })
          }
          style={{ width: 50 }}
        />
      </div>
      <div className="row">
        <label>Starts</label>
        <select
          value={options.num_starts}
          onChange={(e) =>
            onOptionsChange({ ...options, num_starts: parseInt(e.target.value, 10) })
          }
        >
          {[1, 2, 3, 4].map((n) => (
            <option key={n} value={n}>{n}</option>
          ))}
        </select>
      </div>
      <div className="row">
        <label>Goal</label>
        <select
          value={options.goal_placement}
          onChange={(e) =>
            onOptionsChange({ ...options, goal_placement: e.target.value })}
          style={{ minWidth: 90 }}
        >
          {(config?.goal_placement_choices ?? ["center", "random"]).map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>
      <div className="row">
        <label>Start pos</label>
        <select
          value={options.start_placement}
          onChange={(e) =>
            onOptionsChange({ ...options, start_placement: e.target.value })}
          style={{ minWidth: 90 }}
        >
          {(config?.start_placement_choices ?? ["corners", "random"]).map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>
      <div className="row">
        <label>Min dist</label>
        <input
          type="number"
          min={0}
          value={options.min_goal_distance}
          onChange={(e) =>
            onOptionsChange({
              ...options,
              min_goal_distance: parseInt(e.target.value, 10) || 0,
            })
          }
          style={{ width: 50 }}
          title="Minimum steps from start to goal"
        />
      </div>
      <div className="row">
        <label>Safe r</label>
        <input
          type="number"
          min={0}
          value={options.safe_segment_radius}
          onChange={(e) =>
            onOptionsChange({
              ...options,
              safe_segment_radius: parseInt(e.target.value, 10) || 0,
            })
          }
          style={{ width: 50 }}
          title="Radius of safe tiles around starts/goal"
        />
      </div>
      <div className="row">
        <label>Checkpoints</label>
        <input
          type="number"
          min={0}
          value={options.num_checkpoints}
          onChange={(e) =>
            onOptionsChange({
              ...options,
              num_checkpoints: parseInt(e.target.value, 10) || 0,
            })
          }
          style={{ width: 50 }}
        />
      </div>
      <div className="row" style={{ marginTop: 8, gap: 8, flexWrap: "wrap" }}>
        <button
          type="button"
          onClick={onGenerate}
          disabled={generating}
          style={{ flex: 1, minWidth: 80 }}
        >
          {generating ? "Generating…" : "Generate"}
        </button>
        <button
          type="button"
          onClick={onLuckyBoard}
          disabled={generating}
          style={{ flex: 1, minWidth: 80 }}
          title="Generate until route is short/easy or medium"
        >
          Lucky board
        </button>
      </div>
    </div>
  );
}
