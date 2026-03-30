## Cursor Cloud specific instructions

### Overview

Single-file Python desktop app (`board_generator.py`) — a procedural board-game map generator with Tkinter GUI and CLI modes. No external services, databases, or build steps required. See `README.md` for usage.

### System dependencies

- **Python 3.10+** (uses `int | None` union syntax)
- **python3-tk** (system package, required for GUI mode)
- **Xvfb** (pre-installed; needed for headless GUI testing)
- **Pillow** (optional pip package for JPEG export and better PNG export)

### Running the app

- **GUI mode**: `DISPLAY=:99 python3 board_generator.py` (start `Xvfb :99` first in headless environments)
- **CLI mode**: `python3 board_generator.py --cli --seed 42 --width 20 --height 20`

### Gotchas

- There is no `requirements.txt`, `pyproject.toml`, or test framework in the repo. The only pip dependency is `Pillow` (optional).
- The Tkinter window title stays "Board Generator (50x50)" regardless of the actual board size — this is existing behavior, not a bug.
- For GUI testing with `computerUse`, start Xvfb on display `:99` before launching the app.
- No linter or formatter is configured in the repo. If adding one, `ruff` or `flake8` are reasonable choices.
