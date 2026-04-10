"""
Board endpoints: generate, pathability, route quality, board-to-text, export image.
"""

from __future__ import annotations

import random
import zipfile
from io import BytesIO
from urllib.request import urlopen

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from api.routes import config as config_routes
from api.schemas import (
    BoardRequest,
    BoardValidationResponse,
    CardTemplateEntry,
    BoardTextResponse,
    ExportCardsRequest,
    ExportImageRequest,
    GameExportRequest,
    GameExportResponse,
    GameImportRequest,
    GameImportResponse,
    GenerateRequest,
    GenerateResponse,
    PathabilityResponse,
    ExportPrintRequest,
    GenerateBalancedRequest,
    RegenerateRequest,
    RegenerateResponse,
    RouteQualityResponse,
    SimulateRequest,
    SimulateResponse,
)
from board_core import (
    BoardOptions,
    DEFAULT_TERRAIN_WEIGHTS,
    TILE_COLORS,
    TILE_METADATA,
    TILE_NAMES,
    TILE_RULES,
    TILE_STYLES,
    check_pathability,
    compute_route_quality,
    generate_board,
    generate_board_with_selection_or_locks,
    board_to_string,
    run_monte_carlo,
)

router = APIRouter(prefix="/board", tags=["board"])

from api.utils import (
    Image,
    ImageDraw,
    ImageFont,
    PIL_AVAILABLE as _PIL_AVAILABLE,
    draw_board_to_image,
)

_BG_CANVAS = "#0A0E14"
_BORDER = "#262a33"
_DEFAULT_OUTLINES = {"G": ("#FACC15", 3), "1": ("#388BFD", 2), "2": ("#388BFD", 2), "3": ("#388BFD", 2), "4": ("#388BFD", 2)}


