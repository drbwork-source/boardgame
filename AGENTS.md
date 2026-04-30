## Cursor Cloud specific instructions

### Overview

**Board Generator Studio** — Python project with a board-centred **desktop app** ([`app.py`](app.py), launched via [`board_generator.py`](board_generator.py)), a **FastAPI** backend ([`api/`](api/)), and a **React + Vite** frontend ([`web/`](web/)). Shared generation logic lives in [`board_core.py`](board_core.py) (no UI dependencies). See [`README.md`](README.md) for full usage.

### System dependencies

- **Python 3.10+** (uses `int | None` union syntax)
- **Node.js 20+** and **npm** — for building/serving the web UI (`web/`)
- **python3-tk** (system package) — required for desktop GUI mode
- **Xvfb** — useful for headless GUI testing (`DISPLAY=:99`)
- **Pillow** — optional; better PNG/JPEG export (see [`requirements.txt`](requirements.txt))

### Running the app

- **Desktop (recommended)**: `pip install -r requirements.txt` then `python board_generator.py` (uses CustomTkinter when installed; otherwise classic Tk).
- **CLI**: `python board_generator.py --cli --seed 42 --width 20 --height 20` (see README for full flags).
- **Web API (dev)**: `python run_web.py` — API at http://localhost:8000; frontend dev server `cd web && npm install && npm run dev` → http://localhost:5173.
- **Web API (single command)**: `python board_generator.py --web` (still run Vite separately for dev).
- **Production web**: `cd web && npm run build`, then `python run_web.py` — serves built assets from `web/dist/` when present.

### Tests and CI

- **Python tests**: `pip install -r requirements.txt` then `pytest -q`
- **CI** (`.github/workflows/ci.yml`): pytest + `npm ci` / `npm run build` in `web/`

### Gotchas

- **Do not commit** `web/node_modules/`, `web/dist/`, `build/`, `dist/`, or `__pycache__/` — they are listed in [`.gitignore`](.gitignore); regenerate with npm/PyInstaller locally.
- **AGENTS.md** is the agent briefing; user-facing docs stay in **README.md**.
- For GUI testing in headless environments, start Xvfb on display `:99` before launching the desktop app.
- No project linter/formatter is configured; `ruff` is a reasonable choice if you add one.
