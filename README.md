# boardgame

This repo now includes a configurable random board generator for a **50 x 50** game grid.

## Quick start

```bash
python board_generator.py
```

That prints a random 50x50 board using default terrain symbols:
- `.` plain
- `F` forest
- `M` mountain
- `W` water

If you run it by double-clicking the `.py` file on desktop, it now keeps the window open and also saves the board to `generated_board.txt` so the result is not lost.

## Customize layout

Example:

```bash
python board_generator.py \
  --seed 42 \
  --symmetry horizontal \
  --smoothing 2 \
  --cluster-bias 0.35 \
  --weights ".:0.55,F:0.20,M:0.15,W:0.10"
```

### Options
- `--width`, `--height`: board size (defaults to `50` x `50`)
- `--seed`: set a seed for reproducible boards
- `--weights`: terrain probability weights (`symbol:weight,...`)
- `--symmetry`: `none`, `horizontal`, `vertical`, or `both`
- `--smoothing`: number of neighborhood-smoothing passes
- `--cluster-bias`: `0.0` to `1.0`; higher values make clumps of terrain
- `--output`: optional file path to save the board text

## Use in your own code

```python
from board_generator import BoardOptions, generate_board, board_to_string

options = BoardOptions(
    width=50,
    height=50,
    seed=None,  # different board each game
    terrain_weights={".": 0.60, "F": 0.20, "M": 0.12, "W": 0.08},
    symmetry="none",
    smoothing_passes=1,
    cluster_bias=0.25,
)

board = generate_board(options)
print(board_to_string(board))
```
