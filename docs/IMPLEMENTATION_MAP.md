# Mystic Meadows — Implementation Map (developer-facing)

This document maps the existing repository files, TMX layers, and concrete asset paths
to the runtime systems and behaviors expected by the codebase. It's intended as a
hand-off for any developer implementing or maintaining the game logic.

Keep this file in the repository (docs/) and update when systems or TMX layers change.

Overview
- Core scene: Farm (expected canonical file: `src/farm.py`) — constructs the world from `data/map.tmx`, loads sprites from `assets/sprites`, starts audio from `assets/audio`, and coordinates update/render for the simulation.
- Map TMX and assets:
  - `data/map.tmx` — source map used to place tiles, collision, trees, player start, beds, trader, etc.
  - `assets/sprites/` — player, tiles, crops, water frames and world ground image.
  - `assets/audio/success.wav` and `assets/audio/music.mp3` — sfx and BGM.

High-level responsibilities

- Farm scene (`src/farm.py`)
  - Load `data/map.tmx` (e.g. using `pytmx.util_pygame.load_pygame`) and iterate layers by name.
  - Instantiate `Generic`, `Water`, `Tree`, `WildFlower`, `Interaction` sprites for tiles/objects and add them to appropriate sprite groups (e.g., `all_sprites`, `collision_sprites`, `tree_sprites`, `interaction_sprites`).
  - Load a ground image and place at z = `LAYERS['ground']` from `assets/sprites/world/ground.png`.
  - Create `SoilLayer` (from `src/soil.py`) and pass references to `Player` and relevant groups.
  - Instantiate `Menu`, `UI`, `Sky`, `Rain`, `Transition`, audio `Sound` objects, and the `CameraGroup`.
  - Implement `run(dt)` that: clears the display, calls `all_sprites.custom_draw(player)`, updates either `menu` or `all_sprites` + `plant_collision()`, calls `ui.display()`, updates `rain`, calls `sky.display(dt)`, and runs `transition.play()` when `player.sleep`.

- Soil / Farming (`src/soil.py`) — `SoilLayer`
  - Maintain a grid (2D list) of tile states: tilled, seed_id, plant sprite ref, watered_today flag, occupied_by.
  - Expose methods: `till(x,y)`, `plant(x,y,seed_id)`, `water(x,y)`, `update_plants()` (advance growth at day rollover), `remove_water()`, `water_all()`.
  - Keep `plant_sprites` group so `farm.plant_collision()` can iterate and detect harvesting.

- Player (`src/player.py`)
  - Handle movement (checking `collision_sprites`), tool use, inventory management, and interactions.
  - Player receives refs: `collision_sprites`, `tree_sprites`, `interaction_sprites`, `soil_layer`, `toggle_shop` callback.
  - Set `player.sleep = True` when interacting with a `Bed` interaction; use Trader interactions to toggle the shop.

- Sprites (`src/sprites.py`)
  - Provide `Generic`, `Water`, `WildFlower`, `Tree`, `Interaction`, `Particle` with appropriate groups and layering.
  - All sprites must have `.z` attribute to support `CameraGroup.custom_draw` ordering. Default `.z` should be `LAYERS['main']`.

- CameraGroup & rendering
  - `all_sprites` is a `CameraGroup` (subclass of `pygame.sprite.Group`) with `custom_draw(player)` which:
    - Computes camera offset to center player.
    - Iterates `LAYERS` in order and blits sprites with matching `sprite.z`, sorted by `sprite.rect.centery` (top-down depth).

- Tree & Interaction sprites
  - Trees should add themselves to `all_sprites`, `collision_sprites`, and `tree_sprites`.
  - Trees manage fruit spawn and provide `player_add` callbacks when harvested.
  - Interactions placed from TMX (e.g., `Trader`, `Bed`) become `Interaction` sprites in `interaction_sprites`.

- Shop & Menu (`src/menu.py`, `src/ui.py`)
  - `Menu` is modal. When `shop_active` is True, `Farm.run` should call `menu.update()` instead of updating the simulation.
  - Buying/selling updates `player.item_inventory` and currency; `toggle_shop` opens/closes modal.

- Sky, Rain, Transition (`src/sky.py`, `src/transition.py`)
  - `Sky` handles day/night visual overlay applied every frame via `sky.display(dt)`.
  - `Rain` is visual when `raining` is True and lives in `all_sprites`.
  - `Transition` coordinates end-of-day animation and then calls `Farm.reset()` to run day-rollover logic.