def _build_print_tiled_images(board: list[list[str]], paper: str):
    """Build tiled page PNGs; yield (page_index, png_bytes)."""
    if not _PIL_AVAILABLE:
        return
    page_w = int(8.5 * 150)
    page_h = int(11 * 150)
    if paper.lower() == "a4":
        page_w = int(210 / 25.4 * 150)
        page_h = int(297 / 25.4 * 150)
    board_w, board_h = len(board[0]), len(board)
    margin = 40
    mark = 12
    cell_px = min((page_w - 2 * margin) // board_w, (page_h - 2 * margin) // board_h)
    cells_per_page_x = (page_w - 2 * margin) // cell_px
    cells_per_page_y = (page_h - 2 * margin) // cell_px
    pages_x = (board_w + cells_per_page_x - 1) // cells_per_page_x
    pages_y = (board_h + cells_per_page_y - 1) // cells_per_page_y
    for py in range(pages_y):
        for px in range(pages_x):
            img = Image.new("RGB", (page_w, page_h), "white")
            draw = ImageDraw.Draw(img)
            ox, oy = margin, margin
            for dy in range(cells_per_page_y):
                for dx in range(cells_per_page_x):
                    gx = px * cells_per_page_x + dx
                    gy = py * cells_per_page_y + dy
                    if gx >= board_w or gy >= board_h:
                        continue
                    symbol = board[gy][gx]
                    color = TILE_COLORS.get(symbol, "#F8FAFC")
                    x0, y0 = ox + dx * cell_px, oy + dy * cell_px
                    draw.rectangle(
                        [x0, y0, x0 + cell_px, y0 + cell_px],
                        fill=color,
                        outline="#333",
                    )
            for (mx, my) in [
                (margin, margin),
                (page_w - margin, margin),
                (page_w - margin, page_h - margin),
                (margin, page_h - margin),
            ]:
                draw.ellipse(
                    [mx - mark, my - mark, mx + mark, my + mark],
                    outline="#000",
                    width=2,
                )
            buf = BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            yield py * pages_x + px + 1, buf.getvalue()


def _build_print_poster(board: list[list[str]]) -> bytes:
    """Build single poster PNG; return PNG bytes."""
    if not _PIL_AVAILABLE:
        return b""
    cell_px = 24
    img = draw_board_to_image(
        board,
        cell_px,
        TILE_COLORS,
        None,
        bg_color=_BG_CANVAS,
        border_color=_BORDER,
        draw_glyphs=False,
    )
    if img is None:
        return b""
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _build_board_legend_text(board: list[list[str]]) -> str:
    """Build a compact plain-text legend for symbols present on the board."""
    symbols = sorted({cell for row in board for cell in row})
    lines = ["Board Legend", "============", ""]
    for sym in symbols:
        name = TILE_NAMES.get(sym, "Unknown")
        rule = TILE_RULES.get(sym, "").strip()
        if rule:
            lines.append(f"{sym}: {name} - {rule}")
        else:
            lines.append(f"{sym}: {name}")
    return "\n".join(lines) + "\n"


def _compute_min_start_goal_distance(board: list[list[str]]) -> int | None:
    """Return shortest walkable distance from any start to goal, or None when unreachable/missing."""
    if not board or not board[0]:
        return None
    h, w = len(board), len(board[0])
    starts: list[tuple[int, int]] = []
    goal: tuple[int, int] | None = None
    blocked = {"W"}
    for y in range(h):
        for x in range(w):
            symbol = board[y][x]
            if symbol in {"1", "2", "3", "4"}:
                starts.append((x, y))
            elif symbol == "G":
                goal = (x, y)
    if not starts or goal is None:
        return None
    from collections import deque

    gx, gy = goal
    q = deque([(gx, gy, 0)])
    seen = {(gx, gy)}
    distances: dict[tuple[int, int], int] = {}
    while q:
        x, y, d = q.popleft()
        if (x, y) in starts:
            distances[(x, y)] = d
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if nx < 0 or ny < 0 or nx >= w or ny >= h:
                continue
            if (nx, ny) in seen:
                continue
            if board[ny][nx] in blocked:
                continue
            seen.add((nx, ny))
            q.append((nx, ny, d + 1))
    if not distances:
        return None
    return min(distances.values())


def _board_options_from_api(
    *,
    width: int,
    height: int,
    seed: int | None,
    terrain_weights: dict[str, float],
    symmetry: str,
    smoothing_passes: int,
    cluster_bias: float,
    generation_mode: str,
    num_starts: int,
    goal_placement: str,
    start_placement: str,
    min_goal_distance: int,
    safe_segment_radius: int,
    num_checkpoints: int,
) -> BoardOptions:
    """Single builder for GenerateRequest / GenerateBalancedRequest field sets."""
    weights = terrain_weights if terrain_weights else dict(DEFAULT_TERRAIN_WEIGHTS)
    return BoardOptions(
        width=width,
        height=height,
        seed=seed,
        terrain_weights=weights,
        symmetry=symmetry,
        smoothing_passes=smoothing_passes,
        cluster_bias=cluster_bias,
        generation_mode=generation_mode,
        num_starts=num_starts,
        goal_placement=goal_placement,
        start_placement=start_placement,
        min_goal_distance=min_goal_distance,
        safe_segment_radius=safe_segment_radius,
        num_checkpoints=num_checkpoints,
    )


def _request_to_options(req: GenerateRequest) -> BoardOptions:
    return _board_options_from_api(
        width=req.width,
        height=req.height,
        seed=req.seed,
        terrain_weights=req.terrain_weights,
        symmetry=req.symmetry,
        smoothing_passes=req.smoothing_passes,
        cluster_bias=req.cluster_bias,
        generation_mode=req.generation_mode,
        num_starts=req.num_starts,
        goal_placement=req.goal_placement,
        start_placement=req.start_placement,
        min_goal_distance=req.min_goal_distance,
        safe_segment_radius=req.safe_segment_radius,
        num_checkpoints=req.num_checkpoints,
    )


def _balanced_request_to_options(req: GenerateBalancedRequest, seed: int | None) -> BoardOptions:
    return _board_options_from_api(
        width=req.width,
        height=req.height,
        seed=seed,
        terrain_weights=req.terrain_weights,
        symmetry=req.symmetry,
        smoothing_passes=req.smoothing_passes,
        cluster_bias=req.cluster_bias,
        generation_mode=req.generation_mode,
        num_starts=req.num_starts,
        goal_placement=req.goal_placement,
        start_placement=req.start_placement,
        min_goal_distance=req.min_goal_distance,
        safe_segment_radius=req.safe_segment_radius,
        num_checkpoints=req.num_checkpoints,
    )


@router.post("/generate", response_model=GenerateResponse)
def post_generate(req: GenerateRequest) -> GenerateResponse:
    """Generate a new board from options."""
    options = _request_to_options(req)
    board = generate_board(options)
    return GenerateResponse(board=board, seed_used=options.seed)


@router.post("/generate-balanced", response_model=GenerateResponse)
def post_generate_balanced(req: GenerateBalancedRequest) -> GenerateResponse:
    """Generate a board with random seeds until route quality matches target (or max_attempts)."""
    target = (req.target_quality or "short/easy").strip().lower()
    accepted = {"short/easy", "medium"} if target == "short/easy" else ({"medium"} if target == "medium" else {"short/easy", "medium", "brutal"})
    rng = random.Random()
    for _ in range(req.max_attempts):
        seed = rng.randint(0, 2**31 - 1)
        options = _balanced_request_to_options(req, seed)
        board = generate_board(options)
        ok, _ = check_pathability(board)
        if not ok:
            continue
        label, _ = compute_route_quality(board)
        if target == "any" or label in accepted:
            return GenerateResponse(board=board, seed_used=seed)
    options = _balanced_request_to_options(req, rng.randint(0, 2**31 - 1))
    board = generate_board(options)
    return GenerateResponse(board=board, seed_used=options.seed)


@router.post("/pathability", response_model=PathabilityResponse)
def post_pathability(req: BoardRequest) -> PathabilityResponse:
    """Check whether all start positions can reach the goal."""
    ok, unreachable = check_pathability(req.board)
    return PathabilityResponse(ok=ok, unreachable=unreachable)


@router.post("/validate", response_model=BoardValidationResponse)
def post_validate(req: BoardRequest) -> BoardValidationResponse:
    """Validate start/goal requirements and connectivity for current board."""
    board = req.board
    goal_count = sum(1 for row in board for c in row if c == "G")
    start_count = sum(1 for row in board for c in row if c in {"1", "2", "3", "4"})
    ok, unreachable = check_pathability(board)
    min_distance = _compute_min_start_goal_distance(board)
    return BoardValidationResponse(
        goal_count=goal_count,
        start_count=start_count,
        pathability_ok=ok,
        unreachable=unreachable,
        min_start_goal_distance=min_distance,
    )


@router.post("/route-quality", response_model=RouteQualityResponse)
def post_route_quality(req: BoardRequest) -> RouteQualityResponse:
    """Get route quality label and details."""
    label, details = compute_route_quality(req.board)
    return RouteQualityResponse(label=label, details=details)


@router.post("/simulate", response_model=SimulateResponse)
def post_simulate(req: SimulateRequest) -> SimulateResponse:
    """Run Monte Carlo simulation: many simulated games from each start to goal."""
    result = run_monte_carlo(
        req.board,
        num_games=req.num_games,
        seed=req.seed,
        max_roll=req.max_roll,
    )
    heatmap_list = [
        {"x": x, "y": y, "count": count}
        for (x, y), count in result["heatmap"].items()
        if count > 0
    ]
    penalty_spikes_list = [list(p) for p in result["penalty_spikes"]]
    turns = [t for t in result["turns_per_start"] if t is not None]
    turn_spread = float(max(turns) - min(turns)) if turns else 0.0
    return SimulateResponse(
        expected_turns=result["expected_turns"],
        turns_per_start=result["turns_per_start"],
        heatmap=heatmap_list,
        penalty_spikes=penalty_spikes_list,
        turn_spread=turn_spread,
        hotspot_count=len(penalty_spikes_list),
    )


def _migrate_game_save(data: dict) -> dict:
    """Normalize saved game dict (set version if missing; future: migrate v1 -> v2)."""
    if "version" not in data or data["version"] is None:
        data = {**data, "version": 1}
    return data


@router.post("/export-game", response_model=GameExportResponse)
def post_export_game(req: GameExportRequest) -> GameExportResponse:
    """Build saved game JSON (unified schema: version, board, options, tile_rules, tile_metadata, locked_mask, layers)."""
    tile_rules = req.tile_rules if req.tile_rules is not None else dict(TILE_RULES)
    tile_metadata = req.tile_metadata if req.tile_metadata is not None else dict(TILE_METADATA)
    return GameExportResponse(
        version=1,
        board=req.board,
        options=req.options,
        tile_rules=tile_rules,
        tile_metadata=tile_metadata,
        locked_mask=req.locked_mask,
        path_layer=req.path_layer,
        events_layer=req.events_layer,
    )


@router.post("/import-game", response_model=GameImportResponse)
def post_import_game(req: GameImportRequest) -> GameImportResponse:
    """Validate uploaded game JSON (unified schema) and return board + options + locked_mask + layers for frontend."""
    if not req.board or not isinstance(req.board, list):
        raise HTTPException(status_code=400, detail="Invalid or missing 'board'")
    return GameImportResponse(
        board=req.board,
        options=req.options,
        tile_rules=req.tile_rules,
        tile_metadata=req.tile_metadata,
        locked_mask=req.locked_mask,
        path_layer=req.path_layer,
        events_layer=req.events_layer,
    )


@router.post("/regenerate", response_model=RegenerateResponse)
def post_regenerate(req: RegenerateRequest) -> RegenerateResponse:
    """Regenerate board, optionally only the selected region, preserving locked cells."""
    options = _request_to_options(req.options)
    sel = tuple(req.selection_rect) if req.selection_rect and len(req.selection_rect) == 4 else None
    new_board = generate_board_with_selection_or_locks(
        options,
        regenerate_selection_only=req.regenerate_selection_only,
        current_board=req.board,
        selection_rect=sel,
        locked_mask=req.locked_mask,
    )
    return RegenerateResponse(board=new_board)


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Wrap text to fit max_width; return list of lines."""
    if not text or max_width <= 0:
        return []
    lines: list[str] = []
    for para in text.split("\n"):
        words = para.split()
        current = ""
        for w in words:
            candidate = f"{current} {w}".strip() if current else w
            bbox = draw.textbbox((0, 0), candidate, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = w
        if current:
            lines.append(current)
    return lines


def _build_card_sheet_png(
    deck_id: str,
    deck_name: str,
    cards: list[CardTemplateEntry],
    include_back: bool,
) -> bytes:
    """Build one PNG sheet with real card content (title, body, optional image) and optional backs."""
    if not _PIL_AVAILABLE:
        return b""
    card_w, card_h = 300, 420
    margin, gap = 20, 10
    cut_line = 2
    padding = 12
    n_cards = len(cards) if cards else 1
    cols = 2
    rows_front = (n_cards + cols - 1) // cols
    rows_back = rows_front if include_back else 0
    rows = rows_front + rows_back
    sheet_w = 2 * margin + cols * (card_w + gap) - gap
    sheet_h = 2 * margin + rows * (card_h + gap) - gap
    img = Image.new("RGB", (sheet_w, sheet_h), "white")
    draw = ImageDraw.Draw(img)
    try:
        font_title = ImageFont.truetype("arial.ttf", 20)
        font_body = ImageFont.truetype("arial.ttf", 14)
    except Exception:
        font_title = ImageFont.load_default()
        font_body = font_title

    def draw_card_front(x0: int, y0: int, card: CardTemplateEntry) -> None:
        draw.rectangle([x0, y0, x0 + card_w, y0 + card_h], outline="#333", width=cut_line)
        inner = [x0 + cut_line, y0 + cut_line, x0 + card_w - cut_line, y0 + card_h - cut_line]
        draw.rectangle(inner, fill="#FEF3C7")
        ix0, iy0 = x0 + padding, y0 + padding
        iw = card_w - 2 * padding - 2 * cut_line
        ih = card_h - 2 * padding - 2 * cut_line
        # Title
        title = (card.title or card.id or "Untitled").strip() or "Untitled"
        if len(title) > 35:
            title = title[:32] + "..."
        draw.text((ix0, iy0), title, fill="#92400E", font=font_title)
        title_bbox = draw.textbbox((ix0, iy0), title, font=font_title)
        y_cur = title_bbox[3] + 8
        # Optional image area (top portion of body area)
        img_h = 0
        if card.image_url:
            try:
                with urlopen(card.image_url, timeout=5) as resp:
                    data = resp.read()
                card_img = Image.open(BytesIO(data)).convert("RGB")
                thumb_w = min(iw, card_img.width)
                thumb_h = min(120, int(card_img.height * thumb_w / card_img.width) if card_img.width else 120)
                card_img = card_img.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
                img.paste(card_img, (ix0, y_cur))
                img_h = thumb_h + 6
                y_cur += img_h
            except Exception:
                pass
        # Body (wrapped)
        body = (card.body or "").strip()
        if body:
            max_w = iw
            lines = _wrap_text(draw, body, font_body, max_w)
            line_h = draw.textbbox((0, 0), "Ay", font=font_body)[3] - draw.textbbox((0, 0), "A", font=font_body)[1]
            for line in lines:
                if y_cur + line_h > y0 + card_h - padding - cut_line:
                    break
                draw.text((ix0, y_cur), line, fill="#78350F", font=font_body)
                y_cur += line_h + 2

    def draw_card_back(x0: int, y0: int, back_label: str) -> None:
        draw.rectangle([x0, y0, x0 + card_w, y0 + card_h], outline="#333", width=cut_line)
        inner = [x0 + cut_line, y0 + cut_line, x0 + card_w - cut_line, y0 + card_h - cut_line]
        draw.rectangle(inner, fill="#E5E7EB")
        text = (back_label or "BACK").strip() or "BACK"
        if len(text) > 28:
            text = text[:25] + "..."
        draw.text((x0 + card_w // 2 - 30, y0 + card_h // 2 - 12), text, fill="#6B7280", font=font_title)

    # Placeholder when no templates
    if not cards:
        cards = [CardTemplateEntry(id="placeholder", title=deck_name, body="", image_url=None, back_text=None)]
        n_cards = 1

    for i, card in enumerate(cards):
        row = i // cols
        col = i % cols
        y0 = margin + row * (card_h + gap)
        x0 = margin + col * (card_w + gap)
        draw_card_front(x0, y0, card)
    if include_back:
        for i in range(n_cards):
            row = rows_front + i // cols
            col = i % cols
            y0 = margin + row * (card_h + gap)
            x0 = margin + col * (card_w + gap)
            back_label = cards[i].back_text if i < len(cards) else "BACK"
            draw_card_back(x0, y0, back_label or "")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@router.post("/export-cards")
def post_export_cards(req: ExportCardsRequest) -> Response:
    """Export print-ready card sheets (real card content from templates + optional back, cut lines) as ZIP of PNGs."""
    if not _PIL_AVAILABLE:
        raise HTTPException(status_code=501, detail="PIL (Pillow) is required for card export")
    all_decks = config_routes.list_decks()
    if req.deck_ids:
        decks = [config_routes.get_deck_by_id(did) for did in req.deck_ids]
        decks = [d for d in decks if d is not None]
    else:
        decks = all_decks
    if not decks:
        raise HTTPException(status_code=400, detail="No decks to export")
    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for d in decks:
            templates = config_routes.get_templates_by_ids(d.card_template_ids)
            png_bytes = _build_card_sheet_png(d.id, d.name, templates, req.include_back)
            zf.writestr(f"cards_{d.id}.png", png_bytes)
    zip_buf.seek(0)
    return Response(content=zip_buf.getvalue(), media_type="application/zip")


@router.post("/export-print")
def post_export_print(req: ExportPrintRequest) -> Response:
    """Export board for print: tiled pages (ZIP of PNGs) or single poster (PNG)."""
    if not _PIL_AVAILABLE:
        raise HTTPException(status_code=501, detail="PIL (Pillow) is required for print export")
    if not req.board or not req.board[0]:
        raise HTTPException(status_code=400, detail="Board must have at least one row and column")
    paper = req.paper if req.paper in ("a4", "letter") else "a4"
    if req.mode == "poster":
        png_bytes = _build_print_poster(req.board)
        return Response(content=png_bytes, media_type="image/png")
    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for page_num, png_bytes in _build_print_tiled_images(req.board, paper):
            zf.writestr(f"board_page_{page_num}.png", png_bytes)
        zf.writestr("board_legend.txt", _build_board_legend_text(req.board))
    zip_buf.seek(0)
    return Response(content=zip_buf.getvalue(), media_type="application/zip")


@router.post("/to-text", response_model=BoardTextResponse)
def post_to_text(req: BoardRequest) -> BoardTextResponse:
    """Serialize board to text (one row per line)."""
    text = board_to_string(req.board)
    return BoardTextResponse(text=text)


@router.post("/export-image")
def post_export_image(req: ExportImageRequest) -> Response:
    """Export board as PNG. Returns 501 if PIL is not installed."""
    if not _PIL_AVAILABLE:
        raise HTTPException(status_code=501, detail="PIL (Pillow) is required for image export")
    board = req.board
    if not board or not board[0]:
        raise HTTPException(status_code=400, detail="Board must have at least one row and column")
    tile_size = req.tile_size
    font = ImageFont.load_default() if ImageFont else None
    image = draw_board_to_image(
        board,
        tile_size,
        TILE_COLORS,
        TILE_STYLES,
        bg_color=_BG_CANVAS,
        border_color=_BORDER,
        outline_overrides=_DEFAULT_OUTLINES,
        draw_glyphs=True,
        font=font,
    )
    if image is None:
        raise HTTPException(status_code=501, detail="PIL (Pillow) is required for image export")
    buf = BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    return Response(content=buf.read(), media_type="image/png")
