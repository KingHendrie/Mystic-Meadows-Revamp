# Mystic Meadows — Revamp (Project 2)

A small 2D farming game prototype built with Python and Pygame. This
repository contains the game code, assets and simple tools used during
development. The recent work added debug utilities (export screenshots,
soil exports), HUD improvements and shop/harvest fixes.

## Quick start

Requirements: Python 3.10+ and `pygame` (pygame-ce recommended).

Run the game (from project root):

```bash
python run_game.py
```

You can also run small smoke tests used during development, e.g. to render
the HUD headlessly (used in CI/dev):

```bash
python - <<'PY'
import pygame
from pathlib import Path
pygame.init(); pygame.display.set_mode((640,480))
from src.game.entities.player import Player
from src.game.ui.hud import HUD
p = Player(assets_dir=Path('assets'))
ui = HUD(p, assets_dir=Path('assets'))
ui.display(pygame.display.get_surface())
print('HUD drawn')
PY
```

## Repository layout

- `assets/` — game images, sprites, audio and fonts
- `src/game/` — main source code
  - `entities/` — `Player` and entity code
  - `ui/` — HUD, Menu and UI overlays
  - `soil.py` — `SoilLayer` grid and plant handling
  - `farm.py` — world manager, camera, sprite groups, save/load
  - `debug_utils.py` — debug actions (exports, GrowAll, Teleport, etc.)
  - `systems/save_system.py` — simple save/load helpers
- `data/` — runtime data; saves and debug exports are written here by default

## Key modules and important functions

Below are the most important modules and the core functions / methods to
know. Use these as a quick code map when making changes.

- `src/game/farm.py`
  - `class Farm` — central world manager. Key methods:
    - `render(surface)` — draws the world (sprites, sky, hud and overlays).
    - `update(dt, keys)` — game loop update; handles debug keys (F6/F7), shop toggle
    - `save_game(slot=None)` — assembles state and delegates to `SaveSystem`.
    - `reset_day()` / `_on_day_advance()` — day advancement logic and autosave.

- `src/game/soil.py`
  - `class SoilLayer` — maintains a 2D `grid` of per-tile flags (tilled/water/plant)
    and `plant_sprites` group.
  - `plant(tx, ty, seed_id)` — plant a seed on a tile.
  - `harvest_at_rect(rect)` — harvest any plant overlapping a rect and update grid
    (keeps tile tilled after harvest so replanting is immediate).
  - `water_all()`, `remove_water()` — watering helpers.

- `src/game/entities/player.py`
  - `class Player` — input, tools and inventory handling.
  - `player.player_add(item, count)` — adds items to inventory (used for harvest/sell)
  - Tool use and interaction methods for hoe/water/harvest.

- `src/game/ui/hud.py`
  - `class HUD` — renders top HUD, hotbar, debug panel and toasts.
  - `display(surface)` — draw HUD elements; handles toasts and debug button layout.
  - `toast(text, duration, ttype)` — ephemeral message API (info/success/error).
  - `handle_debug_event(event)` — translates clicks on debug panel into actions.

- `src/game/ui/menu.py`
  - Shop and controls overlays. Implements Buy/Sell buttons per-item. See `draw`
    and `handle_event` for click mapping logic.

- `src/game/debug_utils.py`
  - `handle_debug_action(hud, key)` — central dispatcher for debug actions.
  - Exports: `ExportScreen` creates multiple debug images (farm view, color map,
    collisions, plant map, HUD-only) and saves them under `data/screenshots/YYYY-MM-DD/`.
  - `ExportSoil` dumps `soil.grid` and plant metadata to `data/exports/` as JSON.

## Debug/export workflow

- Trigger the debug menu by pressing `F7` in-game; click the new `ExportScreen`
  to produce diagnostic images in `data/screenshots/YYYY-MM-DD/`.
- `ExportSoil` writes a JSON snapshot to `data/exports/`.
- The new `.gitignore` excludes `data/screenshots/` and `data/exports/` so exported
  artifacts don't get accidentally committed.

## Development notes & suggestions

- Add a small configuration entry for export paths (e.g. `farm.debug_dir`) so
  exports can be redirected outside the repo (recommended).
- Add unit tests for `debug_utils` and `soil` to avoid regressions when modifying
  plant/save logic.
- Consider offloading image/file writes to a background thread to avoid stalls
  when exporting during gameplay.

## Contributing

If you plan to extend the project, please:

1. Run tests (when present) and linting locally.
2. Create a feature branch and open a PR with a descriptive message.
3. Keep changes small and add tests for new logic where practical.

---
If you'd like, I can also generate a short developer guide listing common
edit points (where to add new plants, how to add seeds, etc.) or prepare
a small CI workflow to run tests and linting automatically.
