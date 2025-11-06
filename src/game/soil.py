"""SoilLayer: backup-like grid-of-flags farming system.

This implementation mirrors the backup semantics: grid[y][x] is a list of
flags ('F' = farmable, 'X' = tilled, 'W' = watered, 'P' = planted). Tools
use hit-rects to detect farmable tiles (get_hit) and visual tiles are
created from assets/sprites/soil. Plants are created from assets/sprites/fruit.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple, List, Optional
import logging
import pygame

from pygame.sprite import Group, Sprite

_logger = logging.getLogger("mystic_meadows.soil")


class Plant(Sprite):
    def __init__(self, x: int, y: int, tile_size: int, plant_type: str = "corn", assets_dir: Optional[Path] = None):
        super().__init__()
        self.plant_type = plant_type
        self.tile_size = tile_size
        # store tile coords for later repositioning when image/frame changes
        self.tx = x
        self.ty = y
        try:
            from src.game.resources.resource_manager import import_folder
            assets = Path(assets_dir) if assets_dir is not None else Path('assets')
            frames = import_folder(assets / 'sprites' / 'fruit' / plant_type)
        except Exception:
            frames = []

        if frames:
            # ensure frames are usable surfaces and have alpha
            cleaned = []
            for fr in frames:
                try:
                    fr2 = fr.convert_alpha()
                except Exception:
                    fr2 = fr
                cleaned.append(fr2)
            self.frames = cleaned
            self.image = self.frames[0]
            self.max_stage = len(self.frames) - 1
        else:
            self.image = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
            pygame.draw.rect(self.image, (34, 139, 34), self.image.get_rect())
            self.frames = [self.image]
            self.max_stage = 3

        # small vertical offset for different plant types
        self.y_offset = -16 if plant_type == 'corn' else -8
        # position plant so it's visually centered on the tile and uses the y offset
        self.reposition()
        # try to use project layer mapping when available
        try:
            from data.config.settings import LAYERS
            self.z = LAYERS.get('ground plant', 6)
        except Exception:
            self.z = 6
        self.growth_stage = 0.0
        self.harvestable = False

    def advance(self):
        if self.growth_stage < self.max_stage:
            self.growth_stage += 1
            try:
                self.image = self.frames[int(self.growth_stage)]
            except Exception:
                pass
            # ensure rect matches new image while preserving tile alignment
            try:
                self.reposition()
            except Exception:
                pass
            if self.growth_stage >= self.max_stage:
                self.harvestable = True

    def reposition(self):
        """Recompute rect based on current image and stored tile coords so
        changing frames keeps the plant aligned to its tile."""
        try:
            mid_x = self.tx * self.tile_size + self.tile_size // 2
            mid_bottom_y = self.ty * self.tile_size + self.tile_size
            self.rect = self.image.get_rect(midbottom=(mid_x, mid_bottom_y + self.y_offset))
        except Exception:
            # fallback: keep existing rect or create a default one
            try:
                self.rect = self.image.get_rect()
            except Exception:
                self.rect = pygame.Rect(0, 0, self.tile_size, self.tile_size)


class SoilLayer:
    def __init__(self, all_sprites: Group, collision_sprites: Group, tile_size: int, grid_size: Tuple[int, int], assets_dir: Optional[Path] = None):
        self.all_sprites = all_sprites
        self.collision_sprites = collision_sprites
        self.tile_size = tile_size
        self.grid_w, self.grid_h = grid_size
        try:
            self.assets_dir = Path(assets_dir) if assets_dir is not None else Path('assets')
        except Exception:
            self.assets_dir = Path('assets')

        # grid[y][x] -> list of flags like 'F','X','W','P'
        self.grid: List[List[List[str]]] = [[[] for _ in range(self.grid_w)] for _ in range(self.grid_h)]

        # sprite groups
        self.plant_sprites: Group = Group()
        self.soil_sprites: Group = Group()
        # preview sprites (temporary placement indicators)
        # use a plain assignment (some environments don't accept PEP526 instance annotations here)
        self.preview_sprites = Group()
        self.water_sprites: Group = Group()

        self.raining = False

        # load visuals
        self.soil_surfs = self._import_soil_surfaces(self.assets_dir / 'sprites' / 'soil')
        try:
            from src.game.resources.resource_manager import import_folder
            self.water_surfs = import_folder(self.assets_dir / 'sprites' / 'soil_water')
        except Exception:
            self.water_surfs = []

        # populate farmable tiles
        self.create_soil_grid()
        # create hit rects for farmable tiles
        self.create_hit_rects()

        # optional sounds
        try:
            hoe_path = Path('assets') / 'audio' / 'hoe.wav'
            plant_path = Path('assets') / 'audio' / 'plant.wav'
            if hoe_path.exists():
                self.hoe_sound = pygame.mixer.Sound(str(hoe_path))
                try:
                    self.hoe_sound.set_volume(0.1)
                except Exception:
                    pass
            else:
                self.hoe_sound = None
            if plant_path.exists():
                self.plant_sound = pygame.mixer.Sound(str(plant_path))
                try:
                    self.plant_sound.set_volume(0.2)
                except Exception:
                    pass
            else:
                self.plant_sound = None
        except Exception:
            self.hoe_sound = None
            self.plant_sound = None

    def in_bounds(self, tx: int, ty: int) -> bool:
        return 0 <= tx < self.grid_w and 0 <= ty < self.grid_h

    def _import_soil_surfaces(self, folder: Path) -> Dict[str, pygame.Surface]:
        out: Dict[str, pygame.Surface] = {}
        if not folder.exists() or not folder.is_dir():
            return out
        for f in folder.iterdir():
            if f.suffix.lower() in ('.png', '.jpg', '.bmp'):
                try:
                    surf = pygame.image.load(str(f)).convert_alpha()
                    out[f.stem] = surf
                except Exception:
                    pass
        return out

    def create_soil_grid(self):
        """Populate farmable 'F' flags from data/map.tmx Farmable layer or mark all tiles farmable."""
        try:
            from pytmx.util_pygame import load_pygame
            tmx = load_pygame('data/map.tmx')
            # If the TMX map exists, resize our internal grid to match the map dimensions
            try:
                map_w = tmx.width
                map_h = tmx.height
                # update grid dimensions and reinitialize grid structure
                self.grid_w = map_w
                self.grid_h = map_h
                self.grid = [[[] for _ in range(self.grid_w)] for _ in range(self.grid_h)]
            except Exception:
                pass
            layer = tmx.get_layer_by_name('Farmable')
            for x, y, _ in layer.tiles():
                if 0 <= x < self.grid_w and 0 <= y < self.grid_h:
                    if 'F' not in self.grid[y][x]:
                        self.grid[y][x].append('F')
        except Exception:
            # fallback: mark all tiles farmable
            for y in range(self.grid_h):
                for x in range(self.grid_w):
                    if 'F' not in self.grid[y][x]:
                        self.grid[y][x].append('F')

    def create_hit_rects(self):
        self.hit_rects: List[pygame.Rect] = []
        for y, row in enumerate(self.grid):
            for x, cell in enumerate(row):
                if 'F' in cell:
                    r = pygame.Rect(x * self.tile_size, y * self.tile_size, self.tile_size, self.tile_size)
                    self.hit_rects.append(r)

    def create_soil_tiles(self):
        """Rebuild soil sprite visuals for all tilled ('X') tiles using neighbor-aware tile types."""
        for s in list(self.soil_sprites.sprites()):
            s.kill()

        for y in range(self.grid_h):
            for x in range(self.grid_w):
                cell = self.grid[y][x]
                if 'X' not in cell:
                    continue

                # neighbor checks (safe bounds)
                t = 'X' in self.grid[y - 1][x] if y - 1 >= 0 else False
                b = 'X' in self.grid[y + 1][x] if y + 1 < self.grid_h else False
                l = 'X' in self.grid[y][x - 1] if x - 1 >= 0 else False
                r = 'X' in self.grid[y][x + 1] if x + 1 < self.grid_w else False

                tile_type = 'o'
                if all((t, r, b, l)):
                    tile_type = 'x'
                if l and not any((t, r, b)):
                    tile_type = 'r'
                if r and not any((t, l, b)):
                    tile_type = 'l'
                if r and l and not any((t, b)):
                    tile_type = 'lr'
                if t and not any((r, l, b)):
                    tile_type = 'b'
                if b and not any((r, l, t)):
                    tile_type = 't'
                if b and t and not any((r, l)):
                    tile_type = 'tb'
                if l and b and not any((t, r)):
                    tile_type = 'tr'
                if r and b and not any((t, l)):
                    tile_type = 'tl'
                if l and t and not any((b, r)):
                    tile_type = 'br'
                if r and t and not any((b, l)):
                    tile_type = 'bl'
                if all((t, b, r)) and not l:
                    tile_type = 'tbr'
                if all((t, b, l)) and not r:
                    tile_type = 'tbl'
                if all((l, r, t)) and not b:
                    tile_type = 'lrb'
                if all((l, r, b)) and not t:
                    tile_type = 'lrt'

                surf = self.soil_surfs.get(tile_type) if self.soil_surfs else None
                if surf is None:
                    surf = pygame.Surface((self.tile_size, self.tile_size), pygame.SRCALPHA)
                    surf.fill((101, 67, 33))

                SoilTile((x * self.tile_size, y * self.tile_size), surf, [self.all_sprites, self.soil_sprites])

    # ---- preview helpers ----
    def preview_tile(self, tx: int, ty: int):
        """Create a temporary preview sprite at tile coords (tx,ty).
        This is used to show where a hoe/plant/water action will occur before
        the action completes. Returns the preview sprite instance.
        """
        if not (0 <= tx < self.grid_w and 0 <= ty < self.grid_h):
            _logger.debug("preview_tile out of bounds: %s,%s", tx, ty)
            return None
        # choose a simple preview surface (semi-transparent overlay)
        surf = pygame.Surface((self.tile_size, self.tile_size), pygame.SRCALPHA)
        surf.fill((200, 160, 100, 120))
        p = SoilTile((tx * self.tile_size, ty * self.tile_size), surf, [self.all_sprites, self.preview_sprites])
        _logger.debug("preview_tile created at tile %s,%s (px %s,%s)", tx, ty, tx * self.tile_size, ty * self.tile_size)
        return p

    def clear_preview(self):
        for s in list(self.preview_sprites.sprites()):
            try:
                s.kill()
            except Exception:
                pass
        _logger.debug("clear_preview called, preview_count now %s", len(self.preview_sprites.sprites()))

    def get_hit(self, point: Tuple[int, int]) -> bool:
        """Backup-compatible helper: accept a world point (x,y), find a farmable
        hit rect and mark it tilled (append 'X'). Returns True if tilled.
        """
        try:
            for rect in list(getattr(self, 'hit_rects', [])):
                if rect.collidepoint(point):
                    _logger.debug("get_hit: point %s collides with rect at %s,%s", point, rect.x, rect.y)
                    try:
                        if getattr(self, 'hoe_sound', None) is not None:
                            self.hoe_sound.play()
                    except Exception:
                        pass

                    x = rect.x // self.tile_size
                    y = rect.y // self.tile_size
                    _logger.debug("get_hit -> tile coords %s,%s", x, y)
                    cell = self.grid[y][x]
                    if 'F' in cell and 'X' not in cell:
                        cell.append('X')
                        _logger.debug("get_hit: tilled tile %s,%s; creating soil tiles", x, y)
                        self.create_soil_tiles()
                        if self.raining:
                            self.water_all()
                        return True
                    else:
                        _logger.debug("get_hit: tile not tilled (F in cell: %s, X in cell: %s)", 'F' in cell, 'X' in cell)
        except Exception:
            _logger.exception("get_hit encountered an exception")
        return False

    def till(self, tx: int, ty: int) -> bool:
        """Till by tile coords (tx,ty). Compatible with player.use_tool calls."""
        if not self.in_bounds(tx, ty):
            _logger.debug("till out of bounds: %s,%s", tx, ty)
            return False
        cell = self.grid[ty][tx]
        if 'F' not in cell or 'X' in cell:
            _logger.debug("till: cannot till tile %s,%s (F in cell: %s, X in cell: %s)", tx, ty, 'F' in cell, 'X' in cell)
            return False
        cell.append('X')
        try:
            if getattr(self, 'hoe_sound', None) is not None:
                self.hoe_sound.play()
        except Exception:
            pass
        _logger.debug("till: tilled tile %s,%s; creating soil tiles", tx, ty)
        self.create_soil_tiles()
        if self.raining:
            self.water_all()
        return True

    def water(self, tx: int, ty: int) -> bool:
        if not self.in_bounds(tx, ty):
            return False
        cell = self.grid[ty][tx]
        # Only water tilled soil ('X') — watering should not work on untilled ground
        if 'X' not in cell:
            _logger.debug("water: tile %s,%s is not tilled; skipping", tx, ty)
            return False
        if 'W' in cell:
            return True
        cell.append('W')
        try:
            if self.water_surfs:
                from random import choice
                surf = choice(self.water_surfs)
                WaterTile((tx * self.tile_size, ty * self.tile_size), surf, [self.all_sprites, self.water_sprites])
        except Exception:
            pass
        return True

    def water_all(self):
        for y in range(self.grid_h):
            for x in range(self.grid_w):
                cell = self.grid[y][x]
                if 'X' in cell and 'W' not in cell:
                    cell.append('W')
                    try:
                        from random import choice
                        surf = choice(self.water_surfs) if self.water_surfs else None
                        if surf is not None:
                            WaterTile((x * self.tile_size, y * self.tile_size), surf, [self.all_sprites, self.water_sprites])
                    except Exception:
                        pass
        _logger.debug("All tiles watered (rain)")

    def remove_water(self):
        for s in list(self.water_sprites.sprites()):
            try:
                s.kill()
            except Exception:
                pass
        for y in range(self.grid_h):
            for x in range(self.grid_w):
                cell = self.grid[y][x]
                if 'W' in cell:
                    try:
                        cell.remove('W')
                    except Exception:
                        pass

    def check_watered(self, pos: Tuple[int, int]) -> bool:
        x = pos[0] // self.tile_size
        y = pos[1] // self.tile_size
        if not (0 <= x < self.grid_w and 0 <= y < self.grid_h):
            return False
        return 'W' in self.grid[y][x]

    def plant(self, tx: int, ty: int, seed_id: str) -> bool:
        # backward-compatible plant at tile coords
        if not self.in_bounds(tx, ty):
            return False
        cell = self.grid[ty][tx]
        if 'X' not in cell or 'P' in cell:
            return False
        cell.append('P')
        plant = Plant(tx, ty, self.tile_size, plant_type=seed_id, assets_dir=self.assets_dir)
        self.plant_sprites.add(plant)
        self.all_sprites.add(plant)
        _logger.debug("plant: planted %s at %s,%s", seed_id, tx, ty)
        try:
            if getattr(self, 'plant_sound', None) is not None:
                self.plant_sound.play()
        except Exception:
            pass
        return True

    def update_plants(self):
        for p in list(self.plant_sprites.sprites()):
            if self.check_watered(p.rect.center) or self.raining:
                p.advance()

    def restore_state(self, soil_payload: dict, plants_payload: list):
        """Restore soil grid and plant sprites from saved payload.

        soil_payload: dict with keys 'grid', 'tile_size', 'width', 'height'
        plants_payload: list of plant descriptors with x,y,type,growth_stage
        """
        try:
            grid = soil_payload.get('grid', None)
            if grid is not None:
                # assign grid and dimensions
                self.grid = grid
                self.grid_h = len(self.grid)
                self.grid_w = len(self.grid[0]) if self.grid_h > 0 else 0

            # clear existing sprites
            for s in list(self.soil_sprites.sprites()):
                try:
                    s.kill()
                except Exception:
                    pass
            for s in list(self.water_sprites.sprites()):
                try:
                    s.kill()
                except Exception:
                    pass
            for s in list(self.plant_sprites.sprites()):
                try:
                    s.kill()
                except Exception:
                    pass

            # rebuild soil visuals for tilled tiles
            try:
                self.create_soil_tiles()
            except Exception:
                pass

            # recreate water visuals for tiles marked 'W'
            try:
                if getattr(self, 'water_surfs', None):
                    from random import choice
                    for y in range(self.grid_h):
                        for x in range(self.grid_w):
                            try:
                                cell = self.grid[y][x]
                                if 'W' in cell:
                                    surf = choice(self.water_surfs) if self.water_surfs else None
                                    if surf is not None:
                                        WaterTile((x * self.tile_size, y * self.tile_size), surf, [self.all_sprites, self.water_sprites])
                            except Exception:
                                pass
            except Exception:
                pass

            # recreate plants
            for pdesc in plants_payload or []:
                try:
                    tx_raw = int(pdesc.get('x', 0))
                    ty_raw = int(pdesc.get('y', 0))
                    ptype = pdesc.get('type', 'corn')
                    gstage = float(pdesc.get('growth_stage', 0.0))

                    # clamp out-of-bounds plant coords to nearest tile and log
                    tx = max(0, min(tx_raw, self.grid_w - 1)) if self.grid_w > 0 else 0
                    ty = max(0, min(ty_raw, self.grid_h - 1)) if self.grid_h > 0 else 0
                    if tx != tx_raw or ty != ty_raw:
                        _logger.debug("restore_state: remapped plant from %s,%s to %s,%s (grid %sx%s)", tx_raw, ty_raw, tx, ty, self.grid_w, self.grid_h)

                    # ensure grid marks planted
                    try:
                        cell = self.grid[ty][tx]
                        if 'P' not in cell:
                            cell.append('P')
                    except Exception:
                        _logger.debug("restore_state: failed to mark grid cell P at %s,%s", tx, ty)

                    # create plant at clamped coords
                    plant = Plant(tx, ty, self.tile_size, plant_type=ptype, assets_dir=self.assets_dir)
                    _logger.debug("restore_state: created plant type=%s requested=%s at tile=%s,%s frames=%s image_size=%s z=%s", ptype, pdesc.get('type'), tx, ty, len(getattr(plant, 'frames', [])), getattr(getattr(plant, 'image', None), 'get_size', lambda: None)(), getattr(plant, 'z', None))

                    # set growth stage and image/frame
                    try:
                        plant.growth_stage = gstage
                        if hasattr(plant, 'frames') and plant.frames:
                            idx = min(int(plant.growth_stage), len(plant.frames) - 1)
                            plant.image = plant.frames[idx]
                        # ensure rect matches new image/frame
                        try:
                            plant.reposition()
                        except Exception:
                            pass
                        plant.harvestable = plant.growth_stage >= getattr(plant, 'max_stage', 0)
                    except Exception:
                        pass

                    self.plant_sprites.add(plant)
                    self.all_sprites.add(plant)
                except Exception:
                    _logger.exception('restore_state: failed to recreate plant from descriptor %s', pdesc)
        except Exception:
            pass

    def harvest_at_rect(self, rect: pygame.Rect) -> Optional[str]:
        for p in list(self.plant_sprites.sprites()):
            if p.harvestable and p.rect.colliderect(rect):
                plant_type = p.plant_type
                # Prefer stored tile coords (tx,ty) when available so we target the correct grid cell
                tx = getattr(p, 'tx', None)
                ty = getattr(p, 'ty', None)
                if tx is None or ty is None:
                    tx = p.rect.x // self.tile_size
                    ty = p.rect.y // self.tile_size
                # clamp to bounds
                try:
                    tx = int(max(0, min(tx, self.grid_w - 1)))
                    ty = int(max(0, min(ty, self.grid_h - 1)))
                except Exception:
                    pass
                cell = self.grid[ty][tx]
                try:
                    if 'P' in cell:
                        cell.remove('P')
                except Exception:
                    pass
                try:
                    if 'W' in cell:
                        cell.remove('W')
                except Exception:
                    pass
                p.kill()
                _logger.debug("Harvested %s at %s,%s", plant_type, tx, ty)
                return plant_type
        return None


class SoilTile(pygame.sprite.Sprite):
    def __init__(self, pos, surf, groups):
        super().__init__()
        self.image = surf
        self.rect = self.image.get_rect(topleft=pos)
        # use TMX layer if available so soil tiles layer correctly with other sprites
        try:
            from data.config.settings import LAYERS
            self.z = LAYERS.get('soil', 2)
        except Exception:
            self.z = 2
        for g in groups:
            g.add(self)


class WaterTile(pygame.sprite.Sprite):
    def __init__(self, pos, surf, groups):
        super().__init__()
        self.image = surf
        self.rect = self.image.get_rect(topleft=pos)
        try:
            from data.config.settings import LAYERS
            self.z = LAYERS.get('soil water', 2)
        except Exception:
            self.z = 2
        for g in groups:
            g.add(self)
