# boardgame

This project includes a **self-contained interactive app** for generating random board layouts.

## Desktop app (recommended)

```bash
python board_generator.py
```

Running with no arguments opens a windowed app (Tkinter) that stays open until you close it.
You can:
- set width/height (default 50x50)
- set optional seed
- tune terrain weights
- apply symmetry, smoothing, and clustering
- generate new boards repeatedly
- save the generated board to a text file

This fixes the "console opens then closes" problem for desktop usage.

## CLI mode (optional)

```bash
python board_generator.py --cli --seed 42 --symmetry horizontal --output board.txt
```

### CLI options
- `--cli`: run in terminal mode instead of GUI
- `--width`, `--height`: board size
- `--seed`: deterministic generation
- `--weights`: e.g. `.:0.65,F:0.17,M:0.10,W:0.08`
- `--symmetry`: `none`, `horizontal`, `vertical`, `both`
- `--smoothing`: neighborhood smoothing passes
- `--cluster-bias`: value from `0.0` to `1.0`
- `--output`: file path to save the board text

## Programmatic usage

```python
from board_generator import BoardOptions, generate_board, board_to_string

options = BoardOptions(width=50, height=50, seed=None)
board = generate_board(options)
print(board_to_string(board))
```
