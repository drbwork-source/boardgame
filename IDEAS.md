# Boardgame Feature Ideas

This document collects practical ideas for expanding this board generator into a complete "physical board + rules cards" toolkit.

## 1) Path & progression design
- **Auto-place start/end zones** with configurable distance and optional "safe" first/last segments.
- **Route quality score** that estimates average game length and difficulty (short/easy, medium, brutal).
- **Checkpoint tiles** so players can save progress mid-board.
- **Optional branching path generator** (single critical path plus side routes for risk/reward).
- **Dead-end budget** slider to control how often risky detours appear.

## 2) Tile behavior system
- **Tile metadata editor** where each symbol maps to: category, difficulty, and card deck type.
- **Stacked effects** (e.g., entering Water + carrying a "heavy item" adds extra penalty).
- **Trigger frequency control** (always trigger, trigger once per player, trigger with dice roll).
- **Stateful tiles** that can flip after activation (e.g., trap springs once, then becomes normal).

## 3) Card/deck management (Monopoly-style events)
- **Deck builder UI** with per-tile decks (Forest Deck, Mountain Deck, etc.).
- **Card templates** for common effect types:
  - move forward/backward
  - skip turn
  - swap positions
  - resource gain/loss
  - choose-your-risk action
- **Rarity weighting** to keep severe forfeits uncommon.
- **Print-ready card export** (PDF with card backs and cut lines).
- **Optional QR codes** on tiles/cards linking to digital rules text.

## 4) Balance & simulation tools
- **Monte Carlo playtest simulator** (virtual players roll/move thousands of games).
- **Expected turns-to-finish metric** for selected board + deck config.
- **Tile heatmap report** showing most visited spaces.
- **Penalty spike detector** to flag punishing clusters (e.g., too many harsh tiles in a row).
- **Catch-up mechanics** analysis for player count scaling.

## 5) Board authoring workflow
- **Layer mode**: terrain layer, path layer, events layer.
- **Paint-by-region tools** (rectangle fill, lasso fill, noise brush).
- **Locked areas** so handcrafted sections are preserved during regeneration.
- **"Regenerate only selected area"** for quick iteration.
- **Undo/redo history** with snapshots.

## 6) Physical table usability
- **Print-friendly board export**:
  - A4/Letter tiled pages with alignment marks
  - large poster export
- **Colorblind-safe palette packs** and symbol-first mode.
- **Legend sheet auto-generation** (tile symbol -> plain-language rule summary).
- **Setup checklist** output (components needed, card counts, markers).

## 7) Game mode presets
- **Party mode** (chaotic swings, short games).
- **Strategy mode** (fewer random punishments, more choices).
- **Co-op mode** (shared timer/events, group penalties).
- **Campaign mode** where completed runs unlock new tile/card types.

## 8) Data model improvements
- **Single save format** (JSON) for board + rules + decks + print settings.
- **Versioned schema** so old saves can be migrated automatically.
- **Import/export packs** to share custom tilesets and card libraries.

## 9) Nice-to-have polish
- **Seed gallery** (save favorite seeds with thumbnails).
- **"Daily board" generator** from current date.
- **One-click "balanced random setup"** for fast play.
- **Rule text linting** to catch ambiguous wording in cards.

---

## Suggested next implementation order
1. Start/end auto-placement + path validation.
2. Tile metadata + per-tile deck mapping.
3. Print exports (board + cards).
4. Basic simulator for balancing.
5. Advanced authoring tools (region regen, lock areas, layers).