Event/Update sequencing (per-frame)

1. Clear display surface
2. `all_sprites.custom_draw(self.player)` — draw sorted layers with camera offset
3. If `shop_active`: `self.menu.update()` else: `self.all_sprites.update(dt)` and `self.plant_collision()`
4. `self.ui.display()`
5. If `raining`: `self.rain.update()`
6. `self.sky.display(dt)`
7. If `player.sleep`: `self.transition.play()` (when transition completes it calls `reset()`)

Day-rollover (`reset()` called from `Transition`)

- `reset()` should:
  - Call `soil_layer.update_plants()` to advance growth and handle harvest-ready states.
  - Call `soil_layer.remove_water()` to clear daily water flags.
  - Randomize `raining` and, if raining, call `soil_layer.water_all()`.
  - Recreate fruit on trees and reset sky colors.
  - Trigger autosave (persist player state, farm grid, tree fruit states) using a `SaveSystem`.

Harvest flow

- `plant_collision()` loops `soil_layer.plant_sprites` and checks `plant.rect.colliderect(player.hitbox)`.
- On harvest: call `player_add(plant.plant_type)` to increment inventory, `plant.kill()` to remove sprite, spawn `Particle`, and update grid occupancy to free the tile.

Audio

- Initialize `pygame.mixer` early (main or farm init).
- Load sounds:
  - `self.success = pygame.mixer.Sound('assets/audio/success.wav')`
  - `self.music = pygame.mixer.Sound('assets/audio/music.mp3')` (or `mixer.music.load`)
- Play music with `loops=-1` and SFX for interactions/harvest.

TMX layer names and mapping (must match the TMX file)

- `HouseFloor`, `HouseFurnitureBottom` -> Generic (z = `LAYERS['house bottom']`)
- `HouseWalls`, `HouseFurnitureTop` -> Generic (z = `LAYERS['house top']`)
- `Fence` -> Generic added to `collision_sprites`
- `Water` -> Water animated sprites loaded from `assets/sprites/water/`
- `Trees` -> Tree objects (object layer)
- `Decoration` -> WildFlower objects
- `Collision` -> Generic opaque tiles in `collision_sprites`
- `Player` object layer names: `Start`, `Bed`, `Trader` etc. `Start` sets player spawn.

Developer checklist (concrete tasks)

1. Ensure `data/config/settings.py` defines `TILE_SIZE`, `SCREEN_WIDTH`, `SCREEN_HEIGHT`, `LAYERS` mapping matching TMX and rendering.
2. Implement `Generic` sprite constructor to accept `z` and default `z = LAYERS['main']`.
3. Implement `CameraGroup.custom_draw(player)` to center camera and render by layer order and `rect.centery` sort.
4. Implement `SoilLayer` API: `till`, `plant`, `water`, `update_plants`, `remove_water`, `water_all`, and keep `plant_sprites` group.
5. Wire `Player` to use `soil_layer` for tool actions and to set `player.sleep` when interacting with Bed.
6. Hook audio initialization early and centralize through an `AudioSystem` if preferred.
7. Implement `Transition.reset()` to call `Farm.reset()` and trigger save via `SaveSystem`.
8. Persist runtime state in `data/saves/` using transactional writes (save temp + atomic rename + backup).

Extension notes

- If you want finer-grained crop progression (intra-day), add a `TimeSystem` and change `SoilLayer.update_plants()` to advance based on elapsed hours instead of only on reset.
- Consider moving audio and save logic into `systems/` modules for cleaner separation and testability.

Files & asset paths (explicit)

- `data/map.tmx`
- `assets/sprites/water/` (frames loaded by `import_folder`)
- `assets/sprites/world/ground.png`
- `assets/audio/success.wav`
- `assets/audio/music.mp3`

If you want, I can now:
- Create a `src/farm.py` skeleton implementing world construction from the TMX file and integrating `SoilLayer`, `Player` wiring, camera, and the run loop described above, or
- Add a `docs/` checklist and tests for `SoilLayer` and `Player` interactions, or
- Implement a `SaveSystem` that serializes the runtime state at `reset()`.

Pick which one you'd like next and I'll implement it.
