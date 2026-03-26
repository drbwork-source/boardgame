## Cursor Cloud specific instructions

### Overview

Board Generator Studio — a procedural board-game map generator with three interfaces:
- **Web UI**: React/Vite frontend + FastAPI backend (primary dev workflow)
- **Desktop app**: CustomTkinter GUI (`python board_generator.py`)
- **CLI mode**: `python board_generator.py --cli`

See `README.md` for full usage details.

### Running services (Web UI — primary)

1. **Backend API** (FastAPI on port 8000):
   ```
   python3 run_web.py
   ```
2. **Frontend dev server** (Vite on port 5173, proxies `/api` to backend):
   ```
   cd web && npm run dev
   ```
   Open http://localhost:5173 in a browser.

### Running tests

```
python3 -m pytest tests/ -v
```
29 tests covering board core logic and API smoke tests.

### Gotchas

- The `web/node_modules/.bin/` binaries may lack execute permissions after a fresh clone (they were committed without `+x`). Run `chmod +x web/node_modules/.bin/*` before `npm run dev` if you get "Permission denied" on `vite`.
- No linter or formatter is configured in the repo.
- `python3-tk` system package is required for the desktop app (CustomTkinter) but not for the Web UI.
- Pillow is commented out in `requirements.txt` — it's optional for image export features.
- The desktop app (CustomTkinter) needs a display; in headless environments start `Xvfb :99` and set `DISPLAY=:99`.
