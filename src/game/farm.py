"""Farm world manager for the skeleton game.

This keeps sprite groups, camera drawing and integrates `SoilLayer` and `Player`.
It uses a simple grid rather than a full TMX parser to avoid extra dependencies.
"""
from __future__ import annotations

from pathlib import Path
from typing import Tuple
import pygame
import logging

from pygame.sprite import Group, Sprite

from src.game.config import DEFAULT_TILE_SIZE, DEFAULT_WINDOW_SIZE
from src.game.soil import SoilLayer
from src.game.entities.player import Player
from src.game.sprites import Generic, Tree, Interaction, Water, WildFlower
from src.game.systems.save_system import SaveSystem
from src.game.ui.menu import Menu
from src.game.ui.hud import HUD
from src.game.transition import Transition
from src.game.sky import Sky

_logger = logging.getLogger("mystic_meadows.farm")


class CameraGroup(Group):
    def __init__(self, window_size: Tuple[int, int], *sprites):
        super().__init__(*sprites)
        self.window_w, self.window_h = window_size

    def custom_draw(self, player: Player, surface: pygame.Surface):
        # center player
        offset_x = player.rect.centerx - self.window_w // 2
        offset_y = player.rect.centery - self.window_h // 2

        # draw background
        surface.fill((50, 180, 70))

        # draw all sprites sorted by z then by rect.centery
        sprites = sorted(self.sprites(), key=lambda s: (getattr(s, "z", 3), s.rect.centery))
        for s in sprites:
            dest = s.rect.move(-offset_x, -offset_y)
            surface.blit(s.image, dest)


