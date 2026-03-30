# boardgame

A **board-centred desktop app** for generating random board layouts. The application is built around the board canvas: the grid is the visual focus, with compact side panels for settings and actions.

## Desktop app (recommended)

Install the optional UI dependency for the modern interface:

```bash
pip install -r requirements.txt
python board_generator.py
```

Running with no arguments opens the app. If **CustomTkinter** is installed, you get a modern dark-themed UI with the board in the centre and slim sidebars; otherwise the classic Tkinter UI is used.

You can:
- **Customise board size**: width and height (5–100) via spinboxes, plus one-click presets: **10×10**, **25×25**, **50×50**, **75×75**
- switch generation mode between classic **grid** and **pathboard** (single start/end with intertwined route choices)
- set optional seed
- tune terrain weights
- apply symmetry, smoothing, and clustering
- generate new boards repeatedly
- save the generated board to a text file
- edit tiles directly in an editor mode (paint specific symbols where you want them)
- export the board preview to PNG or JPEG image files

This fixes the "console opens then closes" problem for desktop usage.

### Keyboard shortcut (Windows)

To open the **Web UI** with a hotkey:

1. **One-time setup** — create a Desktop shortcut and assign a shortcut key:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/create_shortcut.ps1
   ```
   This creates **Board Generator Studio** on your Desktop and assigns **Ctrl+Alt+G** by default.

2. Press **Ctrl+Alt+G** (or double-click the shortcut) to launch the Web UI. The API starts in the background and your browser opens to http://localhost:8000.

The first time you run it, the batch file may build the frontend (`npm run build` in `web/`) if needed. Ensure Node.js and npm are installed for that.

To use a different shortcut key, run:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/create_shortcut.ps1 -ShortcutKey "Ctrl+Alt+B"
   ```
   You can also right-click the shortcut → **Properties** → **Shortcut key** to change or clear it.

- **launch_board_studio.bat** — launches the Web UI (API + browser).
- **launch_desktop_app.bat** — launches the original desktop app (CustomTkinter) if you prefer that.

## Web UI

A modern web interface is available: React SPA frontend + FastAPI backend that reuses the same board logic.

**Backend (API)** — from the project root:

```bash
pip install -r requirements.txt
python run_web.py
```

This starts the API at **http://localhost:8000**. Open the API docs at http://localhost:8000/docs.

**Frontend (dev)** — in a second terminal:

```bash
cd web
npm install
npm run dev
```

Then open **http://localhost:5173** in your browser. The Vite dev server proxies `/api` to the backend.

**Single command (API only):**

```bash
python board_generator.py --web
```

This starts the API server; run the frontend separately with `cd web && npm run dev` and open http://localhost:5173.

**Production:** Build the frontend (`cd web && npm run build`), then run `python run_web.py`. The API serves the built files at the root; open http://localhost:8000.

## Known limitations

- In Play mode, landing on terrain tiles triggers a card draw from the tile's assigned deck.
- If the assigned deck has no cards, the app shows a placeholder card message instead of a real card.
- Populate decks via Deck Builder (or CSV/XLSX import) to get full card draw behavior.

## CLI mode (optional)

```bash
python board_generator.py --cli --seed 42 --symmetry horizontal --output board.txt
```

### CLI options
- `--cli`: run in terminal mode instead of GUI
- `--width`, `--height`: board size (each 5–100)
- `--seed`: deterministic generation
- `--tileset`: preset name (e.g. `Classic`, `Archipelago`, `Desert Frontier`, `Volcanic`); overrides `--weights` when set
- `--weights`: terrain weights, e.g. `.:0.65,F:0.17,M:0.10,W:0.08` (ignored if `--tileset` is set)
- `--symmetry`: `none`, `horizontal`, `vertical`, `both`
- `--generation-mode`: `grid` or `pathboard`
- `--smoothing`: neighborhood smoothing passes
- `--cluster-bias`: value from `0.0` to `1.0`
- `--output`: file path to save the board text
- `--quiet`: only print the board; no route/pathability messages (exit code 1 if any start cannot reach the goal)

Run `python board_generator.py --cli --help` for the full list of options.

## Programmatic usage

```python
from board_generator import BoardOptions, generate_board, board_to_string

options = BoardOptions(width=50, height=50, seed=None)
board = generate_board(options)
print(board_to_string(board))
```

## Planning next features

See [`IDEAS.md`](IDEAS.md) for a structured roadmap of feature ideas focused on pathing, tile rules, card decks, balancing, and print/table usability.
