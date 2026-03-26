/** Apply a boolean value to all cells in the selection rect on the locked mask. */
export function applyToSelectionRect(
  selectionRect: { x0: number; y0: number; x1: number; y1: number },
  lockedMask: boolean[][] | null,
  value: boolean
): boolean[][] | null {
  if (!lockedMask) return null;
  const { x0, y0, x1, y1 } = selectionRect;
  const xMin = Math.min(x0, x1);
  const xMax = Math.max(x0, x1);
  const yMin = Math.min(y0, y1);
  const yMax = Math.max(y0, y1);
  const next = lockedMask.map((row) => row.slice());
  for (let y = yMin; y <= yMax; y++) {
    for (let x = xMin; x <= xMax; x++) {
      if (y < next.length && x < next[y].length) next[y][x] = value;
    }
  }
  return next;
}