class Farm:
    def __init__(self, assets_dir: Path, data_dir: Path, window_size=DEFAULT_WINDOW_SIZE, tile_size=DEFAULT_TILE_SIZE[0]):
        # Accept None for assets_dir/data_dir and fall back to repository root ('.')
        try:
            self.assets_dir = Path(assets_dir) if assets_dir is not None else Path('.')
        except Exception:
            self.assets_dir = Path('.')
        try:
            self.data_dir = Path(data_dir) if data_dir is not None else Path('.')
        except Exception:
            self.data_dir = Path('.')
        self.tile_size = tile_size
        self.window_size = window_size

        # Sprites and groups
        self.all_sprites = CameraGroup(window_size)
        self.collision_sprites = Group()
        self.tree_sprites = Group()
        self.interaction_sprites = Group()

        # Create a player at center
        px = window_size[0] // 2
        py = window_size[1] // 2
        self.player = Player(id="player", x=px, y=py, assets_dir=self.assets_dir)
        self.all_sprites.add(self.player)

        # Menu (shop) and transition controller
        self.menu = Menu(self.player, self.toggle_shop)
        self._tab_prev = False
        self._n_prev = False
        # debug key edge state (F6 teleport to plant, F7 toggle debug overlay)
        self._f6_prev = False
        self._f7_prev = False
        # debug draw flags
        self._debug_draw_collisions = False

        # Transition for day advance
        self.transition = Transition(window_size, on_day_advance=self._on_day_advance)

        # Sky visuals and HUD
        try:
            self.sky = Sky(window_size)
        except Exception:
            self.sky = None
        try:
            self.ui = HUD(self.player, self.assets_dir)
        except Exception:
            self.ui = None

        
        # Save system
        try:
            self.save_system = SaveSystem(self.data_dir)
        except Exception:
            self.save_system = None

        # Soil grid: prefer using the authored TMX map tile size and dimensions
        # if available so soil tiles align with the map. Fall back to window-based grid.
        grid_w = window_size[0] // tile_size
        grid_h = window_size[1] // tile_size
        effective_tile_size = tile_size
        try:
            try:
                from pytmx.util_pygame import load_pygame
            except Exception:
                load_pygame = None
            map_file = self.data_dir / "map.tmx"
            if load_pygame is not None and map_file.exists():
                tmx = load_pygame(str(map_file))
                # prefer the TMX tile size so coordinates match the map
                effective_tile_size = getattr(tmx, 'tilewidth', tile_size)
                grid_w = getattr(tmx, 'width', grid_w)
                grid_h = getattr(tmx, 'height', grid_h)
        except Exception:
            pass

        # create SoilLayer with the effective tile size and grid dimensions
        self.soil = SoilLayer(self.all_sprites, self.collision_sprites, effective_tile_size, (grid_w, grid_h), assets_dir=self.assets_dir)

        # Try to load authored TMX map with layer-aware sprite creation (preferred)
        try:
            try:
                from pytmx.util_pygame import load_pygame
            except Exception:
                load_pygame = None
            map_file = self.data_dir / "map.tmx"
            if load_pygame is not None and map_file.exists():
                tmx = load_pygame(str(map_file))
                tile_w = tmx.tilewidth
                tile_h = tmx.tileheight

                # try to import layer z mapping from data config if available
                try:
                    from data.config.settings import LAYERS as TMX_LAYERS
                except Exception:
                    TMX_LAYERS = {
                        'water': 0,
                        'ground': 1,
                        'soil': 2,
                        'soil water': 3,
                        'rain floor': 4,
                        'house bottom': 5,
                        'ground plant': 6,
                        'main': 7,
                        'house top': 8,
                        'fruit': 9,
                        'rain drops': 10
                    }

                from src.game.resources.resource_manager import import_folder

                # helper to safely fetch a layer
                def layer_tiles(name):
                    try:
                        layer = tmx.get_layer_by_name(name)
                        return layer.tiles()
                    except Exception:
                        return []

                # House and furniture layers
                for layer_name in ('HouseFloor', 'HouseFurnitureBottom'):
                    try:
                        for x, y, surf in tmx.get_layer_by_name(layer_name).tiles():
                            Generic((x * tile_w, y * tile_h), surf, (self.all_sprites,), z=TMX_LAYERS.get('house bottom', 5))
                    except Exception:
                        pass

                for layer_name in ('HouseWalls', 'HouseFurnitureTop'):
                    try:
                        for x, y, surf in tmx.get_layer_by_name(layer_name).tiles():
                            Generic((x * tile_w, y * tile_h), surf, (self.all_sprites,), z=TMX_LAYERS.get('house top', 8))
                    except Exception:
                        pass

                # Fence -> collision
                try:
                    for x, y, surf in tmx.get_layer_by_name('Fence').tiles():
                        Generic((x * tile_w, y * tile_h), surf, (self.all_sprites, self.collision_sprites), z=TMX_LAYERS.get('main', 7))
                except Exception:
                    pass

                # Water -> animated tiles
                try:
                    water_frames = import_folder(self.assets_dir / 'sprites' / 'water')
                    for x, y, surf in tmx.get_layer_by_name('Water').tiles():
                        Water((x * tile_w, y * tile_h), water_frames, (self.all_sprites,), z=TMX_LAYERS.get('water', 0))
                except Exception:
                    pass

                # Trees (object layer)
                try:
                    for obj in tmx.get_layer_by_name('Trees'):
                        try:
                            nx = int(obj.x)
                            ny = int(obj.y)
                            Tree((nx - 0, ny - tile_h), getattr(obj, 'image', None), (self.all_sprites, self.collision_sprites, self.tree_sprites), name=getattr(obj, 'name', 'Tree'), player_add=getattr(self.player, 'player_add', None), z=TMX_LAYERS.get('main', 7))
                        except Exception:
                            pass
                except Exception:
                    pass

                # Decoration
                try:
                    for obj in tmx.get_layer_by_name('Decoration'):
                        try:
                            WildFlower((int(obj.x), int(obj.y)), getattr(obj, 'image', None), (self.all_sprites,))
                        except Exception:
                            pass
                except Exception:
                    pass

                # Collision tiles
                try:
                    for x, y, surf in tmx.get_layer_by_name('Collision').tiles():
                        Generic((x * tile_w, y * tile_h), pygame.Surface((tile_w, tile_h)), (self.collision_sprites,))
                except Exception:
                    pass

                # Player and object placements
                try:
                    for obj in tmx.get_layer_by_name('Player'):
                        try:
                            name = getattr(obj, 'name', '') or ''
                            nx = int(obj.x)
                            ny = int(obj.y)
                            if name in ('Start', 'Player', 'player', 'start'):
                                try:
                                    self.player.x = nx
                                    self.player.y = ny
                                    self.player.rect.center = (nx, ny)
                                    self.player.hitbox.center = self.player.rect.center
                                    # Debug: verify soil grid marks this spawn tile as farmable
                                    try:
                                        tx = nx // self.soil.tile_size
                                        ty = ny // self.soil.tile_size
                                        f = getattr(self.soil, 'grid', None)
                                        has_f = False
                                        if self.soil.in_bounds(tx, ty):
                                            has_f = ('F' in self.soil.grid[ty][tx])
                                        print(f"Player spawn at px={nx},{ny} -> tile={tx},{ty}, farmable={has_f}")
                                    except Exception:
                                        pass
                                except Exception:
                                    pass
                            elif name == 'Bed':
                                Interaction((nx, ny), (int(getattr(obj, 'width', tile_w)), int(getattr(obj, 'height', tile_h))), 'Bed', (self.all_sprites, self.interaction_sprites), z=TMX_LAYERS.get('main', 7))
                            elif name in ('Trader', 'Shop'):
                                Interaction((nx, ny), (int(getattr(obj, 'width', tile_w)), int(getattr(obj, 'height', tile_h))), 'Trader', (self.all_sprites, self.interaction_sprites), z=TMX_LAYERS.get('main', 7))
                        except Exception:
                            pass
                except Exception:
                    pass

                # Background ground tile (single sprite)
                try:
                    ground_path = self.assets_dir / 'sprites' / 'world' / 'ground.png'
                    if ground_path.exists():
                        ground_surf = pygame.image.load(str(ground_path)).convert_alpha()
                        Generic((0, 0), ground_surf, (self.all_sprites,), z=TMX_LAYERS.get('ground', 1))
                except Exception:
                    pass
            else:
                # fallback: create simple ground tiles so the map is visible without TMX
                ground_path = self.assets_dir / "sprites" / "world" / "ground.png"
                if ground_path.exists():
                    ground_surf = pygame.image.load(str(ground_path)).convert_alpha()
                    ground_surf = pygame.transform.scale(ground_surf, (tile_size, tile_size))
                else:
                    ground_surf = None
                for x in range(grid_w):
                    for y in range(grid_h):
                        if ground_surf is not None:
                            surf = ground_surf
                        else:
                            surf = pygame.Surface((tile_size, tile_size))
                            surf.fill((100, 180, 90))
                        Generic((x * tile_size, y * tile_size), surf, (self.all_sprites,), z=1)
        except Exception:
            pass

        # Attach world references to player so it can call soil/interact
        try:
            self.player.attach_world(self.soil, self.collision_sprites, self.tree_sprites, self.interaction_sprites, self.toggle_shop)
            # convenient backref for HUD or other systems that want the farm/day
            try:
                setattr(self.player, "farm", self)
            except Exception:
                pass
        except Exception:
            pass

        # HUD state
        self.day = 1
        self.running = True
        # selected save slot (default 1); can be overridden by TitleScene via context
        self.save_slot = 1

        # audio
        try:
            pygame.mixer.init()
            success_path = self.assets_dir / "audio" / "success.wav"
            music_path = self.assets_dir / "audio" / "music.mp3"
            if success_path.exists():
                self.success = pygame.mixer.Sound(str(success_path))
                self.success.set_volume(0.3)
            else:
                self.success = None
            if music_path.exists():
                pygame.mixer.music.load(str(music_path))
                pygame.mixer.music.set_volume(0.2)
                pygame.mixer.music.play(-1)
        except Exception:
            _logger.debug("Audio unavailable or failed to initialize")

    def update(self, dt: float, keys):
        # shop modal handling: if menu active, only update menu
        if self.menu.active:
            # allow toggle key to close via edge detection
            try:
                tab_pressed = keys[pygame.K_TAB]
            except Exception:
                tab_pressed = False
            if tab_pressed and not self._tab_prev:
                self.toggle_shop(False)
            self._tab_prev = tab_pressed
            # let menu handle input
            try:
                self.menu.update()
            except Exception:
                pass
            return

        # Edge detect day-transition key (n) and menu key (tab)
        try:
            tab_pressed = keys[pygame.K_TAB]
            n_pressed = keys[pygame.K_n]
        except Exception:
            tab_pressed = False
            n_pressed = False

        # debug: grant seeds/money for quick testing (F1)
        try:
            if keys[pygame.K_F1]:
                try:
                    self.player.inventory['corn'] = self.player.inventory.get('corn', 0) + 5
                    self.player.inventory['tomato'] = self.player.inventory.get('tomato', 0) + 5
                    self.player.money = getattr(self.player, 'money', 0) + 100
                except Exception:
                    pass
        except Exception:
            pass

        # debug keys: teleport to first plant (F6) and toggle plant overlay (F7)
        try:
            try:
                f6_pressed = keys[pygame.K_F6]
            except Exception:
                f6_pressed = False
            try:
                f7_pressed = keys[pygame.K_F7]
            except Exception:
                f7_pressed = False

            # teleport to first plant on press (edge-detected)
            if f6_pressed and not getattr(self, '_f6_prev', False):
                try:
                    ps = list(self.soil.plant_sprites.sprites())
                    if ps:
                        p = ps[0]
                        # set player's logical position via properties so pos/hitbox sync
                        try:
                            # prefer property setters which update rect/hitbox/pos
                            self.player.x = p.rect.centerx
                            self.player.y = p.rect.centery
                        except Exception:
                            # fallback: directly set rect and hitbox and pos vector
                            try:
                                self.player.rect.center = p.rect.center
                            except Exception:
                                pass
                            try:
                                self.player.hitbox.center = p.rect.center
                            except Exception:
                                pass
                            try:
                                if getattr(self.player, 'pos', None) is not None:
                                    self.player.pos.x = p.rect.centerx
                                    self.player.pos.y = p.rect.centery
                            except Exception:
                                pass
                except Exception:
                    pass

            # toggle HUD debug overlay on F7 press (edge-detected)
            if f7_pressed and not getattr(self, '_f7_prev', False):
                try:
                    if getattr(self, 'ui', None) is not None:
                        self.ui.show_debug = not getattr(self.ui, 'show_debug', False)
                except Exception:
                    pass

            self._f6_prev = f6_pressed
            self._f7_prev = f7_pressed
        except Exception:
            pass

        if tab_pressed and not self._tab_prev:
            # only open the shop if the player is near a Trader interaction object
            opened = False
            try:
                if self.player.interaction_sprites is not None:
                    for it in self.player.interaction_sprites.sprites():
                        try:
                            if getattr(it, 'name', None) == 'Trader' and it.rect.colliderect(self.player.hitbox):
                                self.toggle_shop(True)
                                opened = True
                                break
                        except Exception:
                            pass
            except Exception:
                pass
            if not opened:
                # ignore tab when not near trader
                pass
        if n_pressed and not self._n_prev:
            # start transition (which will call day advance when complete)
            try:
                self.transition.start()
            except Exception:
                pass
        self._tab_prev = tab_pressed
        self._n_prev = n_pressed

        # Update player and other sprites. Some sprites accept dt/keys, others don't.
        # Ensure the player is updated with dt and keys.
        try:
            self.player.update(dt, keys)
        except TypeError:
            # fallback to no-arg update
            try:
                self.player.update()
            except Exception:
                pass

        # Update other sprites safely
        for spr in list(self.all_sprites.sprites()):
            if spr is self.player:
                continue
            # Try different update signatures
            try:
                spr.update(dt, keys)
            except TypeError:
                try:
                    spr.update(dt)
                except TypeError:
                    try:
                        spr.update()
                    except Exception:
                        pass

        # update transition
        try:
            self.transition.update(dt)
        except Exception:
            pass

        # If player indicated sleep via interaction, start the day transition
        try:
            if getattr(self.player, 'sleep', False):
                if not getattr(self.transition, 'running', False):
                    try:
                        self.transition.start()
                    except Exception:
                        pass
                # reset the flag so we don't repeatedly start transitions
                try:
                    # clear any current movement so the player doesn't resume moving
                    try:
                        self.player.direction = pygame.math.Vector2()
                    except Exception:
                        pass
                    self.player.sleep = False
                except Exception:
                    pass
        except Exception:
            pass

        # update sky
        try:
            if getattr(self, "sky", None) is not None:
                self.sky.update(dt)
        except Exception:
            pass

    def render(self, surface: pygame.Surface):
        self.all_sprites.custom_draw(self.player, surface)
        # debug: optionally draw player rect and a small marker (controlled by HUD debug toggle)
        try:
            if getattr(self, 'ui', None) is not None and getattr(self.ui, 'show_debug', False):
                pygame.draw.rect(surface, (255, 0, 0), self.player.rect.move((self.window_size[0]//2 - self.player.rect.centerx, self.window_size[1]//2 - self.player.rect.centery)), 1)
                # small center marker
                cx = self.window_size[0] // 2
                cy = self.window_size[1] // 2
                pygame.draw.circle(surface, (0, 0, 255), (cx, cy), 3)
                # optionally draw collision rects
                try:
                    if getattr(self, '_debug_draw_collisions', False):
                        for c in list(self.collision_sprites.sprites()):
                            try:
                                dest = c.rect.move((self.window_size[0]//2 - self.player.rect.centerx, self.window_size[1]//2 - self.player.rect.centery))
                                pygame.draw.rect(surface, (255, 128, 0), dest, 1)
                            except Exception:
                                pass
                except Exception:
                    pass
        except Exception:
            pass
        # sky overlay (draw over sprites but below UI)
        try:
            if getattr(self, "sky", None) is not None:
                self.sky.display(surface)
        except Exception:
            pass

        # HUD
        try:
            if getattr(self, "ui", None) is not None:
                self.ui.display(surface)
        except Exception:
            pass

        # draw menu overlay if active
        try:
            if self.menu.active:
                # let menu render itself (includes controls panel when toggled)
                try:
                    self.menu.draw(surface)
                except Exception:
                    # fallback to old minimal overlay
                    font = pygame.font.Font(None, 32)
                    overlay = pygame.Surface((200, 150), pygame.SRCALPHA)
                    overlay.fill((0,0,0,180))
                    surface.blit(overlay, (50, 50))
                    surface.blit(font.render("Shop - 1: Corn (5)", True, (255,255,255)), (60, 60))
                    surface.blit(font.render("2: Tomato (7)", True, (255,255,255)), (60, 100))
            else:
                # if the menu isn't active but the controls overlay was requested (Tab held), draw it
                try:
                    if getattr(self, 'menu', None) is not None and getattr(self.menu, 'show_controls', False):
                        try:
                            self.menu.draw_controls(surface)
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

        # draw transition on top if running
        try:
            self.transition.draw(surface)
        except Exception:
            pass

    def plant_collision(self):
        # harvest if player overlaps a harvestable plant
        harvested = self.soil.harvest_at_rect(self.player.hitbox)
        if harvested:
            self.player.inventory[harvested] = self.player.inventory.get(harvested, 0) + 1
            if self.success:
                try:
                    self.success.play()
                except Exception:
                    pass

        # harvest tree apples if overlapping
        try:
            for tree in list(self.tree_sprites.sprites()):
                # each tree has an apple_sprites group
                apples = getattr(tree, "apple_sprites", None)
                if apples is None:
                    continue
                for a in list(apples.sprites()):
                    if a.rect.colliderect(self.player.hitbox):
                        # give apple to player
                        app_id = getattr(a, "item_id", "apple")
                        try:
                            self.player.player_add(app_id, 1)
                        except Exception:
                            self.player.inventory[app_id] = self.player.inventory.get(app_id, 0) + 1
                        try:
                            a.kill()
                        except Exception:
                            pass
                        if self.success:
                            try:
                                self.success.play()
                            except Exception:
                                pass
        except Exception:
            pass

    def reset_day(self):
        # Called at end of day
        self.soil.update_plants()
        # Clear any watering marks at day reset so watering lasts only a single day
        # (water should not persist across sleeps/day advances).
        self.soil.remove_water()
        # decide whether the new day will have rain, but do not automatically
        # re-water tiles here: watering should be an in-day event or handled
        # explicitly rather than immediately after sleeping.
        import random
        self.soil.raining = random.choice([False, False, True])
        self.day += 1

    def _on_day_advance(self):
        # Called by transition when day advance is requested
        try:
            self.reset_day()
        except Exception:
            pass

        # perform quick-save of essential state
        if getattr(self, "save_system", None) is not None:
            try:
                # reuse save_game which assembles a consistent state and respects the
                # currently selected save slot (self.save_slot). This ensures we do
                # not accidentally create a new slot based on the day number.
                try:
                    self.save_game(slot=getattr(self, 'save_slot', None))
                    # display a save toast when UI is available
                    try:
                        ui = getattr(self, 'ui', None)
                        if ui is not None:
                            ui.toast(f"Game saved (slot {getattr(self, 'save_slot', 1)})", 2.5)
                    except Exception:
                        pass
                except Exception:
                    # fallback: try auto_save using the configured save_slot
                    try:
                        use_slot = getattr(self, 'save_slot', 1)
                        state = {
                            "day": self.day,
                            "player": {
                                "money": getattr(self.player, "money", 0),
                                "inventory": getattr(self.player, "inventory", getattr(self.player, "item_inventory", {})),
                            },
                            "plants": [
                                {"x": getattr(p, 'tx', int(p.rect.x) // self.tile_size), "y": getattr(p, 'ty', int(p.rect.y) // self.tile_size), "type": getattr(p, "plant_type", None), "growth_stage": getattr(p, "growth_stage", 0)}
                                for p in list(self.soil.plant_sprites.sprites())
                            ],
                        }
                        try:
                            self.save_system.auto_save(state, slot=use_slot)
                        except Exception:
                            try:
                                self.save_system.auto_save(state)
                            except Exception:
                                pass
                        try:
                            ui = getattr(self, 'ui', None)
                            if ui is not None:
                                ui.toast(f"Game saved (slot {use_slot})", 2.5)
                        except Exception:
                            pass
                    except Exception:
                        pass
            except Exception:
                pass

    def toggle_shop(self, on: bool):
        try:
            if on:
                self.menu.open()
            else:
                self.menu.close()
        except Exception:
            pass

    def save_game(self, slot: int | None = None):
        """Assemble runtime state and delegate to SaveSystem to persist it.

        The saved state includes:
        - day number
        - player money and inventory (including seed_inventory)
        - soil grid flags (per-tile list of flags)
        - plant list with x,y,type and growth_stage
        """
        try:
            if getattr(self, 'save_system', None) is None:
                return None
            use_slot = slot or getattr(self, 'save_slot', 1)
            state = {
                'day': getattr(self, 'day', 1),
                'player': {
                    'money': getattr(self.player, 'money', 0),
                    'inventory': getattr(self.player, 'inventory', getattr(self.player, 'item_inventory', {})),
                    'seed_inventory': getattr(self.player, 'seed_inventory', {}),
                    # save player logical position (prefer pos vector) so load can restore camera/player
                    'pos': (
                        int(getattr(getattr(self.player, 'pos', None), 'x', getattr(self.player, 'rect', None) and int(self.player.rect.centerx) or 0)),
                        int(getattr(getattr(self.player, 'pos', None), 'y', getattr(self.player, 'rect', None) and int(self.player.rect.centery) or 0)),
                    ),
                    # save orientation/status so we can restore facing/animation state
                    'status': getattr(self.player, 'status', None),
                    'facing': getattr(self.player, 'facing', None),
                },
                'soil': {
                    'grid': getattr(self.soil, 'grid', []),
                    'tile_size': getattr(self.soil, 'tile_size', None),
                    'width': getattr(self.soil, 'grid_w', None),
                    'height': getattr(self.soil, 'grid_h', None),
                },
                    'plants': [
                        {
                            'x': getattr(p, 'tx', int(p.rect.x) // self.tile_size),
                            'y': getattr(p, 'ty', int(p.rect.y) // self.tile_size),
                            'type': getattr(p, 'plant_type', None),
                            'growth_stage': getattr(p, 'growth_stage', 0),
                        }
                        for p in list(getattr(self.soil, 'plant_sprites', []).sprites())
                    ],
            }
            # use auto_save which wraps save with default directory handling
            try:
                return self.save_system.auto_save(state, slot=use_slot)
            except Exception:
                return None
        except Exception:
            return None

    def load_from_payload(self, payload: dict):
        """Restore farm state from saved payload (payload is the save file 'payload' dict)."""
        # Minimal, robust restore implementation with a clear control flow.
        try:
            # day
            try:
                self.day = int(payload.get('day', self.day))
            except Exception:
                _logger.debug('load_from_payload: failed to parse day from payload')

            # player basic state
            player_state = payload.get('player', {}) or {}
            try:
                self.player.money = player_state.get('money', getattr(self.player, 'money', 0))
            except Exception:
                pass
            if 'inventory' in player_state:
                try:
                    self.player.inventory = player_state.get('inventory', self.player.inventory)
                except Exception:
                    pass
            if 'seed_inventory' in player_state:
                try:
                    self.player.seed_inventory = player_state.get('seed_inventory', getattr(self.player, 'seed_inventory', {}))
                except Exception:
                    pass

            # soil and plants
            soil_payload = payload.get('soil', {})
            plants_payload = payload.get('plants', [])
            if getattr(self, 'soil', None) is not None:
                try:
                    self.soil.restore_state(soil_payload, plants_payload)
                except Exception:
                    _logger.exception('load_from_payload: soil.restore_state failed')

            # Player position handling: prefer saved pos, but if it places the player far
            # away from any restored plant, move them to the first plant so crops are visible.
            pos = player_state.get('pos', None)
            try:
                if pos:
                    # prefer setting player.x/player.y to keep internal pos/hitbox/rect in sync
                    try:
                        self.player.x = int(pos[0])
                        self.player.y = int(pos[1])
                    except Exception:
                        try:
                            self.player.rect.center = (int(pos[0]), int(pos[1]))
                        except Exception:
                            pass
                    try:
                        if getattr(self.player, 'hitbox', None) is not None:
                            self.player.hitbox.center = self.player.rect.center
                    except Exception:
                        pass
                    # restore orientation/status if present
                    try:
                        st = player_state.get('status', None)
                        if st is not None:
                            try:
                                self.player.status = st
                                # if animations exist, update image to match status
                                if getattr(self.player, 'animations', None) and st in getattr(self.player, 'animations', {}):
                                    frames = self.player.animations.get(st) or []
                                    if frames:
                                        self.player.image = frames[0]
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        facing = player_state.get('facing', None)
                        if facing is not None:
                            try:
                                self.player.facing = facing
                            except Exception:
                                pass
                    except Exception:
                        pass
                # collect restored plants
                ps = list(getattr(self.soil, 'plant_sprites', []).sprites()) if getattr(self, 'soil', None) is not None else []
                if ps:
                    if pos:
                        # compute pixel distance to nearest plant
                        px, py = self.player.rect.center
                        min_dist = min(((pp.rect.center[0] - px) ** 2 + (pp.rect.center[1] - py) ** 2) ** 0.5 for pp in ps)
                        thresh = max(self.window_size) if getattr(self, 'window_size', None) is not None else 800
                        if min_dist > thresh:
                            _logger.debug('load_from_payload: saved player pos is far (%.1f px) from nearest plant; centering on first plant', min_dist)
                            p0 = ps[0]
                            try:
                                self.player.rect.center = p0.rect.center
                                try:
                                    self.player.hitbox.center = self.player.rect.center
                                except Exception:
                                    pass
                            except Exception:
                                pass
                    else:
                        # no saved pos: center on first plant
                        p0 = ps[0]
                        try:
                            self.player.rect.center = p0.rect.center
                            try:
                                self.player.hitbox.center = self.player.rect.center
                            except Exception:
                                pass
                        except Exception:
                            pass
            except Exception:
                _logger.exception('load_from_payload: failed to restore player position or center on plants')
        except Exception:
            _logger.exception('load_from_payload: unexpected error during load')
